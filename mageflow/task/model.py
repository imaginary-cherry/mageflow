from typing import Optional, Self

from pydantic import BaseModel
from rapyer import AtomicRedisModel
from rapyer.errors.base import KeyNotFound
from rapyer.fields import Key


class MageflowTaskModel(AtomicRedisModel):
    mageflow_task_name: Key[str]
    task_name: str
    input_validator: Optional[type[BaseModel]] = None
    retries: Optional[int] = None

    @classmethod
    async def safe_get(cls, key: str) -> Self | None:
        try:
            return await cls.aget(key)
        except KeyNotFound:
            return None

    def should_retry(self, attempt_num: int, e: Exception) -> bool:
        if self.retries is not None and attempt_num < self.retries:
            return not self._is_non_retryable(e)
        return False

    @staticmethod
    def _is_non_retryable(e: Exception) -> bool:
        """Check if exception is marked as non-retryable by any client adapter."""
        # Check for the generic mageflow marker
        if getattr(e, "__mageflow_non_retryable__", False):
            return True
        # Check hatchet-specific exception if available
        try:
            from hatchet_sdk import NonRetryableException

            if isinstance(e, NonRetryableException):
                return True
        except ImportError:
            pass
        # Check temporal-specific non-retryable if available
        try:
            from temporalio.exceptions import ApplicationError

            if isinstance(e, ApplicationError) and e.non_retryable:
                return True
        except ImportError:
            pass
        return False


# Backward-compatible alias
HatchetTaskModel = MageflowTaskModel
