"""
Minimal internal protocols for task manager backends.

These protocols define ONLY what Mageflow needs internally to work:
1. Trigger tasks by name with metadata
2. Extract execution metadata from running tasks

The user-facing API is NOT abstracted - each backend (Hatchet, TaskIQ)
exposes its native API plus Mageflow additions (sign, swarm, chain).
"""
from abc import ABC, abstractmethod
from typing import Any, Protocol, runtime_checkable
from pydantic import BaseModel


@runtime_checkable
class TaskTrigger(Protocol):
    """
    Internal protocol for triggering tasks.

    This is the ONLY abstraction Mageflow needs for task execution.
    Each backend implements this differently:
    - Hatchet: workflow.aio_run_no_wait(msg, options)
    - TaskIQ: task.kiq(*args, **kwargs)
    """

    async def trigger(
        self,
        task_name: str,
        input_data: Any,
        task_ctx: dict,
        input_validator: type[BaseModel] | None = None,
    ) -> Any:
        """
        Trigger a task by name.

        Args:
            task_name: Name of the registered task
            input_data: Input to pass to the task
            task_ctx: Mageflow context (contains signature key, etc.)
            input_validator: Optional Pydantic model for validation

        Returns:
            Task reference/handle (backend-specific)
        """
        ...


@runtime_checkable
class ExecutionContext(Protocol):
    """
    Internal protocol for accessing execution metadata from within a running task.

    Different backends provide this data differently:
    - Hatchet: ctx.additional_metadata
    - TaskIQ: From message kwargs or dependency injection
    """

    @property
    def task_data(self) -> dict:
        """Get Mageflow task data (contains signature key, etc.)"""
        ...

    @property
    def workflow_id(self) -> str | None:
        """Get unique execution ID (if available)."""
        ...

    @property
    def task_name(self) -> str | None:
        """Get current task name."""
        ...

    @property
    def attempt_number(self) -> int:
        """Get retry attempt number (1-indexed)."""
        ...

    def log(self, message: str) -> None:
        """Log a message (backend-specific implementation)."""
        ...


class BackendType:
    """Identifies the backend type."""
    HATCHET = "hatchet"
    TASKIQ = "taskiq"
