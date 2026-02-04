"""
Hatchet backend implementation.

This module provides internal implementations for Hatchet:
- HatchetTaskTrigger: Triggers tasks via Hatchet workflows
- HatchetExecutionContext: Extracts metadata from Hatchet Context
"""
from typing import Any
import logging

from hatchet_sdk import Hatchet, Context
from hatchet_sdk.runnables.contextvars import ctx_additional_metadata
from pydantic import BaseModel

from mageflow.backends.protocol import TaskTrigger, ExecutionContext
from mageflow.workflows import TASK_DATA_PARAM_NAME, MageflowWorkflow

logger = logging.getLogger(__name__)


class HatchetTaskTrigger:
    """
    Hatchet implementation of TaskTrigger.

    Uses Hatchet's workflow system to trigger tasks.
    """

    def __init__(self, hatchet_client: Hatchet):
        self._client = hatchet_client

    async def trigger(
        self,
        task_name: str,
        input_data: Any,
        task_ctx: dict,
        input_validator: type[BaseModel] | None = None,
    ) -> Any:
        """Trigger a task using Hatchet workflow."""
        workflow = self._client.workflow(
            name=task_name,
            input_validator=input_validator,
        )
        mageflow_wf = MageflowWorkflow(
            workflow,
            task_ctx=task_ctx,
        )
        return await mageflow_wf.aio_run_no_wait(input_data)


class HatchetExecutionContext:
    """
    Hatchet implementation of ExecutionContext.

    Extracts Mageflow metadata from Hatchet's Context object.
    """

    def __init__(self, ctx: Context, message: Any = None):
        self._ctx = ctx
        self._message = message
        # Extract and clean task data from additional_metadata
        self._task_data = ctx.additional_metadata.get(TASK_DATA_PARAM_NAME, {})
        # Clean up context variable (Hatchet-specific pattern)
        self._clean_context_var()

    def _clean_context_var(self):
        """Remove task data from Hatchet's context variable."""
        hatchet_ctx_metadata = ctx_additional_metadata.get() or {}
        hatchet_ctx_metadata.pop(TASK_DATA_PARAM_NAME, None)
        ctx_additional_metadata.set(hatchet_ctx_metadata)

    @property
    def task_data(self) -> dict:
        """Get Mageflow task data (signature key, etc.)."""
        return self._task_data

    @property
    def workflow_id(self) -> str | None:
        """Get Hatchet workflow execution ID."""
        return self._ctx.workflow_id

    @property
    def task_name(self) -> str | None:
        """Get current task/job name."""
        return self._ctx.action.job_name

    @property
    def attempt_number(self) -> int:
        """Get retry attempt number."""
        return self._ctx.attempt_number

    def log(self, message: str) -> None:
        """Log using Hatchet's context logger."""
        self._ctx.log(message)

    @property
    def raw_context(self) -> Context:
        """Get the underlying Hatchet Context for advanced use."""
        return self._ctx
