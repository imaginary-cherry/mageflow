"""
TaskIQ backend implementation for MageFlow.

This module provides the TaskIQ-specific implementation of the BackendClient
interface, enabling MageFlow to work with TaskIQ as its task execution backend.
"""

from datetime import timedelta
from typing import Any, Callable, TypeVar, Generic
import functools
import asyncio

from pydantic import BaseModel

from mageflow.backends.base import (
    BackendClient,
    BackendType,
    TaskContext,
    WorkflowWrapper,
    WorkerWrapper,
)
from mageflow.utils.pythonic import deep_merge

TASK_DATA_PARAM_NAME = "task_data"


# Type variable for TaskIQ broker
TBroker = TypeVar("TBroker")


class TaskIQContext:
    """
    TaskIQ-specific context object.

    This class provides context information during task execution,
    similar to Hatchet's Context but for TaskIQ.
    """

    def __init__(
        self,
        task_id: str | None = None,
        task_name: str | None = None,
        attempt_number: int = 1,
        labels: dict | None = None,
        broker: Any = None,
    ):
        self.task_id = task_id
        self.task_name = task_name
        self.attempt_number = attempt_number
        self.labels = labels or {}
        self.broker = broker
        self._cancelled = False
        self._logs: list[str] = []

    @property
    def additional_metadata(self) -> dict:
        """Get labels as additional metadata."""
        return self.labels

    @property
    def workflow_id(self) -> str:
        """Get task_id as workflow_id for compatibility."""
        return self.task_id or ""

    def log(self, message: str) -> None:
        """Log a message."""
        self._logs.append(message)

    async def aio_cancel(self) -> None:
        """Mark task as cancelled."""
        self._cancelled = True

    def is_cancelled(self) -> bool:
        """Check if task is cancelled."""
        return self._cancelled


class TaskIQWorkflowWrapper:
    """
    TaskIQ-specific workflow wrapper that implements the WorkflowWrapper protocol.

    This class wraps a TaskIQ task and adds MageFlow-specific functionality
    like task context injection and parameter merging.
    """

    def __init__(
        self,
        task: Any,  # TaskIQ task
        broker: Any,  # TaskIQ broker
        workflow_params: dict | None = None,
        return_value_field: str | None = None,
        task_ctx: dict | None = None,
        input_validator: type[BaseModel] | None = None,
    ):
        self._task = task
        self._broker = broker
        self._mageflow_workflow_params = workflow_params or {}
        self._return_value_field = return_value_field
        self._task_ctx = task_ctx or {}
        self._input_validator = input_validator

    def _prepare_input(self, input: Any) -> dict:
        """Prepare input by merging with workflow params."""
        if isinstance(input, BaseModel):
            input_dict = input.model_dump(mode="json")
        elif isinstance(input, dict):
            input_dict = input
        else:
            input_dict = {}

        result = deep_merge(input_dict, self._mageflow_workflow_params)

        if self._return_value_field and input:
            result = {self._return_value_field: input_dict, **self._mageflow_workflow_params}

        return result

    def _prepare_labels(self) -> dict:
        """Prepare labels including task context."""
        labels = {}
        if self._task_ctx:
            labels[TASK_DATA_PARAM_NAME] = self._task_ctx
        return labels

    async def aio_run_no_wait(self, input: Any = None, options: dict | None = None) -> Any:
        """Execute task without waiting for completion."""
        prepared_input = self._prepare_input(input)
        labels = self._prepare_labels()

        # TaskIQ kiq (kick) method to enqueue task
        if hasattr(self._task, "kiq"):
            return await self._task.kiq(**prepared_input, labels=labels)
        elif hasattr(self._task, "kicker"):
            kicker = self._task.kicker()
            if labels:
                kicker = kicker.with_labels(**labels)
            return await kicker.kiq(**prepared_input)
        else:
            # Fallback: direct call
            return await self._task(**prepared_input)

    async def aio_run(self, input: Any = None, options: dict | None = None) -> Any:
        """Execute task and wait for completion."""
        result = await self.aio_run_no_wait(input, options)

        # Wait for result if it's a TaskiqResult
        if hasattr(result, "wait_result"):
            return await result.wait_result()
        return result

    def run_no_wait(self, input: Any = None, options: dict | None = None) -> Any:
        """Synchronously trigger task without waiting."""
        return asyncio.get_event_loop().run_until_complete(
            self.aio_run_no_wait(input, options)
        )

    def run(self, input: Any = None, options: dict | None = None) -> Any:
        """Synchronously trigger task and wait for completion."""
        return asyncio.get_event_loop().run_until_complete(self.aio_run(input, options))


class TaskIQWorkerWrapper:
    """
    TaskIQ-specific worker wrapper that implements the WorkerWrapper protocol.
    """

    def __init__(self, broker: Any, tasks: list[Any] | None = None):
        self._broker = broker
        self._tasks = tasks or []
        self._running = False

    async def start(self) -> None:
        """Start the worker."""
        self._running = True
        # TaskIQ broker startup
        if hasattr(self._broker, "startup"):
            await self._broker.startup()

    async def stop(self) -> None:
        """Stop the worker."""
        self._running = False
        # TaskIQ broker shutdown
        if hasattr(self._broker, "shutdown"):
            await self._broker.shutdown()


class TaskIQBackend(BackendClient[Any]):
    """
    TaskIQ backend implementation for MageFlow.

    This class implements the BackendClient interface for TaskIQ,
    providing all necessary operations for task orchestration.
    """

    backend_type = BackendType.TASKIQ

    def __init__(self, broker: Any):
        """
        Initialize the TaskIQ backend.

        Args:
            broker: TaskIQ broker instance (e.g., InMemoryBroker, RedisBroker)
        """
        super().__init__(broker)
        self._registered_tasks: dict[str, Any] = {}

    @property
    def broker(self) -> Any:
        """Access the underlying TaskIQ broker."""
        return self._native_client

    def create_workflow(
        self,
        name: str,
        input_validator: type[BaseModel] | None = None,
        workflow_params: dict | None = None,
        return_value_field: str | None = None,
        task_ctx: dict | None = None,
    ) -> WorkflowWrapper:
        """Create a TaskIQ workflow wrapper."""
        task = self._registered_tasks.get(name)

        if task is None:
            # Create a placeholder task if not registered
            @self._native_client.task(task_name=name)
            async def placeholder_task(**kwargs):
                raise RuntimeError(f"Task '{name}' not properly registered")

            task = placeholder_task

        return TaskIQWorkflowWrapper(
            task=task,
            broker=self._native_client,
            workflow_params=workflow_params,
            return_value_field=return_value_field,
            task_ctx=task_ctx,
            input_validator=input_validator,
        )

    def create_task_decorator(
        self,
        name: str | None = None,
        input_validator: type[BaseModel] | None = None,
        retries: int = 0,
        **kwargs,
    ) -> Callable:
        """Create a TaskIQ task decorator."""

        def decorator(func: Callable) -> Any:
            task_name = name or func.__name__

            # Store input validator for later use
            func.__mageflow_input_validator__ = input_validator
            func.__mageflow_retries__ = retries

            # Create TaskIQ task
            if hasattr(self._native_client, "task"):
                # Standard TaskIQ broker
                taskiq_decorator = self._native_client.task(
                    task_name=task_name,
                    retry_on_error=retries > 0,
                    max_retries=retries,
                    **kwargs,
                )
                task = taskiq_decorator(func)
            else:
                # Fallback for custom brokers
                task = func
                task.name = task_name

            # Register task for workflow creation
            self._registered_tasks[task_name] = task
            task.__mageflow_task_name__ = task_name

            return task

        return decorator

    def create_durable_task_decorator(
        self,
        name: str | None = None,
        input_validator: type[BaseModel] | None = None,
        retries: int = 0,
        **kwargs,
    ) -> Callable:
        """
        Create a durable task decorator for TaskIQ.

        In TaskIQ, durable tasks are handled similarly to regular tasks
        but with different retry/persistence settings.
        """
        # TaskIQ doesn't have a direct "durable" concept like Hatchet
        # We simulate it with higher retries and different scheduling
        return self.create_task_decorator(
            name=name,
            input_validator=input_validator,
            retries=max(retries, 3),  # Ensure at least 3 retries for durability
            **kwargs,
        )

    def create_worker(
        self,
        workflows: list[Any] | None = None,
        lifespan: Callable | None = None,
        **kwargs,
    ) -> WorkerWrapper:
        """Create a TaskIQ worker."""
        return TaskIQWorkerWrapper(broker=self._native_client, tasks=workflows)

    def create_task_context(self, message: BaseModel, raw_ctx: Any) -> TaskContext:
        """Create a unified TaskContext from TaskIQ context."""
        if isinstance(raw_ctx, TaskIQContext):
            task_data = raw_ctx.labels.get(TASK_DATA_PARAM_NAME, {})
            return TaskContext(
                task_id=task_data.get("task_id"),
                workflow_id=raw_ctx.task_id,
                attempt_number=raw_ctx.attempt_number,
                additional_metadata=task_data,
                raw_context=raw_ctx,
            )
        elif hasattr(raw_ctx, "message"):
            # TaskIQ TaskiqMessage context
            labels = getattr(raw_ctx.message, "labels", {}) or {}
            task_data = labels.get(TASK_DATA_PARAM_NAME, {})
            return TaskContext(
                task_id=task_data.get("task_id"),
                workflow_id=getattr(raw_ctx.message, "task_id", None),
                attempt_number=getattr(raw_ctx, "attempt", 1),
                additional_metadata=task_data,
                raw_context=raw_ctx,
            )
        else:
            # Fallback for unknown context types
            return TaskContext(
                task_id=None,
                workflow_id=None,
                attempt_number=1,
                additional_metadata={},
                raw_context=raw_ctx,
            )

    def extract_task_data(self, ctx: TaskContext) -> dict:
        """Extract MageFlow task data from the context."""
        return ctx.additional_metadata

    async def cancel_task(self, ctx: TaskContext) -> None:
        """Cancel the current task execution."""
        if ctx.raw_context and hasattr(ctx.raw_context, "aio_cancel"):
            await ctx.raw_context.aio_cancel()
        elif ctx.raw_context and isinstance(ctx.raw_context, TaskIQContext):
            await ctx.raw_context.aio_cancel()

    def get_job_name(self, ctx: TaskContext) -> str:
        """Get the job name from TaskIQ context."""
        if ctx.raw_context:
            if hasattr(ctx.raw_context, "message") and hasattr(
                ctx.raw_context.message, "task_name"
            ):
                return ctx.raw_context.message.task_name
            if hasattr(ctx.raw_context, "task_name"):
                return ctx.raw_context.task_name
        return ""

    def log(self, ctx: TaskContext, message: str) -> None:
        """Log a message."""
        if ctx.raw_context and hasattr(ctx.raw_context, "log"):
            ctx.raw_context.log(message)
        else:
            # Fallback to standard logging
            import logging

            logging.getLogger("mageflow.taskiq").info(message)

    def refresh_timeout(self, ctx: TaskContext, seconds: float) -> None:
        """
        Refresh the task timeout.

        TaskIQ doesn't have native timeout refresh, but we can track it.
        """
        # TaskIQ doesn't support runtime timeout refresh
        # This is a no-op but keeps the interface consistent
        pass

    def init_mageflow_tasks(self) -> list[Any]:
        """Initialize MageFlow internal tasks for TaskIQ."""
        from mageflow.callbacks import register_task
        from mageflow.chain.consts import ON_CHAIN_END, ON_CHAIN_ERROR
        from mageflow.chain.messages import ChainSuccessTaskCommandMessage
        from mageflow.chain.workflows import chain_end_task, chain_error_task
        from mageflow.swarm.consts import ON_SWARM_ERROR, ON_SWARM_END, ON_SWARM_START
        from mageflow.swarm.messages import SwarmResultsMessage
        from mageflow.swarm.workflows import (
            swarm_item_failed,
            swarm_item_done,
            swarm_start_tasks,
        )

        registered_tasks = []

        # Chain tasks
        chain_done_decorator = self.create_task_decorator(
            name=ON_CHAIN_END,
            input_validator=ChainSuccessTaskCommandMessage,
            retries=3,
        )
        chain_error_decorator = self.create_task_decorator(
            name=ON_CHAIN_ERROR,
            retries=3,
        )
        chain_done_task_impl = chain_done_decorator(chain_end_task)
        chain_error_task_impl = chain_error_decorator(chain_error_task)
        register_task(ON_CHAIN_END)(chain_done_task_impl)
        register_task(ON_CHAIN_ERROR)(chain_error_task_impl)
        registered_tasks.extend([chain_done_task_impl, chain_error_task_impl])

        # Swarm tasks
        swarm_start_decorator = self.create_task_decorator(
            name=ON_SWARM_START,
            retries=3,
        )
        swarm_done_decorator = self.create_task_decorator(
            name=ON_SWARM_END,
            input_validator=SwarmResultsMessage,
            retries=3,
        )
        swarm_error_decorator = self.create_task_decorator(
            name=ON_SWARM_ERROR,
            retries=3,
        )
        swarm_start_impl = swarm_start_decorator(swarm_start_tasks)
        swarm_done_impl = swarm_done_decorator(swarm_item_done)
        swarm_error_impl = swarm_error_decorator(swarm_item_failed)
        register_task(ON_SWARM_START)(swarm_start_impl)
        register_task(ON_SWARM_END)(swarm_done_impl)
        register_task(ON_SWARM_ERROR)(swarm_error_impl)
        registered_tasks.extend([swarm_start_impl, swarm_done_impl, swarm_error_impl])

        return registered_tasks
