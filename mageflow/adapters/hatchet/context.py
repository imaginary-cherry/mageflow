"""
Hatchet-specific TaskContext implementation.

This module provides the TaskContext wrapper for Hatchet's Context object.
It normalizes the Hatchet context into the Mageflow TaskContext protocol.
"""
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from hatchet_sdk import Context
from hatchet_sdk.runnables.contextvars import ctx_additional_metadata

from mageflow.adapters.protocols import TaskContext, TaskExecutionInfo
from mageflow.workflows import TASK_DATA_PARAM_NAME


@dataclass
class HatchetTaskContext:
    """
    TaskContext implementation for Hatchet.

    Wraps Hatchet's Context object and provides a normalized interface
    for task operations like logging, cancellation, and timeout management.
    """

    _ctx: Context
    _execution_info: TaskExecutionInfo

    def __init__(self, ctx: Context, execution_info: TaskExecutionInfo):
        self._ctx = ctx
        self._execution_info = execution_info

    @property
    def execution_info(self) -> TaskExecutionInfo:
        """Get task execution information."""
        return self._execution_info

    def log(self, message: str) -> None:
        """Log a message associated with this task execution."""
        self._ctx.log(message)

    async def cancel(self) -> None:
        """Request cancellation of this task."""
        await self._ctx.aio_cancel()

    def refresh_timeout(self, duration: timedelta) -> None:
        """Extend the task execution timeout."""
        self._ctx.refresh_timeout(duration)

    @property
    def raw_context(self) -> Context:
        """Get the underlying Hatchet Context (for advanced use cases)."""
        return self._ctx


def extract_hatchet_execution_info(ctx: Context, message: Any) -> TaskExecutionInfo:
    """
    Extract TaskExecutionInfo from Hatchet's Context.

    This is the Hatchet-specific implementation of execution info extraction.
    It pulls data from ctx.additional_metadata and other Context properties.

    Args:
        ctx: Hatchet Context object
        message: The message/input passed to the task

    Returns:
        Normalized TaskExecutionInfo
    """
    # Extract task_data from additional_metadata
    task_data = ctx.additional_metadata.get(TASK_DATA_PARAM_NAME, {})

    # Clean up the context variable (Hatchet-specific)
    hatchet_ctx_metadata = ctx_additional_metadata.get() or {}
    hatchet_ctx_metadata.pop(TASK_DATA_PARAM_NAME, None)
    ctx_additional_metadata.set(hatchet_ctx_metadata)

    return TaskExecutionInfo(
        task_data=task_data,
        workflow_id=ctx.workflow_id,
        task_name=ctx.action.job_name,
        attempt_number=ctx.attempt_number,
        raw_context=ctx,
    )


def create_hatchet_task_context(ctx: Context, message: Any) -> HatchetTaskContext:
    """
    Create a HatchetTaskContext from a Hatchet Context.

    Args:
        ctx: Hatchet Context object
        message: The message/input passed to the task

    Returns:
        HatchetTaskContext wrapping the native context
    """
    execution_info = extract_hatchet_execution_info(ctx, message)
    return HatchetTaskContext(ctx, execution_info)
