"""
Task model - task manager agnostic version.

This module defines the TaskModel that stores registered task metadata
in Redis. It's used for task lookup and retry logic.
"""
from typing import Optional, Self

from pydantic import BaseModel
from rapyer import AtomicRedisModel
from rapyer.errors.base import KeyNotFound
from rapyer.fields import Key


class TaskModel(AtomicRedisModel):
    """
    Stores metadata about registered tasks.

    This model is stored in Redis and used to look up task information
    at runtime (e.g., for retry logic, input validation).

    The model is task-manager-agnostic. Each adapter is responsible for
    creating TaskModel entries when tasks are registered.
    """

    mageflow_task_name: Key[str]
    """The Mageflow task name (used for lookup)"""

    task_name: str
    """The native task name (may differ from mageflow_task_name)"""

    input_validator: Optional[type[BaseModel]] = None
    """Pydantic model for input validation (if any)"""

    retries: Optional[int] = None
    """Maximum retry attempts"""

    @classmethod
    async def safe_get(cls, key: str) -> Self | None:
        """
        Get a task model by key, returning None if not found.

        Args:
            key: The mageflow_task_name to look up

        Returns:
            TaskModel if found, None otherwise
        """
        try:
            return await cls.aget(key)
        except KeyNotFound:
            return None

    def should_retry(self, attempt_num: int, e: Exception) -> bool:
        """
        Check if a task should be retried.

        This provides the base retry logic. The adapter may have additional
        checks (e.g., NonRetryableException).

        Args:
            attempt_num: Current attempt number (1-indexed)
            e: The exception that occurred

        Returns:
            True if the task should be retried
        """
        if self.retries is None:
            return False
        return attempt_num < self.retries


# Alias for backwards compatibility
HatchetTaskModel = TaskModel
