"""
TaskIQ task manager adapter.

This module provides the TaskIQ implementation of the TaskManagerAdapter.
It's a skeleton/template showing what needs to be implemented for TaskIQ support.

NOTE: This is a skeleton implementation. Full TaskIQ support requires:
1. Installing taskiq packages (taskiq, taskiq-redis, etc.)
2. Understanding your specific TaskIQ setup (broker, result backend)
3. Implementing the actual task registration and execution logic

TaskIQ Differences from Hatchet:
- No context object passed to tasks (metadata goes in message)
- Different retry/concurrency configuration
- Broker-based architecture (Redis, RabbitMQ, etc.)
- Different worker model
"""
from datetime import timedelta
from typing import Any, Callable
import functools
import uuid
import logging

from pydantic import BaseModel

from mageflow.adapters.protocols import (
    TaskManagerAdapter,
    TaskManagerType,
    TaskExecutionInfo,
    TaskContext,
    WorkflowAdapter,
    WorkerAdapter,
    TaskFunc,
)
from mageflow.adapters.registry import register_adapter
from mageflow.adapters.taskiq.context import (
    TaskIQTaskContext,
    extract_taskiq_execution_info,
    create_taskiq_task_context,
)

logger = logging.getLogger(__name__)


# Placeholder type hints - replace with actual TaskIQ imports when implementing
# from taskiq import TaskiqBroker, TaskiqTask, TaskiqResult
TaskiqBroker = Any
TaskiqTask = Any


@register_adapter(TaskManagerType.TASKIQ)
class TaskIQAdapter(TaskManagerAdapter):
    """
    TaskIQ implementation of TaskManagerAdapter.

    This adapter wraps TaskIQ's broker and provides the normalized interface
    that Mageflow uses internally.

    IMPORTANT: This is a skeleton showing the structure. Each method needs
    implementation based on your specific TaskIQ setup.
    """

    adapter_type = TaskManagerType.TASKIQ

    def __init__(
        self,
        broker: Any = None,  # TaskiqBroker
        result_backend: Any = None,
        **config,
    ):
        """
        Initialize the TaskIQ adapter.

        Args:
            broker: TaskIQ broker instance (e.g., RedisBroker)
            result_backend: Result backend for storing task results
            **config: Additional configuration options
        """
        self._broker = broker
        self._result_backend = result_backend
        self._config = config
        self._registered_tasks: dict[str, Any] = {}

        if broker is None:
            logger.warning(
                "TaskIQAdapter initialized without broker. "
                "Set broker before using the adapter."
            )

    @property
    def native_client(self) -> Any:
        """Get the native TaskIQ broker."""
        return self._broker

    def task(
        self,
        name: str | None = None,
        **options: Any,
    ) -> Callable[[TaskFunc], TaskFunc]:
        """
        Create a TaskIQ task decorator.

        TaskIQ's task registration is broker-based:
            @broker.task
            async def my_task(msg):
                ...

        This method creates a decorator that:
        1. Registers the task with the broker
        2. Wraps the function to handle Mageflow-specific logic
        """

        def decorator(func: TaskFunc) -> TaskFunc:
            task_name = name or func.__name__

            # Create the task wrapper that handles Mageflow integration
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                # Extract message (first positional arg or from kwargs)
                message = args[0] if args else kwargs.get("msg") or kwargs.get("message")

                # Generate task ID (TaskIQ might provide this differently)
                task_id = kwargs.pop("_mageflow_task_id", None) or str(uuid.uuid4())

                # Extract retry info from TaskIQ's middleware (if available)
                attempt_number = kwargs.pop("_retry_attempt", 1)

                # Create execution info and context
                execution_info = extract_taskiq_execution_info(
                    message=message,
                    task_name=task_name,
                    task_id=task_id,
                    attempt_number=attempt_number,
                )
                task_context = create_taskiq_task_context(
                    message=message,
                    task_name=task_name,
                    task_id=task_id,
                    attempt_number=attempt_number,
                )

                # Call the actual task function
                # Note: TaskIQ doesn't have a context param like Hatchet
                # If user wants context, they use @mage_client.with_ctx
                return await func(*args, **kwargs)

            # Register with TaskIQ broker if available
            if self._broker is not None:
                # TaskIQ registration (pseudo-code, adjust for actual API)
                # registered_task = self._broker.task(wrapper)
                # self._registered_tasks[task_name] = registered_task
                pass

            self._registered_tasks[task_name] = wrapper
            return wrapper

        return decorator

    def durable_task(
        self,
        name: str | None = None,
        **options: Any,
    ) -> Callable[[TaskFunc], TaskFunc]:
        """
        Create a durable task decorator.

        TaskIQ doesn't have a direct "durable task" concept like Hatchet.
        Durability is typically achieved through:
        - Broker persistence (Redis persistence, RabbitMQ durable queues)
        - Result backend configuration
        - Retry middleware

        For now, this delegates to regular task with durability hints.
        """
        options["_durable"] = True
        return self.task(name=name, **options)

    def worker(
        self,
        name: str,
        workflows: list[Any] | None = None,
        lifespan: Callable | None = None,
        **options: Any,
    ) -> WorkerAdapter:
        """
        Create a TaskIQ worker.

        TaskIQ workers are different from Hatchet:
        - Worker is typically created from broker
        - No explicit workflow registration (tasks are on broker)
        """
        return TaskIQWorkerAdapter(
            broker=self._broker,
            name=name,
            lifespan=lifespan,
            **options,
        )

    def workflow(
        self,
        name: str,
        input_validator: type[BaseModel] | None = None,
        task_ctx: dict | None = None,
        workflow_params: dict | None = None,
        return_value_field: str | None = None,
    ) -> WorkflowAdapter:
        """
        Create a workflow adapter for triggering tasks.

        In TaskIQ, "workflow" = calling a registered task.
        """
        return TaskIQWorkflowAdapter(
            broker=self._broker,
            task_name=name,
            input_validator=input_validator,
            task_ctx=task_ctx or {},
            workflow_params=workflow_params or {},
            return_value_field=return_value_field,
            registered_tasks=self._registered_tasks,
        )

    def extract_execution_info(self, raw_context: Any, message: Any) -> TaskExecutionInfo:
        """
        Extract TaskExecutionInfo from TaskIQ context.

        TaskIQ doesn't have a context object like Hatchet, so we extract
        info from the message and any available task state.
        """
        return extract_taskiq_execution_info(
            message=message,
            task_name=getattr(raw_context, "task_name", None) if raw_context else None,
            task_id=getattr(raw_context, "task_id", None) if raw_context else None,
        )

    def create_task_context(self, raw_context: Any, message: Any) -> TaskContext:
        """Create a TaskContext wrapper for TaskIQ."""
        return create_taskiq_task_context(
            message=message,
            task_state=raw_context,
        )

    def create_framework_tasks(self) -> list[Any]:
        """
        Create internal framework tasks for chain/swarm.

        TODO: Implement TaskIQ versions of chain/swarm handlers.
        """
        from mageflow.adapters.taskiq.framework_tasks import (
            create_taskiq_framework_tasks,
        )

        return create_taskiq_framework_tasks(self)

    def should_retry(
        self, execution_info: TaskExecutionInfo, exception: Exception
    ) -> bool:
        """
        Check if task should retry.

        TaskIQ retry logic depends on the retry middleware configuration.
        """
        # TaskIQ might have a NonRetryableError equivalent
        # Check for it here
        exception_name = type(exception).__name__
        if "NonRetryable" in exception_name or "NoRetry" in exception_name:
            return False
        return True


class TaskIQWorkerAdapter:
    """WorkerAdapter implementation for TaskIQ."""

    def __init__(
        self,
        broker: Any,
        name: str,
        lifespan: Callable | None = None,
        **options,
    ):
        self._broker = broker
        self._name = name
        self._lifespan = lifespan
        self._options = options

    async def async_start(self) -> None:
        """
        Start the worker asynchronously.

        TaskIQ worker startup (pseudo-code):
            from taskiq import TaskiqWorker
            worker = TaskiqWorker(broker)
            await worker.run()
        """
        if self._broker is None:
            raise RuntimeError("Cannot start worker: broker not set")

        # Run lifespan startup if provided
        if self._lifespan:
            # TaskIQ doesn't have built-in lifespan, so we manage it
            # This is a simplification - real impl needs proper context manager handling
            pass

        # Start the worker
        # In actual implementation:
        # from taskiq import TaskiqWorker
        # worker = TaskiqWorker(self._broker)
        # await worker.run()
        raise NotImplementedError(
            "TaskIQ worker startup not fully implemented. "
            "Implement based on your TaskIQ setup."
        )

    def start(self) -> None:
        """Start the worker synchronously."""
        import asyncio

        asyncio.run(self.async_start())


class TaskIQWorkflowAdapter:
    """WorkflowAdapter implementation for TaskIQ task triggering."""

    def __init__(
        self,
        broker: Any,
        task_name: str,
        input_validator: type[BaseModel] | None = None,
        task_ctx: dict | None = None,
        workflow_params: dict | None = None,
        return_value_field: str | None = None,
        registered_tasks: dict | None = None,
    ):
        self._broker = broker
        self._task_name = task_name
        self._input_validator = input_validator
        self._task_ctx = task_ctx or {}
        self._workflow_params = workflow_params or {}
        self._return_value_field = return_value_field
        self._registered_tasks = registered_tasks or {}

    def _prepare_input(self, input: Any) -> dict:
        """Prepare input for TaskIQ task."""
        if input is None:
            data = {}
        elif isinstance(input, BaseModel):
            data = input.model_dump()
        elif isinstance(input, dict):
            data = input
        else:
            data = {"value": input}

        # Merge workflow params
        data.update(self._workflow_params)

        # Inject Mageflow task context
        if self._task_ctx:
            data["_mageflow_task_data"] = self._task_ctx

        return data

    async def aio_run(
        self,
        input: Any = None,
        options: dict | None = None,
    ) -> Any:
        """
        Run the task and wait for result.

        TaskIQ task execution (pseudo-code):
            task = broker.get_task(task_name)
            result = await task.kiq(**kwargs)
            return await result.wait_result()
        """
        data = self._prepare_input(input)

        # In actual implementation:
        # task = self._registered_tasks.get(self._task_name)
        # if task:
        #     result = await task.kiq(**data)
        #     return await result.wait_result()
        raise NotImplementedError(
            "TaskIQ task execution not fully implemented. "
            "Implement based on your TaskIQ setup."
        )

    async def aio_run_no_wait(
        self,
        input: Any = None,
        options: dict | None = None,
    ) -> Any:
        """
        Trigger the task without waiting for result.

        TaskIQ fire-and-forget (pseudo-code):
            task = broker.get_task(task_name)
            return await task.kiq(**kwargs)
        """
        data = self._prepare_input(input)

        # In actual implementation:
        # task = self._registered_tasks.get(self._task_name)
        # if task:
        #     return await task.kiq(**data)
        raise NotImplementedError(
            "TaskIQ task triggering not fully implemented. "
            "Implement based on your TaskIQ setup."
        )

    def run(
        self,
        input: Any = None,
        options: dict | None = None,
    ) -> Any:
        """Synchronously run the task and wait for result."""
        import asyncio

        return asyncio.run(self.aio_run(input, options))

    def run_no_wait(
        self,
        input: Any = None,
        options: dict | None = None,
    ) -> Any:
        """Synchronously trigger the task without waiting."""
        import asyncio

        return asyncio.run(self.aio_run_no_wait(input, options))
