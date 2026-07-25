import asyncio
from typing import Annotated, Any, ClassVar, cast

import rapyer
from pydantic import BaseModel, Field
from rapyer.cascade import CascadeTTL
from rapyer.config import RedisConfig
from rapyer.fields import RapyerKey
from rapyer.types import Reference

from thirdmagic.container import ContainerTaskSignature, container_ttl_cascade_meta
from thirdmagic.errors import MissingSignatureError
from thirdmagic.signature.status import ContainerStatus, SignatureStatus
from thirdmagic.task.model import TaskSignature
from thirdmagic.utils import HAS_HATCHET

if HAS_HATCHET:
    from hatchet_sdk.clients.admin import TriggerWorkflowOptions


class ChainTaskSignature(ContainerTaskSignature):
    # Sub-tasks are ForeignKey edges so a write to the chain cascades TTL to them.
    tasks: Annotated[list[Reference[TaskSignature]], CascadeTTL()] = Field(
        default_factory=list
    )

    Meta: ClassVar[RedisConfig] = container_ttl_cascade_meta()

    @property
    def task_ids(self) -> list[RapyerKey]:
        return [ref.target_key for ref in self.tasks]

    async def on_sub_task_done(self, sub_task: TaskSignature, results: Any):
        task_ids = self.task_ids
        sub_task_idx = task_ids.index(sub_task.key)
        # If this is the last task, activate chain success callbacks
        if sub_task_idx == len(task_ids) - 1:
            await self.ClientAdapter.acall_chain_done(results, self)
        else:
            next_task_key = task_ids[sub_task_idx + 1]
            next_task = await rapyer.aget(next_task_key)
            next_task = cast(TaskSignature, next_task)
            await next_task.acall(results, set_return_field=True, **self.kwargs)

    async def on_sub_task_error(
        self, sub_task: TaskSignature, error: BaseException, original_msg: dict
    ):
        await self.ClientAdapter.acall_chain_error(original_msg, error, self, sub_task)

    async def sub_tasks(self) -> list[TaskSignature]:
        sub_tasks = await rapyer.afind(*self.task_ids, skip_missing=True)
        return cast(list[TaskSignature], sub_tasks)

    async def astatus(self) -> ContainerStatus:
        sub_tasks = await self.sub_tasks()
        finished = failed = running = 0
        for task in sub_tasks:
            status = task.task_status.status
            if status == SignatureStatus.DONE:
                finished += 1
            elif status == SignatureStatus.FAILED:
                failed += 1
            elif status == SignatureStatus.ACTIVE:
                running += 1
        total = len(self.tasks)
        pending = total - finished - failed - running
        return ContainerStatus.from_counts(
            signature_id=self.key,
            task_name=self.task_name,
            status=self.task_status.status,
            total=total,
            finished=finished,
            failed=failed,
            running=running,
            pending=pending,
            is_done=self.task_status.is_done(),
        )

    async def acall(self, msg: Any, set_return_field: bool = True, **kwargs):
        first_task = await rapyer.afind_one(self.task_ids[0])
        if first_task is None:
            raise MissingSignatureError(f"First task from chain {self.key} not found")

        full_kwargs = self.kwargs | kwargs
        return await first_task.acall(msg, set_return_field, **full_kwargs)

    if HAS_HATCHET:

        async def aio_run_no_wait(
            self, msg: BaseModel, options: TriggerWorkflowOptions = None
        ):
            return await self.acall(msg, options=options, set_return_field=False)

    async def change_status(self, status: SignatureStatus):
        pause_chain_tasks = [
            TaskSignature.safe_change_status(task, status) for task in self.task_ids
        ]
        pause_chain = super().change_status(status)
        await asyncio.gather(pause_chain, *pause_chain_tasks, return_exceptions=True)

    async def suspend(self):
        await asyncio.gather(
            *[TaskSignature.suspend_from_key(task_id) for task_id in self.task_ids],
            return_exceptions=True,
        )
        await super().change_status(SignatureStatus.SUSPENDED)

    async def interrupt(self):
        await asyncio.gather(
            *[TaskSignature.interrupt_from_key(task_id) for task_id in self.task_ids],
            return_exceptions=True,
        )
        await super().change_status(SignatureStatus.INTERRUPTED)

    async def resume(self):
        await asyncio.gather(
            *[TaskSignature.resume_from_key(task_key) for task_key in self.task_ids],
            return_exceptions=True,
        )
        await super().change_status(self.task_status.last_status)
