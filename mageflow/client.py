"""
Unified MageFlow client with multi-backend support.

This module provides a unified API for task orchestration that works
with multiple backends (Hatchet, TaskIQ) through dependency injection.
"""

import asyncio
import functools
import inspect
import os
import random
from abc import ABC, abstractmethod
from datetime import timedelta
from typing import TypeVar, Any, overload, Unpack, Callable, Generic

import redis
from redis.asyncio import Redis
from pydantic import BaseModel
from typing_extensions import override

from mageflow.backends.base import BackendClient, BackendType, TaskContext
from mageflow.callbacks import AcceptParams, register_task, handle_task_callback
from mageflow.chain.creator import chain
from mageflow.signature.creator import sign, TaskSignatureConvertible
from mageflow.signature.model import TaskSignature, TaskInputType
from mageflow.startup import (
    lifespan_initialize,
    mageflow_config,
    init_mageflow,
    teardown_mageflow,
)
from mageflow.swarm.creator import swarm, SignatureOptions
from mageflow.utils.mageflow import does_task_wants_ctx


T = TypeVar("T")
TBackend = TypeVar("TBackend", bound=BackendClient)


class BaseMageflow(ABC, Generic[TBackend]):
    """
    Abstract base class for MageFlow clients.

    This class defines the common API that all MageFlow implementations
    must provide, regardless of the underlying backend.
    """

    def __init__(
        self,
        backend: TBackend,
        redis_client: Redis,
        param_config: AcceptParams = AcceptParams.NO_CTX,
    ):
        self._backend = backend
        self.redis = redis_client
        self.param_config = param_config

    @property
    def backend(self) -> TBackend:
        """Access the underlying backend client."""
        return self._backend

    @property
    def backend_type(self) -> BackendType:
        """Get the type of backend being used."""
        return self._backend.backend_type

    @abstractmethod
    def task(self, *, name: str | None = None, **kwargs) -> Callable:
        """Decorator for defining tasks."""
        pass

    @abstractmethod
    def durable_task(self, *, name: str | None = None, **kwargs) -> Callable:
        """Decorator for defining durable (long-running) tasks."""
        pass

    @abstractmethod
    def worker(self, *args, workflows=None, lifespan=None, **kwargs):
        """Create a worker to process tasks."""
        pass

    async def sign(self, task: str | Any, **options: Any) -> TaskSignature:
        """Create a task signature."""
        return await sign(task, **options)

    async def chain(
        self,
        tasks: list[TaskSignatureConvertible],
        name: str = None,
        error: TaskInputType = None,
        success: TaskInputType = None,
    ):
        """Create a chain of tasks to execute sequentially."""
        return await chain(tasks, name, error, success)

    async def swarm(
        self,
        tasks: list[TaskSignatureConvertible] = None,
        task_name: str = None,
        **kwargs: Unpack[SignatureOptions],
    ):
        """Create a swarm of tasks to execute in parallel."""
        return await swarm(tasks, task_name, **kwargs)

    def with_ctx(self, func):
        """Mark a task function as wanting the raw context."""
        func.__user_ctx__ = True
        return func

    def with_signature(self, func):
        """Mark a task function as wanting the TaskSignature."""
        func.__send_signature__ = True
        return func

    def stagger_execution(self, wait_delta: timedelta):
        """Decorator to add random delay before task execution."""

        def decorator(func):
            @self.with_ctx
            @functools.wraps(func)
            async def stagger_wrapper(message, ctx, *args, **kwargs):
                stagger = random.uniform(0, wait_delta.total_seconds())
                self._backend.log(ctx, f"Staggering for {stagger:.2f} seconds")
                self._backend.refresh_timeout(ctx, stagger)
                await asyncio.sleep(stagger)

                if does_task_wants_ctx(func):
                    return await func(message, ctx, *args, **kwargs)
                else:
                    return await func(message, *args, **kwargs)

            stagger_wrapper.__signature__ = inspect.signature(func)
            return stagger_wrapper

        return decorator


# ============================================================================
# Hatchet Backend Implementation
# ============================================================================

try:
    from hatchet_sdk import Hatchet, Worker, Context
    from hatchet_sdk.runnables.workflow import BaseWorkflow
    from hatchet_sdk.worker.worker import LifespanFn
    from mageflow.backends.hatchet import HatchetBackend
    from mageflow.init import init_mageflow_hatchet_tasks
    from mageflow.signature.types import HatchetTaskType

    async def merge_lifespan(original_lifespan: LifespanFn):
        """Merge user lifespan with MageFlow initialization."""
        await init_mageflow()
        async for res in original_lifespan():
            yield res
        await teardown_mageflow()

    class HatchetMageflow(BaseMageflow[HatchetBackend], Hatchet):
        """
        MageFlow client for Hatchet backend.

        This class provides the MageFlow API on top of Hatchet,
        allowing task orchestration with chains, swarms, and signatures.
        """

        def __init__(
            self,
            hatchet: Hatchet,
            redis_client: Redis,
            param_config: AcceptParams = AcceptParams.NO_CTX,
        ):
            # Initialize Hatchet
            Hatchet.__init__(self, client=hatchet._client)
            self.hatchet = hatchet

            # Create backend wrapper
            backend = HatchetBackend(hatchet)

            # Initialize BaseMageflow
            BaseMageflow.__init__(self, backend, redis_client, param_config)

        @override
        def task(self, *, name: str | None = None, **kwargs):
            """Decorator for defining Hatchet tasks."""
            hatchet_task = Hatchet.task(self, name=name, **kwargs)
            decorator = functools.partial(
                task_decorator,
                hatchet_task=hatchet_task,
                mage_client=self,
                hatchet_task_name=name,
            )
            return decorator

        @override
        def durable_task(self, *, name: str | None = None, **kwargs):
            """Decorator for defining Hatchet durable tasks."""
            hatchet_task = Hatchet.durable_task(self, name=name, **kwargs)
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
            *args,
            workflows: list[BaseWorkflow[Any]] | None = None,
            lifespan: LifespanFn | None = None,
            **kwargs,
        ) -> Worker:
            """Create a Hatchet worker with MageFlow tasks."""
            mageflow_flows = init_mageflow_hatchet_tasks(self.hatchet)
            if workflows is None:
                workflows = []
            workflows = workflows + mageflow_flows
            if lifespan is None:
                lifespan = lifespan_initialize
            else:
                lifespan = functools.partial(merge_lifespan, lifespan)

            return Hatchet.worker(self, *args, workflows=workflows, lifespan=lifespan, **kwargs)

        def stagger_execution(self, wait_delta: timedelta):
            """Hatchet-specific stagger execution with context refresh."""

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
        """Internal decorator for wrapping task functions."""
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

    HATCHET_AVAILABLE = True
except ImportError:
    HATCHET_AVAILABLE = False
    HatchetMageflow = None
    HatchetBackend = None


# ============================================================================
# TaskIQ Backend Implementation
# ============================================================================

try:
    from mageflow.backends.taskiq import TaskIQBackend, TaskIQContext

    class TaskIQMageflow(BaseMageflow[TaskIQBackend]):
        """
        MageFlow client for TaskIQ backend.

        This class provides the MageFlow API on top of TaskIQ,
        allowing task orchestration with chains, swarms, and signatures.
        """

        def __init__(
            self,
            broker: Any,
            redis_client: Redis,
            param_config: AcceptParams = AcceptParams.NO_CTX,
        ):
            backend = TaskIQBackend(broker)
            super().__init__(backend, redis_client, param_config)
            self._broker = broker

        @property
        def broker(self) -> Any:
            """Access the underlying TaskIQ broker."""
            return self._broker

        @override
        def task(self, *, name: str | None = None, **kwargs):
            """Decorator for defining TaskIQ tasks."""
            taskiq_decorator = self._backend.create_task_decorator(name=name, **kwargs)

            def decorator(func: Callable) -> Any:
                param_config = (
                    AcceptParams.ALL if does_task_wants_ctx(func) else self.param_config
                )
                send_signature = getattr(func, "__send_signature__", False)
                handler_dec = handle_task_callback(
                    param_config, send_signature=send_signature, backend_type=BackendType.TASKIQ
                )
                wrapped_func = handler_dec(func)
                task = taskiq_decorator(wrapped_func)

                task_name = name or func.__name__
                register = register_task(task_name)
                return register(task)

            return decorator

        @override
        def durable_task(self, *, name: str | None = None, **kwargs):
            """Decorator for defining TaskIQ durable tasks."""
            taskiq_decorator = self._backend.create_durable_task_decorator(name=name, **kwargs)

            def decorator(func: Callable) -> Any:
                param_config = (
                    AcceptParams.ALL if does_task_wants_ctx(func) else self.param_config
                )
                send_signature = getattr(func, "__send_signature__", False)
                handler_dec = handle_task_callback(
                    param_config, send_signature=send_signature, backend_type=BackendType.TASKIQ
                )
                wrapped_func = handler_dec(func)
                task = taskiq_decorator(wrapped_func)

                task_name = name or func.__name__
                register = register_task(task_name)
                return register(task)

            return decorator

        @override
        def worker(
            self,
            *args,
            workflows: list[Any] | None = None,
            lifespan: Callable | None = None,
            **kwargs,
        ):
            """Create a TaskIQ worker with MageFlow tasks."""
            mageflow_tasks = self._backend.init_mageflow_tasks()
            if workflows is None:
                workflows = []
            workflows = workflows + mageflow_tasks
            return self._backend.create_worker(workflows=workflows, lifespan=lifespan, **kwargs)

    TASKIQ_AVAILABLE = True
except ImportError:
    TASKIQ_AVAILABLE = False
    TaskIQMageflow = None
    TaskIQBackend = None


# ============================================================================
# Unified Factory Functions
# ============================================================================


@overload
def Mageflow(
    hatchet_client: "Hatchet", redis_client: Redis | str = None
) -> "HatchetMageflow": ...


@overload
def Mageflow(
    taskiq_broker: Any,
    redis_client: Redis | str = None,
    *,
    backend: BackendType = BackendType.TASKIQ,
) -> "TaskIQMageflow": ...


def Mageflow(
    client: T = None,
    redis_client: Redis | str = None,
    param_config: AcceptParams = AcceptParams.NO_CTX,
    backend: BackendType | None = None,
) -> T:
    """
    Factory function to create a MageFlow client.

    This function automatically detects the backend type based on the client
    provided, or you can explicitly specify the backend type.

    Args:
        client: The backend client (Hatchet instance or TaskIQ broker)
        redis_client: Redis client or connection string
        param_config: Parameter configuration for task functions
        backend: Explicit backend type (auto-detected if not provided)

    Returns:
        A MageFlow client instance appropriate for the backend

    Examples:
        # With Hatchet (auto-detected)
        from hatchet_sdk import Hatchet
        mageflow = Mageflow(Hatchet())

        # With TaskIQ (explicit)
        from taskiq import InMemoryBroker
        mageflow = Mageflow(InMemoryBroker(), backend=BackendType.TASKIQ)

        # With TaskIQ (auto-detected via has 'task' attribute check)
        mageflow = Mageflow(broker)
    """
    # Initialize Redis
    if redis_client is None:
        redis_url = os.getenv("REDIS_URL")
        redis_client = redis.asyncio.from_url(redis_url, decode_responses=True)
    if isinstance(redis_client, str):
        redis_client = redis.asyncio.from_url(redis_client, decode_responses=True)
    mageflow_config.redis_client = redis_client

    # Auto-detect backend type if not specified
    if backend is None:
        backend = _detect_backend_type(client)

    if backend == BackendType.HATCHET:
        return _create_hatchet_mageflow(client, redis_client, param_config)
    elif backend == BackendType.TASKIQ:
        return _create_taskiq_mageflow(client, redis_client, param_config)
    else:
        raise ValueError(f"Unsupported backend type: {backend}")


def _detect_backend_type(client: Any) -> BackendType:
    """Detect the backend type from the client instance."""
    if client is None:
        # Default to Hatchet if no client provided
        return BackendType.HATCHET

    # Check for Hatchet
    if HATCHET_AVAILABLE:
        from hatchet_sdk import Hatchet

        if isinstance(client, Hatchet):
            return BackendType.HATCHET

    # Check for TaskIQ broker (has 'task' decorator method)
    if hasattr(client, "task") and hasattr(client, "startup") and hasattr(client, "shutdown"):
        return BackendType.TASKIQ

    # Check class name as fallback
    client_class_name = type(client).__name__.lower()
    if "hatchet" in client_class_name:
        return BackendType.HATCHET
    if "broker" in client_class_name or "taskiq" in client_class_name:
        return BackendType.TASKIQ

    # Default to Hatchet for backwards compatibility
    return BackendType.HATCHET


def _create_hatchet_mageflow(
    client: Any, redis_client: Redis, param_config: AcceptParams
) -> "HatchetMageflow":
    """Create a HatchetMageflow instance."""
    if not HATCHET_AVAILABLE:
        raise ImportError(
            "Hatchet SDK is not installed. Install it with: pip install hatchet-sdk"
        )

    from hatchet_sdk import Hatchet

    if client is None:
        client = Hatchet()

    # Create a hatchet client with empty namespace for creating workflows
    config = client._client.config.model_copy(deep=True)
    config.namespace = ""
    hatchet_caller = Hatchet(config=config, debug=client._client.debug)
    mageflow_config.hatchet_client = hatchet_caller

    return HatchetMageflow(client, redis_client, param_config)


def _create_taskiq_mageflow(
    broker: Any, redis_client: Redis, param_config: AcceptParams
) -> "TaskIQMageflow":
    """Create a TaskIQMageflow instance."""
    if not TASKIQ_AVAILABLE:
        raise ImportError(
            "TaskIQ backend is not available. Check your installation."
        )

    if broker is None:
        raise ValueError("TaskIQ broker must be provided")

    # Store reference for workflow creation
    mageflow_config.taskiq_broker = broker

    return TaskIQMageflow(broker, redis_client, param_config)


# Backwards compatibility alias
__all__ = [
    "Mageflow",
    "BaseMageflow",
    "HatchetMageflow",
    "TaskIQMageflow",
    "AcceptParams",
    "BackendType",
]
