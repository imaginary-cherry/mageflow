import asyncio
from typing import Optional, Any

from pydantic import BaseModel, Field

from orchestrator.hatchet.signature import TaskIdentifierType, TaskSignature


class ContextTaskMessage(BaseModel):
    context: dict


class CommandTaskMetadata(BaseModel):
    # This contain more data on the current task
    task_id: Optional[TaskIdentifierType] = None

    async def run_success(
        self, result: Optional[Any], orig_msg: ContextTaskMessage
    ) -> bool:
        success_publish_tasks = []
        if self.task_id:
            current_task = await TaskSignature.from_id(self.task_id)
            task_success_workflows = current_task.activate_success(
                result, context=orig_msg.context
            )
            success_publish_tasks.append(asyncio.create_task(task_success_workflows))

        if success_publish_tasks:
            await asyncio.gather(*success_publish_tasks)
            return True
        return False

    async def run_error(self, msg: BaseModel):
        error_publish_tasks = []
        if self.task_id:
            current_task = await TaskSignature.from_id(self.task_id)
            task_error_workflows = current_task.activate_error(msg, context=msg.context)
            error_publish_tasks.append(asyncio.create_task(task_error_workflows))

        if error_publish_tasks:
            await asyncio.gather(*error_publish_tasks)
            return True
        return False

    async def remove_task(
        self, with_success: bool = True, with_error: bool = True
    ) -> TaskSignature | None:
        if self.task_id:
            signature = await TaskSignature.from_id(self.task_id)
            await signature.remove(with_error, with_success)


class CommandTaskMessage(ContextTaskMessage):
    metadata: CommandTaskMetadata = Field(default_factory=CommandTaskMetadata)
