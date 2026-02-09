import asyncio
import functools
import inspect
import os
import random
from datetime import timedelta
from typing import TypeVar, Any, Callable

import redis
from redis.asyncio import Redis

from mageflow.callbacks import AcceptParams, register_task, handle_task_callback
from mageflow.chain.creator import chain
from mageflow.init import init_mageflow_internal_tasks
from mageflow.invokers.base import TaskClientAdapter
from mageflow.signature.creator import sign, TaskSignatureConvertible
from mageflow.signature.model import TaskSignature, TaskInputType
from mageflow.signature.types import TaskType
from mageflow.startup import (
    lifespan_initialize,
    mageflow_config,
    init_mageflow,
    teardown_mageflow,
)
from mageflow.swarm.creator import swarm, SignatureOptions
from mageflow.utils.mageflow import does_task_wants_ctx

Duration = timedelta | str


async def merge_lifespan(original_lifespan):
    await init_mageflow()
    async for res in original_lifespan():
        yield res
    await teardown_mageflow()


class MageflowClient:
    """
    Client-agnostic Mageflow interface.

    Wraps any TaskClientAdapter (Hatchet, Temporal, etc.) and provides
    the unified task orchestration API (task, durable_task, worker, sign,
    chain, swarm, etc.).
    """

    def __init__(
        self,
        adapter: TaskClientAdapter,
        redis_client: Redis,
        param_config: AcceptParams = AcceptParams.NO_CTX,
    ):
        self.adapter = adapter
        self.redis = redis_client
        self.param_config = param_config

    def task(self, name: str | None = None, **kwargs):
        """
        Decorator that registers a function as a mageflow task.

        The underlying client adapter handles the actual task registration.
        """
        client_task_decorator = self.adapter.task(name=name, **kwargs)

        decorator = functools.partial(
            _task_decorator,
            client_task_decorator=client_task_decorator,
            mage_client=self,
            task_name=name,
        )
        return decorator

    def durable_task(self, *, name: str | None = None, **kwargs):
        """
        Decorator that registers a function as a durable/long-running mageflow task.
        """
        client_task_decorator = self.adapter.durable_task(name=name, **kwargs)

        decorator = functools.partial(
            _task_decorator,
            client_task_decorator=client_task_decorator,
            mage_client=self,
            task_name=name,
        )
        return decorator

    def worker(self, name: str, *args, workflows=None, lifespan=None, **kwargs):
        """Create a worker, auto-registering internal mageflow tasks."""
        internal_tasks = init_mageflow_internal_tasks(self.adapter)

        if workflows is None:
            workflows = []
        workflows = workflows + internal_tasks

        if lifespan is None:
            lifespan = lifespan_initialize
        else:
            lifespan = functools.partial(merge_lifespan, lifespan)

        return self.adapter.worker(
            name, *args, workflows=workflows, lifespan=lifespan, **kwargs
        )

    async def sign(self, task: str | TaskType, **options: Any) -> TaskSignature:
        return await sign(task, **options)

    async def chain(
        self,
        tasks: list[TaskSignatureConvertible],
        name: str = None,
        error: TaskInputType = None,
        success: TaskInputType = None,
    ):
        return await chain(tasks, name, error, success)

    async def swarm(
        self,
        tasks: list[TaskSignatureConvertible] = None,
        task_name: str = None,
        **kwargs,
    ):
        return await swarm(tasks, task_name, **kwargs)

    def with_ctx(self, func):
        """Mark a function to receive the client context as second argument."""
        func.__user_ctx__ = True
        return func

    def with_signature(self, func):
        """Mark a function to receive its TaskSignature via kwargs."""
        func.__send_signature__ = True
        return func

    def stagger_execution(self, wait_delta: timedelta):
        """Decorator to add a random stagger delay before task execution."""

        def decorator(func):
            @self.with_ctx
            @functools.wraps(func)
            async def stagger_wrapper(message, ctx, *args, **kwargs):
                stagger = random.uniform(0, wait_delta.total_seconds())

                # Use adapter-agnostic logging and timeout refresh
                invoker = self.adapter.create_invoker(message, ctx)
                await invoker.log(f"Staggering for {stagger:.2f} seconds")
                await invoker.refresh_timeout(timedelta(seconds=stagger))
                await asyncio.sleep(stagger)

                if does_task_wants_ctx(func):
                    return await func(message, ctx, *args, **kwargs)
                else:
                    return await func(message, *args, **kwargs)

            stagger_wrapper.__signature__ = inspect.signature(func)
            return stagger_wrapper

        return decorator


# Backward-compatible alias
HatchetMageflow = MageflowClient


def _task_decorator(
    func: Callable,
    client_task_decorator,
    mage_client: MageflowClient,
    task_name: str | None = None,
):
    """Apply mageflow callback handling, then the client's task decorator, then register."""
    param_config = (
        AcceptParams.ALL if does_task_wants_ctx(func) else mage_client.param_config
    )
    send_signature = getattr(func, "__send_signature__", False)
    handler_dec = handle_task_callback(param_config, send_signature=send_signature)
    func = handler_dec(func)
    wf = client_task_decorator(func)

    name = task_name or func.__name__
    register = register_task(name)
    return register(wf)


# Keep old name
task_decorator = _task_decorator


T = TypeVar("T")


def _resolve_redis(redis_client: Redis | str | None) -> Redis:
    if redis_client is None:
        redis_url = os.getenv("REDIS_URL")
        return redis.asyncio.from_url(redis_url, decode_responses=True)
    if isinstance(redis_client, str):
        return redis.asyncio.from_url(redis_client, decode_responses=True)
    return redis_client


def Mageflow(
    client=None,
    redis_client: Redis | str = None,
    param_config: AcceptParams = AcceptParams.NO_CTX,
    task_queue: str = "mageflow",
) -> MageflowClient:
    """
    Factory function to create a MageflowClient from a task manager client.

    Supports:
    - Hatchet: pass a hatchet_sdk.Hatchet instance
    - Temporal: pass a temporalio.client.Client instance
    - None: defaults to Hatchet() if hatchet_sdk is available

    Examples:
        # Hatchet
        from hatchet_sdk import Hatchet
        mf = Mageflow(Hatchet())

        # Temporal
        from temporalio.client import Client
        temporal_client = await Client.connect("localhost:7233")
        mf = Mageflow(temporal_client, task_queue="my-queue")
    """
    adapter = _create_adapter(client, task_queue)

    redis_resolved = _resolve_redis(redis_client)
    mageflow_config.adapter = adapter
    mageflow_config.redis_client = redis_resolved

    # For backward compat: set HatchetInvoker.client if using Hatchet
    if hasattr(adapter, "client"):
        try:
            from mageflow.invokers.hatchet import HatchetInvoker

            HatchetInvoker.client = adapter.client
        except ImportError:
            pass

    return MageflowClient(adapter, redis_resolved, param_config)


def _create_adapter(client, task_queue: str = "mageflow") -> TaskClientAdapter:
    """Detect the client type and create the appropriate adapter."""
    if client is None:
        try:
            from hatchet_sdk import Hatchet

            client = Hatchet()
        except ImportError:
            raise RuntimeError(
                "No task manager client provided and hatchet_sdk not installed. "
                "Install hatchet-sdk or temporalio, then pass the client to Mageflow()."
            )

    # Check if it's a Hatchet client
    try:
        from hatchet_sdk import Hatchet

        if isinstance(client, Hatchet):
            from mageflow.invokers.hatchet import HatchetClientAdapter

            # Create a caller with empty namespace for workflow creation
            config = client._client.config.model_copy(deep=True)
            config.namespace = ""
            hatchet_caller = Hatchet(config=config, debug=client._client.debug)
            return HatchetClientAdapter(client, hatchet_caller)
    except ImportError:
        pass

    # Check if it's a Temporal client
    try:
        from temporalio.client import Client as TemporalClient

        if isinstance(client, TemporalClient):
            from mageflow.invokers.temporal import TemporalClientAdapter

            return TemporalClientAdapter(client, task_queue=task_queue)
    except ImportError:
        pass

    # Check if it's already an adapter
    if isinstance(client, TaskClientAdapter):
        return client

    raise TypeError(
        f"Unsupported client type: {type(client).__name__}. "
        f"Expected Hatchet, temporalio.client.Client, or a TaskClientAdapter."
    )
