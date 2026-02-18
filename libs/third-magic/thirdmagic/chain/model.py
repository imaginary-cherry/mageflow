import asyncio
from typing import cast, Any

import rapyer
from pydantic import field_validator, Field, BaseModel
from rapyer.fields import RapyerKey

from thirdmagic.errors import MissingSignatureError
from thirdmagic.signature.model import TaskSignature
from thirdmagic.container import ContainerTaskSignature
from thirdmagic.signature.status import SignatureStatus
from thirdmagic.utils import HAS_HATCHET

if HAS_HATCHET:
    from hatchet_sdk.clients.admin import TriggerWorkflowOptions


class ChainTaskSignature(ContainerTaskSignature):
    tasks: list[RapyerKey] = Field(default_factory=list)

    @field_validator("tasks", mode="before")
    @classmethod
    def validate_tasks(cls, v: list[TaskSignature]):
        return [cls.validate_task_key(item) for item in v]

    @property
    def task_ids(self):
        return self.tasks

    async def on_sub_task_done(self, sub_task: TaskSignature, results: Any):
        sub_task_idx = self.tasks.index(sub_task.key)
        # If this is the last task, activate chain success callbacks
        if sub_task_idx == len(self.tasks) - 1:
            await self.ClientAdapter.acall_chain_done(results, self)
        else:
            next_task_key = self.tasks[sub_task_idx + 1]
            next_task = await rapyer.aget(next_task_key)
            next_task = cast(TaskSignature, next_task)
            await next_task.ClientAdapter.acall_signature(
                next_task, results, **self.kwargs, set_return_field=True
            )

    async def on_sub_task_error(
        self, sub_task: TaskSignature, error: Exception, original_msg: BaseModel
    ):
        await self.ClientAdapter.acall_chain_error(
            original_msg.model_dump(mode="json"), error, self, sub_task
        )

    async def sub_tasks(self) -> list[TaskSignature]:
        sub_tasks = await rapyer.afind(*self.tasks, skip_missing=True)
        return cast(list[TaskSignature], sub_tasks)

    async def acall(self, msg: Any, set_return_field: bool = True, **kwargs):
        first_task = await TaskSignature.get_safe(self.tasks[0])
        if first_task is None:
            raise MissingSignatureError(f"First task from chain {self.key} not found")

        full_kwargs = self.kwargs | kwargs
        return await first_task.acall(msg, set_return_field, **full_kwargs)

    if HAS_HATCHET:

        async def aio_run_no_wait(
            self, msg: BaseModel, options: TriggerWorkflowOptions = None, **kwargs
        ):
            return await self.acall(
                msg, options=options, set_return_field=False, **kwargs
            )

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
