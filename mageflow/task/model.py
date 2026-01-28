"""
Task model for MageFlow.

This module provides the task metadata model used for tracking
registered tasks across all backends.
"""

from typing import Optional, Annotated, Self

from pydantic import BaseModel
from rapyer import AtomicRedisModel
from rapyer.errors.base import KeyNotFound
from rapyer.fields import Key


# Try to import Hatchet's NonRetryableException
try:
    from hatchet_sdk import NonRetryableException
    HATCHET_AVAILABLE = True
except ImportError:
    # Define a placeholder exception class when Hatchet is not installed
    class NonRetryableException(Exception):
        """Placeholder for Hatchet's NonRetryableException when not installed."""
        pass
    HATCHET_AVAILABLE = False


class TaskModel(AtomicRedisModel):
    """
    Task metadata model for tracking registered tasks.

    This model stores task metadata in Redis for runtime lookup
    of task configuration like retries and input validators.
    """

    mageflow_task_name: Annotated[str, Key()]
    task_name: str
    input_validator: Optional[type[BaseModel]] = None
    retries: Optional[int] = None

    @classmethod
    async def safe_get(cls, key: str) -> Self | None:
        """Safely get a task model, returning None if not found."""
        try:
            return await cls.get(key)
        except KeyNotFound:
            return None

    def should_retry(self, attempt_num: int, e: Exception) -> bool:
        """
        Determine if a task should be retried based on attempt number and exception.

        Args:
            attempt_num: Current attempt number (1-indexed)
            e: The exception that was raised

        Returns:
            True if the task should be retried, False otherwise
        """
        finish_retry = self.retries is not None and attempt_num < self.retries
        return finish_retry and not isinstance(e, NonRetryableException)


# Backwards compatibility alias
HatchetTaskModel = TaskModel
