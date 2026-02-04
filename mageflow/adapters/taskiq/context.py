"""
TaskIQ-specific TaskContext implementation.

This module provides the TaskContext wrapper for TaskIQ's context/state objects.
TaskIQ has a different model where task state is accessed differently than Hatchet.

NOTE: This is a skeleton implementation. TaskIQ integration requires:
1. Installing taskiq and related packages
2. Understanding TaskIQ's specific context model
3. Implementing the actual context extraction logic
"""
from dataclasses import dataclass
from datetime import timedelta
from typing import Any
import logging

from mageflow.adapters.protocols import TaskContext, TaskExecutionInfo

logger = logging.getLogger(__name__)


@dataclass
class TaskIQTaskContext:
    """
    TaskContext implementation for TaskIQ.

    TaskIQ doesn't have a context object like Hatchet. Instead, task metadata
    is typically passed through:
    1. Task labels/metadata at decoration time
    2. Message/kwargs at runtime
    3. Dependency injection

    This class normalizes TaskIQ's model to match Mageflow's TaskContext protocol.
    """

    _execution_info: TaskExecutionInfo
    _task_state: Any  # TaskIQ's task state if available

    def __init__(self, execution_info: TaskExecutionInfo, task_state: Any = None):
        self._execution_info = execution_info
        self._task_state = task_state

    @property
    def execution_info(self) -> TaskExecutionInfo:
        """Get task execution information."""
        return self._execution_info

    def log(self, message: str) -> None:
        """
        Log a message associated with this task execution.

        TaskIQ doesn't have built-in task logging like Hatchet.
        We use Python's standard logging with task context.
        """
        task_name = self._execution_info.task_name or "unknown"
        workflow_id = self._execution_info.workflow_id or "no-id"
        logger.info(f"[{task_name}:{workflow_id}] {message}")

    async def cancel(self) -> None:
        """
        Request cancellation of this task.

        TaskIQ cancellation depends on the broker being used.
        This is a placeholder that should be implemented based on
        the specific broker (Redis, RabbitMQ, etc.).
        """
        # TODO: Implement TaskIQ-specific cancellation
        # This might involve:
        # - Setting a cancellation flag in Redis
        # - Using broker-specific cancellation mechanisms
        # - Raising an exception that the task handler catches
        raise NotImplementedError(
            "TaskIQ cancellation not yet implemented. "
            "Implementation depends on the broker being used."
        )

    def refresh_timeout(self, duration: timedelta) -> None:
        """
        Extend the task execution timeout.

        TaskIQ timeout handling is different from Hatchet.
        Timeouts are typically set at task definition time.
        Runtime timeout extension may not be supported.
        """
        logger.warning(
            f"refresh_timeout called with {duration}, but TaskIQ does not "
            "support runtime timeout extension. Ignoring."
        )


def extract_taskiq_execution_info(
    message: Any,
    task_name: str | None = None,
    task_id: str | None = None,
    **kwargs,
) -> TaskExecutionInfo:
    """
    Extract TaskExecutionInfo from TaskIQ task parameters.

    TaskIQ passes metadata differently than Hatchet:
    - Task name is known at decoration time
    - Task ID may be generated or passed in message
    - Attempt number comes from retry middleware
    - Custom metadata is passed in the message itself

    Args:
        message: The message/input passed to the task
        task_name: Name of the task (from decorator)
        task_id: Unique task execution ID
        **kwargs: Additional context (retry count, etc.)

    Returns:
        Normalized TaskExecutionInfo
    """
    # In TaskIQ, task_data (signature key, etc.) is typically embedded in the message
    task_data = {}

    # Check if message is a dict or has Mageflow metadata
    if isinstance(message, dict):
        task_data = message.get("_mageflow_task_data", {})
    elif hasattr(message, "model_dump"):
        # Pydantic model - check for task data field
        msg_dict = message.model_dump()
        task_data = msg_dict.get("_mageflow_task_data", {})

    return TaskExecutionInfo(
        task_data=task_data,
        workflow_id=task_id,
        task_name=task_name,
        attempt_number=kwargs.get("attempt_number", 1),
        raw_context=kwargs.get("raw_context"),
    )


def create_taskiq_task_context(
    message: Any,
    task_name: str | None = None,
    task_id: str | None = None,
    task_state: Any = None,
    **kwargs,
) -> TaskIQTaskContext:
    """
    Create a TaskIQTaskContext for a task execution.

    Args:
        message: The message/input passed to the task
        task_name: Name of the task
        task_id: Unique task execution ID
        task_state: TaskIQ task state object (if available)
        **kwargs: Additional context

    Returns:
        TaskIQTaskContext wrapping the execution info
    """
    execution_info = extract_taskiq_execution_info(
        message=message,
        task_name=task_name,
        task_id=task_id,
        **kwargs,
    )
    return TaskIQTaskContext(execution_info, task_state)
