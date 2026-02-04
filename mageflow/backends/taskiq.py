"""
TaskIQ backend implementation.

This module provides internal implementations for TaskIQ:
- TaskIQTaskTrigger: Triggers tasks via TaskIQ's .kiq() method
- TaskIQExecutionContext: Extracts metadata from task kwargs

TaskIQ Differences from Hatchet:
- No context object passed to tasks
- Metadata passed in task kwargs (using _mageflow_task_data key)
- Uses .kiq() to trigger tasks, not workflow.run()
- No "workflow" or "durable_task" concepts
"""
from typing import Any
import logging
import uuid

from pydantic import BaseModel

from mageflow.backends.protocol import TaskTrigger, ExecutionContext

logger = logging.getLogger(__name__)

# Key for Mageflow metadata in TaskIQ kwargs
MAGEFLOW_TASK_DATA_KEY = "_mageflow_task_data"
MAGEFLOW_TASK_ID_KEY = "_mageflow_task_id"


class TaskIQTaskTrigger:
    """
    TaskIQ implementation of TaskTrigger.

    Uses TaskIQ's .kiq() method to trigger tasks.
    The broker maintains a registry of decorated tasks.
    """

    def __init__(self, broker: Any, task_registry: dict[str, Any]):
        """
        Initialize TaskIQ task trigger.

        Args:
            broker: TaskIQ broker instance
            task_registry: Dict mapping task names to decorated task objects
        """
        self._broker = broker
        self._task_registry = task_registry

    async def trigger(
        self,
        task_name: str,
        input_data: Any,
        task_ctx: dict,
        input_validator: type[BaseModel] | None = None,
    ) -> Any:
        """
        Trigger a task using TaskIQ's .kiq() method.

        Mageflow metadata is passed as a special kwarg that the
        task wrapper extracts.
        """
        task = self._task_registry.get(task_name)
        if task is None:
            raise ValueError(f"Task '{task_name}' not found in registry")

        # Prepare kwargs with Mageflow metadata
        kwargs = {}
        if isinstance(input_data, BaseModel):
            kwargs = input_data.model_dump()
        elif isinstance(input_data, dict):
            kwargs = input_data
        else:
            kwargs = {"input": input_data}

        # Inject Mageflow task context
        kwargs[MAGEFLOW_TASK_DATA_KEY] = task_ctx
        kwargs[MAGEFLOW_TASK_ID_KEY] = str(uuid.uuid4())

        # Use TaskIQ's .kiq() to queue the task
        return await task.kiq(**kwargs)


class TaskIQExecutionContext:
    """
    TaskIQ implementation of ExecutionContext.

    Extracts Mageflow metadata from task kwargs since TaskIQ
    doesn't have a context object like Hatchet.
    """

    def __init__(
        self,
        kwargs: dict,
        task_name: str | None = None,
        attempt_number: int = 1,
    ):
        """
        Initialize TaskIQ execution context.

        Args:
            kwargs: Task kwargs (contains _mageflow_task_data)
            task_name: Name of the task (from decorator)
            attempt_number: Retry attempt (from retry middleware)
        """
        self._kwargs = kwargs
        self._task_data = kwargs.pop(MAGEFLOW_TASK_DATA_KEY, {})
        self._task_id = kwargs.pop(MAGEFLOW_TASK_ID_KEY, None)
        self._task_name = task_name
        self._attempt_number = attempt_number

    @property
    def task_data(self) -> dict:
        """Get Mageflow task data (signature key, etc.)."""
        return self._task_data

    @property
    def workflow_id(self) -> str | None:
        """Get task execution ID."""
        return self._task_id

    @property
    def task_name(self) -> str | None:
        """Get current task name."""
        return self._task_name

    @property
    def attempt_number(self) -> int:
        """Get retry attempt number."""
        return self._attempt_number

    def log(self, message: str) -> None:
        """Log using standard Python logging."""
        task_id = self._task_id or "no-id"
        task_name = self._task_name or "unknown"
        logger.info(f"[{task_name}:{task_id}] {message}")

    @property
    def cleaned_kwargs(self) -> dict:
        """Get kwargs with Mageflow metadata removed."""
        return self._kwargs
