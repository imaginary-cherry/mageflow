import asyncio
from typing import cast

import rapyer
from pydantic import field_validator, Field

from mageflow.errors import MissingSignatureError
from mageflow.signature.container import ContainerTaskSignature
from mageflow.signature.model import TaskSignature, TaskIdentifierType
from mageflow.signature.status import SignatureStatus


class ChainTaskSignature(ContainerTaskSignature):
    tasks: list[TaskIdentifierType] = Field(default_factory=list)

    @field_validator("tasks", mode="before")
    @classmethod
    def validate_tasks(cls, v: list[TaskSignature]):
        return [cls.validate_task_key(item) for item in v]

    @property
    async def sub_tasks(self) -> list[TaskSignature]:
        return cast(list[TaskSignature], await rapyer.afind(*self.tasks))

    async def workflow(self, **task_additional_params):
        first_task = await TaskSignature.get_safe(self.tasks[0])
        if first_task is None:
            raise MissingSignatureError(f"First task from chain {self.key} not found")
        return await first_task.workflow(**task_additional_params)

    async def aupdate_real_task_kwargs(self, **kwargs):
        first_task = await rapyer.aget(self.tasks[0])
        if not isinstance(first_task, TaskSignature):
            raise RuntimeError(f"First task from chain {self.key} must be a signature")
        return await first_task.aupdate_real_task_kwargs(**kwargs)

    async def change_status(self, status: SignatureStatus):
        pause_chain_tasks = [
            TaskSignature.safe_change_status(task, status) for task in self.tasks
        ]
        pause_chain = super().change_status(status)
        await asyncio.gather(pause_chain, *pause_chain_tasks, return_exceptions=True)

    async def suspend(self):
        await asyncio.gather(
            *[TaskSignature.suspend_from_key(task_id) for task_id in self.tasks],
            return_exceptions=True,
        )
        await super().change_status(SignatureStatus.SUSPENDED)

    async def interrupt(self):
        await asyncio.gather(
            *[TaskSignature.interrupt_from_key(task_id) for task_id in self.tasks],
            return_exceptions=True,
        )
        await super().change_status(SignatureStatus.INTERRUPTED)

    async def resume(self):
        await asyncio.gather(
            *[TaskSignature.resume_from_key(task_key) for task_key in self.tasks],
            return_exceptions=True,
        )
        await super().change_status(self.task_status.last_status)
