"""
Mageflow Client - Task Manager Agnostic Entry Point.

This module provides the main entry point for using Mageflow. It handles:
1. Detecting/selecting the task manager type (Hatchet, TaskIQ, etc.)
2. Creating the appropriate adapter
3. Providing a unified API for task management

IMPORTANT: This is the ONLY file where task manager type checking occurs.
All other code uses the adapter protocols and doesn't care about the specific
task manager implementation.
"""
import asyncio
import functools
import inspect
import os
import random
from datetime import timedelta
from typing import TypeVar, Any, overload, Callable, TYPE_CHECKING

import redis.asyncio
from redis.asyncio import Redis

from mageflow.adapters.protocols import (
    TaskManagerAdapter,
    TaskManagerType,
    TaskContext,
    WorkflowAdapter,
    WorkerAdapter,
    TaskOptions,
)
from mageflow.adapters.registry import get_adapter, detect_adapter_type
from mageflow.callbacks_new import (
    AcceptParams,
    register_task,
    create_task_callback_handler,
    REGISTERED_TASKS,
)
from mageflow.chain.creator import chain
from mageflow.invokers.base import BaseInvoker
from mageflow.signature.creator import sign, TaskSignatureConvertible
from mageflow.signature.model import TaskSignature, TaskInputType
from mageflow.startup import mageflow_config
from mageflow.swarm.creator import swarm, SignatureOptions
from mageflow.utils.mageflow import does_task_wants_ctx

if TYPE_CHECKING:
    from mageflow.adapters.hatchet import HatchetAdapter
    from mageflow.adapters.taskiq import TaskIQAdapter

try:
    from typing import Unpack
except ImportError:
    from typing_extensions import Unpack


T = TypeVar("T")


class MageflowClient:
    """
    Task-manager-agnostic Mageflow client.

    This class provides the unified API for creating tasks, workers,
    and managing task workflows. It delegates to the appropriate adapter
    based on the configured task manager.

    Example usage:
        # With Hatchet (auto-detected)
        from hatchet_sdk import Hatchet
        mage = Mageflow(hatchet_client=Hatchet())

        # With TaskIQ
        from taskiq_redis import RedisBroker
        mage = Mageflow(taskiq_broker=RedisBroker(...))

        # Explicit type
        mage = Mageflow(adapter_type=TaskManagerType.HATCHET)

        # Then use as normal
        @mage.task(name="my_task")
        async def my_task(msg):
            ...
    """

    def __init__(
        self,
        adapter: TaskManagerAdapter,
        redis_client: Redis,
        param_config: AcceptParams = AcceptParams.NO_CTX,
    ):
        """
        Initialize the Mageflow client.

        Args:
            adapter: The task manager adapter to use
            redis_client: Redis client for state management
            param_config: Default parameter configuration for tasks
        """
        self._adapter = adapter
        self._redis = redis_client
        self._param_config = param_config

        # Set up the invoker factory based on adapter type
        self._setup_invoker()

    def _setup_invoker(self):
        """Configure the invoker based on adapter type."""
        if self._adapter.adapter_type == TaskManagerType.HATCHET:
            from mageflow.adapters.hatchet.invoker import HatchetInvokerNew

            HatchetInvokerNew.adapter = self._adapter
            self._invoker_class = HatchetInvokerNew
        elif self._adapter.adapter_type == TaskManagerType.TASKIQ:
            # TaskIQ uses the same invoker logic, just with different context extraction
            from mageflow.adapters.hatchet.invoker import HatchetInvokerNew

            # TODO: Create TaskIQInvoker if needed
            HatchetInvokerNew.adapter = self._adapter
            self._invoker_class = HatchetInvokerNew

    def _create_invoker(self, message, execution_info, task_context) -> BaseInvoker:
        """Create an invoker for task execution."""
        return self._invoker_class(message, execution_info, task_context)

    @property
    def adapter(self) -> TaskManagerAdapter:
        """Get the underlying task manager adapter."""
        return self._adapter

    @property
    def redis(self) -> Redis:
        """Get the Redis client."""
        return self._redis

    @property
    def param_config(self) -> AcceptParams:
        """Get the default parameter configuration."""
        return self._param_config

    def task(self, name: str | None = None, **options: Unpack[TaskOptions]):
        """
        Decorator to create a task.

        This creates a task that is managed by Mageflow and executed by
        the configured task manager (Hatchet, TaskIQ, etc.).

        Args:
            name: Task name (defaults to function name)
            **options: Task configuration options

        Returns:
            Decorator for the task function
        """
        # Get the native task decorator from the adapter
        native_task = self._adapter.task(name=name, **options)

        decorator = functools.partial(
            self._task_decorator,
            native_task=native_task,
            task_name=name,
        )
        return decorator

    def durable_task(self, name: str | None = None, **options: Unpack[TaskOptions]):
        """
        Decorator to create a durable task.

        Durable tasks survive worker restarts (implementation varies by task manager).

        Args:
            name: Task name (defaults to function name)
            **options: Task configuration options

        Returns:
            Decorator for the task function
        """
        native_task = self._adapter.durable_task(name=name, **options)

        decorator = functools.partial(
            self._task_decorator,
            native_task=native_task,
            task_name=name,
        )
        return decorator

    def _task_decorator(
        self,
        func: Callable,
        native_task: Callable,
        task_name: str | None = None,
    ):
        """
        Internal task decorator that wraps user functions.

        This:
        1. Determines parameter configuration based on function signature
        2. Wraps with Mageflow callback handler
        3. Applies the native task decorator
        4. Registers the task
        """
        # Determine param config based on whether user wants ctx
        param_config = (
            AcceptParams.ALL if does_task_wants_ctx(func) else self._param_config
        )
        send_signature = getattr(func, "__send_signature__", False)

        # Create the callback handler
        handler_dec = create_task_callback_handler(
            adapter=self._adapter,
            invoker_factory=self._create_invoker,
            expected_params=param_config,
            send_signature=send_signature,
        )
        func = handler_dec(func)

        # Apply native task decorator
        wf = native_task(func)

        # Register with Mageflow
        name = task_name or func.__name__
        register = register_task(name)
        return register(wf)

    def worker(
        self,
        name: str,
        workflows: list[Any] | None = None,
        lifespan: Callable | None = None,
        **options: Any,
    ) -> WorkerAdapter:
        """
        Create a worker that processes tasks.

        Args:
            name: Worker name
            workflows: List of workflows/tasks to run
            lifespan: Async context manager for worker lifecycle
            **options: Additional worker options

        Returns:
            WorkerAdapter that can be started
        """
        from mageflow.startup import lifespan_initialize

        # Add framework tasks
        framework_tasks = self._adapter.create_framework_tasks()
        all_workflows = (workflows or []) + framework_tasks

        # Handle lifespan
        if lifespan is None:
            final_lifespan = lifespan_initialize
        else:
            final_lifespan = functools.partial(self._merge_lifespan, lifespan)

        return self._adapter.worker(
            name,
            workflows=all_workflows,
            lifespan=final_lifespan,
            **options,
        )

    async def _merge_lifespan(self, original_lifespan: Callable):
        """Merge user lifespan with Mageflow initialization."""
        from mageflow.startup import init_mageflow, teardown_mageflow

        await init_mageflow()
        async for res in original_lifespan():
            yield res
        await teardown_mageflow()

    async def sign(self, task: str | Any, **options: Any) -> TaskSignature:
        """Create a task signature for later execution."""
        return await sign(task, **options)

    async def chain(
        self,
        tasks: list[TaskSignatureConvertible],
        name: str = None,
        error: TaskInputType = None,
        success: TaskInputType = None,
    ):
        """Create a chain of tasks that execute sequentially."""
        return await chain(tasks, name, error, success)

    async def swarm(
        self,
        tasks: list[TaskSignatureConvertible] = None,
        task_name: str = None,
        **kwargs: Unpack[SignatureOptions],
    ):
        """Create a swarm of tasks that execute in parallel."""
        return await swarm(tasks, task_name, **kwargs)

    def with_ctx(self, func):
        """
        Decorator to mark a task function as wanting the context parameter.

        When applied, the task function will receive the TaskContext as
        its second parameter.
        """
        func.__user_ctx__ = True
        return func

    def with_signature(self, func):
        """
        Decorator to mark a task function as wanting the signature parameter.

        When applied, the task function will receive the TaskSignature
        as a keyword argument.
        """
        func.__send_signature__ = True
        return func

    def stagger_execution(self, wait_delta: timedelta):
        """
        Decorator to add random stagger before task execution.

        This helps prevent thundering herd problems when many tasks
        are scheduled simultaneously.

        Args:
            wait_delta: Maximum stagger time
        """

        def decorator(func):
            @self.with_ctx
            @functools.wraps(func)
            async def stagger_wrapper(
                message, task_context: TaskContext, *args, **kwargs
            ):
                stagger = random.uniform(0, wait_delta.total_seconds())
                task_context.log(f"Staggering for {stagger:.2f} seconds")
                task_context.refresh_timeout(timedelta(seconds=stagger))
                await asyncio.sleep(stagger)

                if does_task_wants_ctx(func):
                    return await func(message, task_context, *args, **kwargs)
                else:
                    return await func(message, *args, **kwargs)

            stagger_wrapper.__signature__ = inspect.signature(func)
            return stagger_wrapper

        return decorator


# ============================================================================
# Factory Function - The ONLY place where task manager type is determined
# ============================================================================


@overload
def Mageflow(
    hatchet_client: Any,
    redis_client: Redis | str = None,
    param_config: AcceptParams = AcceptParams.NO_CTX,
) -> MageflowClient: ...


@overload
def Mageflow(
    taskiq_broker: Any,
    redis_client: Redis | str = None,
    param_config: AcceptParams = AcceptParams.NO_CTX,
) -> MageflowClient: ...


@overload
def Mageflow(
    adapter_type: TaskManagerType,
    redis_client: Redis | str = None,
    param_config: AcceptParams = AcceptParams.NO_CTX,
    **adapter_config,
) -> MageflowClient: ...


def Mageflow(
    hatchet_client: Any = None,
    taskiq_broker: Any = None,
    adapter_type: TaskManagerType = None,
    redis_client: Redis | str = None,
    param_config: AcceptParams = AcceptParams.NO_CTX,
    **adapter_config,
) -> MageflowClient:
    """
    Create a Mageflow client.

    This is the factory function that creates a MageflowClient with the
    appropriate task manager adapter. It's the ONLY place where task
    manager type detection/selection occurs.

    Usage:
        # With Hatchet (most common)
        from hatchet_sdk import Hatchet
        mage = Mageflow(hatchet_client=Hatchet())

        # With TaskIQ
        from taskiq_redis import RedisBroker
        mage = Mageflow(taskiq_broker=RedisBroker(...))

        # Explicit type selection
        mage = Mageflow(adapter_type=TaskManagerType.HATCHET)

    Args:
        hatchet_client: Hatchet client instance
        taskiq_broker: TaskIQ broker instance
        adapter_type: Explicit task manager type
        redis_client: Redis client or URL for state management
        param_config: Default parameter configuration for tasks
        **adapter_config: Additional adapter configuration

    Returns:
        Configured MageflowClient
    """
    # ==========================================================================
    # TASK MANAGER TYPE DETECTION - The only if-checks for task manager type
    # ==========================================================================

    if hatchet_client is not None:
        # Hatchet path
        adapter_type = TaskManagerType.HATCHET
        adapter_config["client"] = hatchet_client

    elif taskiq_broker is not None:
        # TaskIQ path
        adapter_type = TaskManagerType.TASKIQ
        adapter_config["broker"] = taskiq_broker

    elif adapter_type is None:
        # Auto-detect: default to Hatchet
        adapter_type = TaskManagerType.HATCHET

    # Create the adapter (this uses the registry, no if-checks)
    adapter = get_adapter(adapter_type, **adapter_config)

    # Store adapter reference for workflow creation
    # This is adapter-type-agnostic
    mageflow_config.task_adapter = adapter

    # For backwards compatibility with existing code that uses hatchet_client
    if adapter_type == TaskManagerType.HATCHET:
        from hatchet_sdk import Hatchet

        # Create workflow client for Hatchet
        native_client = adapter.native_client
        config = native_client._client.config.model_copy(deep=True)
        config.namespace = ""
        workflow_client = Hatchet(config=config, debug=native_client._client.debug)
        mageflow_config.hatchet_client = workflow_client

        # Set up HatchetInvoker
        from mageflow.invokers.hatchet import HatchetInvoker

        HatchetInvoker.client = native_client

    # ==========================================================================
    # END OF TASK MANAGER TYPE DETECTION
    # ==========================================================================

    # Configure Redis (same for all adapters)
    if redis_client is None:
        redis_url = os.getenv("REDIS_URL")
        if redis_url:
            redis_client = redis.asyncio.from_url(redis_url, decode_responses=True)
        else:
            raise ValueError(
                "redis_client must be provided or REDIS_URL environment variable must be set"
            )
    if isinstance(redis_client, str):
        redis_client = redis.asyncio.from_url(redis_client, decode_responses=True)
    mageflow_config.redis_client = redis_client

    return MageflowClient(adapter, redis_client, param_config)
