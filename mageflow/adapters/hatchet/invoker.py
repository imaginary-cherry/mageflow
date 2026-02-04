"""
Hatchet-specific invoker implementation.

This module provides the Hatchet implementation of the BaseInvoker.
It handles task lifecycle management using the Hatchet adapter.
"""
import asyncio
from typing import Any

from pydantic import BaseModel

from mageflow.adapters.protocols import TaskExecutionInfo, TaskContext
from mageflow.invokers.base import BaseInvoker
from mageflow.signature.consts import TASK_ID_PARAM_NAME
from mageflow.signature.model import TaskSignature
from mageflow.signature.status import SignatureStatus


class HatchetInvokerNew(BaseInvoker):
    """
    Hatchet implementation of BaseInvoker.

    This invoker uses the adapter pattern and works with TaskExecutionInfo
    instead of directly accessing the Hatchet Context.
    """

    # Set by adapter during initialization
    adapter: "HatchetAdapter" = None

    def __init__(
        self,
        message: BaseModel,
        execution_info: TaskExecutionInfo,
        task_context: TaskContext,
    ):
        self.message = message
        self._execution_info = execution_info
        self._task_context = task_context

    @property
    def task_ctx(self) -> dict:
        """Get task context/metadata."""
        return self._execution_info.task_data

    @property
    def workflow_id(self) -> str | None:
        """Get workflow execution ID."""
        return self._execution_info.workflow_id

    async def start_task(self) -> TaskSignature | None:
        """Mark task as started."""
        task_id = self.task_ctx.get(TASK_ID_PARAM_NAME, None)
        if task_id:
            async with TaskSignature.alock_from_key(task_id) as signature:
                await signature.change_status(SignatureStatus.ACTIVE)
                await signature.task_status.aupdate(worker_task_id=self.workflow_id)
                return signature
        return None

    async def run_success(self, result: Any) -> bool:
        """Handle successful task completion."""
        success_publish_tasks = []
        task_id = self.task_ctx.get(TASK_ID_PARAM_NAME, None)
        if task_id:
            current_task = await TaskSignature.get_safe(task_id)
            task_success_workflows = current_task.activate_success(result)
            await current_task.done()
            success_publish_tasks.append(asyncio.create_task(task_success_workflows))

        if success_publish_tasks:
            await asyncio.gather(*success_publish_tasks)
            return True
        return False

    async def run_error(self) -> bool:
        """Handle task error."""
        error_publish_tasks = []
        task_id = self.task_ctx.get(TASK_ID_PARAM_NAME, None)
        if task_id:
            current_task = await TaskSignature.get_safe(task_id)
            task_error_workflows = current_task.activate_error(self.message)
            error_publish_tasks.append(asyncio.create_task(task_error_workflows))

        if error_publish_tasks:
            await asyncio.gather(*error_publish_tasks)
            return True
        return False

    async def remove_task(
        self, with_success: bool = True, with_error: bool = True
    ) -> TaskSignature | None:
        """Clean up task."""
        task_id = self.task_ctx.get(TASK_ID_PARAM_NAME, None)
        if task_id:
            signature = await TaskSignature.get_safe(task_id)
            if signature:
                await signature.remove(with_error, with_success)
        return None

    async def should_run_task(self) -> bool:
        """Determine if task should execute."""
        task_id = self.task_ctx.get(TASK_ID_PARAM_NAME, None)
        if task_id:
            signature = await TaskSignature.get_safe(task_id)
            if signature is None:
                return False
            should_task_run = await signature.should_run()
            if should_task_run:
                return True
            await signature.task_status.aupdate(last_status=SignatureStatus.ACTIVE)
            await signature.handle_inactive_task(self.message)
            return False
        return True

    async def wait_task(
        self, task_name: str, msg: BaseModel, validator: type[BaseModel] = None
    ):
        """Wait for another task."""
        if self.adapter is None:
            raise RuntimeError("HatchetInvokerNew.adapter not set")
        workflow = self.adapter.workflow(
            name=task_name,
            input_validator=validator,
        )
        return await workflow.aio_run(msg)
