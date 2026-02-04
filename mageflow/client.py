import asyncio
import functools
import inspect
import os
import random
from datetime import timedelta
from typing import TypeVar, Any, overload, Unpack, Callable, TypedDict

import redis
from hatchet_sdk import Hatchet, Worker, Context
from hatchet_sdk.labels import DesiredWorkerLabel
from hatchet_sdk.rate_limit import RateLimit
from hatchet_sdk.runnables.types import (
    StickyStrategy,
    ConcurrencyExpression,
    DefaultFilter,
)
from hatchet_sdk.runnables.workflow import BaseWorkflow
from hatchet_sdk.worker.worker import LifespanFn
from redis.asyncio import Redis
from typing_extensions import override

from mageflow.callbacks import AcceptParams, register_task, handle_task_callback
from mageflow.chain.creator import chain
from mageflow.init import init_mageflow_hatchet_tasks
from mageflow.invokers.hatchet import HatchetInvoker
from mageflow.signature.creator import sign, TaskSignatureConvertible
from mageflow.signature.model import TaskSignature, TaskInputType
from mageflow.signature.types import HatchetTaskType
from mageflow.startup import (
    lifespan_initialize,
    mageflow_config,
    init_mageflow,
    teardown_mageflow,
)
from mageflow.swarm.creator import swarm, SignatureOptions
from mageflow.utils.mageflow import does_task_wants_ctx

Duration = timedelta | str


class TaskOptions(TypedDict, total=False):
    name: str | None
    description: str | None
    input_validator: type | None
    on_events: list[str] | None
    on_crons: list[str] | None
    version: str | None
    sticky: StickyStrategy | None
    default_priority: int
    concurrency: ConcurrencyExpression | list[ConcurrencyExpression] | None
    schedule_timeout: Duration
    execution_timeout: Duration
    retries: int
    rate_limits: list[RateLimit] | None
    desired_worker_labels: dict[str, DesiredWorkerLabel] | None
    backoff_factor: float | None
    backoff_max_seconds: int | None
    default_filters: list[DefaultFilter] | None


class WorkerOptions(TypedDict, total=False):
    slots: int
    durable_slots: int
    labels: dict[str, str | int] | None
    workflows: list[BaseWorkflow[Any]] | None
    lifespan: LifespanFn | None


async def merge_lifespan(original_lifespan: LifespanFn):
    await init_mageflow()
    async for res in original_lifespan():
        yield res
    await teardown_mageflow()


class HatchetMageflow(Hatchet):
    def __init__(
        self,
        hatchet: Hatchet,
        redis_client: Redis,
        param_config: AcceptParams = AcceptParams.NO_CTX,
    ):
        super().__init__(client=hatchet._client)
        self.hatchet = hatchet
        self.redis = redis_client
        self.param_config = param_config

    @override
    def task(self, name: str | None = None, **kwargs: Unpack[TaskOptions]):
        """
        This is a wrapper for task, if you want to see hatchet task go to parent class
        """

        hatchet_task = super().task(name=name, **kwargs)
        decorator = functools.partial(
            task_decorator,
            hatchet_task=hatchet_task,
            mage_client=self,
            hatchet_task_name=name,
        )
        return decorator

    @override
    def durable_task(self, *, name: str | None = None, **kwargs: Unpack[TaskOptions]):
        """
        This is a wrapper for durable task, if you want to see hatchet durable task go to parent class
        """
        hatchet_task = super().durable_task(name=name, **kwargs)
        decorator = functools.partial(
            task_decorator,
            hatchet_task=hatchet_task,
            mage_client=self,
            hatchet_task_name=name,
        )

        return decorator

    @override
    def worker(
        self,
        name: str,
        *args,
        workflows: list[BaseWorkflow[Any]] | None = None,
        lifespan: LifespanFn | None = None,
        **kwargs: Unpack[WorkerOptions],
    ) -> Worker:
        mageflow_flows = init_mageflow_hatchet_tasks(self.hatchet)
        workflows += mageflow_flows
        if lifespan is None:
            lifespan = lifespan_initialize
        else:
            lifespan = functools.partial(merge_lifespan, lifespan)

        return super().worker(
            name, *args, workflows=workflows, lifespan=lifespan, **kwargs
        )

    async def sign(self, task: str | HatchetTaskType, **options: Any) -> TaskSignature:
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
        **kwargs: Unpack[SignatureOptions],
    ):
        return await swarm(tasks, task_name, **kwargs)

    def with_ctx(self, func):
        func.__user_ctx__ = True
        return func

    def with_signature(self, func):
        func.__send_signature__ = True
        return func

    def stagger_execution(self, wait_delta: timedelta):
        def decorator(func):
            @self.with_ctx
            @functools.wraps(func)
            async def stagger_wrapper(message, ctx: Context, *args, **kwargs):
                stagger = random.uniform(0, wait_delta.total_seconds())
                ctx.log(f"Staggering for {stagger:.2f} seconds")
                ctx.refresh_timeout(timedelta(seconds=stagger))
                await asyncio.sleep(stagger)

                if does_task_wants_ctx(func):
                    return await func(message, ctx, *args, **kwargs)
                else:
                    return await func(message, *args, **kwargs)

            stagger_wrapper.__signature__ = inspect.signature(func)
            return stagger_wrapper

        return decorator


def task_decorator(
    func: Callable,
    hatchet_task,
    mage_client: HatchetMageflow,
    hatchet_task_name: str | None = None,
):
    param_config = (
        AcceptParams.ALL if does_task_wants_ctx(func) else mage_client.param_config
    )
    send_signature = getattr(func, "__send_signature__", False)
    handler_dec = handle_task_callback(param_config, send_signature=send_signature)
    func = handler_dec(func)
    wf = hatchet_task(func)

    task_name = hatchet_task_name or func.__name__
    register = register_task(task_name)
    return register(wf)


T = TypeVar("T")


@overload
def Mageflow(
    hatchet_client: Hatchet,
    redis_client: Redis | str = None,
    param_config: AcceptParams = AcceptParams.NO_CTX,
) -> HatchetMageflow: ...


@overload
def Mageflow(
    taskiq_broker: Any,
    redis_client: Redis | str = None,
    param_config: AcceptParams = AcceptParams.NO_CTX,
) -> Any: ...


def Mageflow(
    hatchet_client: T = None,
    taskiq_broker: Any = None,
    redis_client: Redis | str = None,
    param_config: AcceptParams = AcceptParams.NO_CTX,
) -> T:
    """
    Create a Mageflow client for the specified backend.

    This factory function is the ONLY place where backend type is determined.
    All other code uses the configured backend without type checking.

    Usage:
        # With Hatchet
        from hatchet_sdk import Hatchet
        mage = Mageflow(hatchet_client=Hatchet())

        # With TaskIQ
        from taskiq_redis import ListQueueBroker
        mage = Mageflow(taskiq_broker=ListQueueBroker(...))

    Args:
        hatchet_client: Hatchet client instance
        taskiq_broker: TaskIQ broker instance
        redis_client: Redis client or URL for state management
        param_config: Default parameter configuration for tasks

    Returns:
        HatchetMageflow or TaskIQMageflow depending on which client was passed
    """
    from mageflow.backends.protocol import BackendType

    # Configure Redis (common to all backends)
    if redis_client is None:
        redis_url = os.getenv("REDIS_URL")
        if redis_url is None:
            raise ValueError(
                "redis_client must be provided or REDIS_URL environment variable must be set"
            )
        redis_client = redis.asyncio.from_url(redis_url, decode_responses=True)
    if isinstance(redis_client, str):
        redis_client = redis.asyncio.from_url(redis_client, decode_responses=True)
    mageflow_config.redis_client = redis_client

    # =========================================================================
    # BACKEND TYPE DETECTION - The ONLY place this happens
    # =========================================================================

    if taskiq_broker is not None:
        # TaskIQ backend
        from mageflow.backends.taskiq_client import TaskIQMageflow

        mageflow_config.backend_type = BackendType.TASKIQ

        client = TaskIQMageflow(taskiq_broker, redis_client, param_config)
        mageflow_config.task_trigger = client._task_trigger

        return client

    else:
        # Hatchet backend (default)
        if hatchet_client is None:
            hatchet_client = Hatchet()

        mageflow_config.backend_type = BackendType.HATCHET

        # Create a hatchet client with empty namespace for creating workflows
        config = hatchet_client._client.config.model_copy(deep=True)
        config.namespace = ""
        hatchet_caller = Hatchet(config=config, debug=hatchet_client._client.debug)
        mageflow_config.hatchet_client = hatchet_caller
        HatchetInvoker.client = hatchet_client

        return HatchetMageflow(hatchet_client, redis_client, param_config)
