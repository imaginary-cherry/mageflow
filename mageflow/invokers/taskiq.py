"""
TaskIQ-specific invoker implementation for MageFlow.

This module provides the TaskIQ-specific implementation of the BaseInvoker
interface for handling task lifecycle operations.
"""

import asyncio
from typing import Any, TYPE_CHECKING

from pydantic import BaseModel

from mageflow.invokers.base import BaseInvoker
from mageflow.signature.consts import TASK_ID_PARAM_NAME
from mageflow.signature.model import TaskSignature
from mageflow.signature.status import SignatureStatus
from mageflow.backends.taskiq import TASK_DATA_PARAM_NAME

if TYPE_CHECKING:
    from mageflow.backends.base import TaskContext


class TaskIQInvoker(BaseInvoker):
    """
    TaskIQ-specific invoker implementation.

    This class handles task lifecycle operations for tasks running
    on the TaskIQ backend.
    """

    def __init__(self, message: BaseModel, ctx: "TaskContext"):
        """
        Initialize the TaskIQ invoker.

        Args:
            message: The input message for the task
            ctx: The unified TaskContext from TaskIQ backend
        """
        self.message = message
        self.ctx = ctx
        self.task_data = ctx.additional_metadata
        self.workflow_id = ctx.workflow_id

    @property
    def task_ctx(self) -> dict:
        """Get the task context data."""
        return self.task_data

    async def start_task(self) -> TaskSignature | None:
        """Mark task as started and update status."""
        task_id = self.task_data.get(TASK_ID_PARAM_NAME, None)
        if task_id:
            async with TaskSignature.lock_from_key(task_id) as signature:
                await signature.change_status(SignatureStatus.ACTIVE)
                await signature.task_status.aupdate(worker_task_id=self.workflow_id)
                return signature
        return None

    async def run_success(self, result: Any) -> bool:
        """Trigger success callbacks."""
        success_publish_tasks = []
        task_id = self.task_data.get(TASK_ID_PARAM_NAME, None)
        if task_id:
            current_task = await TaskSignature.get_safe(task_id)
            if current_task:
                task_success_workflows = current_task.activate_success(result)
                success_publish_tasks.append(asyncio.create_task(task_success_workflows))

        if success_publish_tasks:
            await asyncio.gather(*success_publish_tasks)
            return True
        return False

    async def run_error(self) -> bool:
        """Trigger error callbacks."""
        error_publish_tasks = []
        task_id = self.task_data.get(TASK_ID_PARAM_NAME, None)
        if task_id:
            current_task = await TaskSignature.get_safe(task_id)
            if current_task:
                task_error_workflows = current_task.activate_error(self.message)
                error_publish_tasks.append(asyncio.create_task(task_error_workflows))

        if error_publish_tasks:
            await asyncio.gather(*error_publish_tasks)
            return True
        return False

    async def remove_task(
        self, with_success: bool = True, with_error: bool = True
    ) -> TaskSignature | None:
        """Remove task from state store."""
        task_id = self.task_data.get(TASK_ID_PARAM_NAME, None)
        if task_id:
            signature = await TaskSignature.get_safe(task_id)
            if signature:
                await signature.remove(with_error, with_success)
                return signature
        return None

    async def should_run_task(self) -> bool:
        """Check if task should be executed based on its status."""
        task_id = self.task_data.get(TASK_ID_PARAM_NAME, None)
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
