import asyncio
from typing import cast, Any

import rapyer
from pydantic import field_validator, Field, BaseModel

from mageflow.chain.consts import ON_CHAIN_END, ON_CHAIN_ERROR
from mageflow.chain.messages import ChainCallbackMessage, ChainErrorMessage
from mageflow.errors import MissingSignatureError
from mageflow.invokers.hatchet import HatchetInvoker
from mageflow.signature.container import ContainerTaskSignature
from mageflow.signature.model import TaskSignature, TaskIdentifierType
from mageflow.signature.status import SignatureStatus


class ChainTaskSignature(ContainerTaskSignature):
    tasks: list[TaskIdentifierType] = Field(default_factory=list)

    @field_validator("tasks", mode="before")
    @classmethod
    def validate_tasks(cls, v: list[TaskSignature]):
        return [cls.validate_task_key(item) for item in v]

    async def on_sub_task_done(self, sub_task: TaskSignature, results: Any):
        sub_task_idx = self.tasks.index(sub_task.key)
        # If this is the last task, activate chain success callbacks
        if sub_task_idx == len(self.tasks) - 1:
            chain_end_msg = ChainCallbackMessage(
                chain_results=results, chain_task_id=self.key
            )
            await HatchetInvoker.run_task(ON_CHAIN_END, chain_end_msg)
        else:
            next_task_key = self.tasks[sub_task_idx + 1]
            next_task = await rapyer.aget(next_task_key)
            next_task = cast(TaskSignature, next_task)
            await next_task.asend_callback(results, **self.kwargs)

    async def on_sub_task_error(
        self, sub_task: TaskSignature, error: Exception, original_msg: BaseModel
    ):
        chain_err_msg = ChainErrorMessage(
            chain_task_id=self.key,
            error=str(error),
            original_msg=original_msg.model_dump(mode="json"),
            error_task_key=sub_task.key,
        )
        await HatchetInvoker.run_task(ON_CHAIN_ERROR, chain_err_msg)

    async def sub_tasks(self) -> list[TaskSignature]:
        sub_tasks = await rapyer.afind(*self.tasks, skip_missing=True)
        return cast(list[TaskSignature], sub_tasks)

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
