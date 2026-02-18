from typing import Optional

import rapyer
from hatchet_sdk import Context, Hatchet
from hatchet_sdk.runnables.contextvars import ctx_additional_metadata
from pydantic import BaseModel
from rapyer.fields import RapyerKey
from thirdmagic.consts import TASK_ID_PARAM_NAME
from thirdmagic.task import TaskSignature, SignatureStatus

from mageflow.invokers.base import BaseInvoker


class HatchetInvoker(BaseInvoker):
    def __init__(
        self, message: BaseModel, task_key: RapyerKey, workflow_id: Optional[str]
    ):
        self.message = message
        self.task_key = task_key
        self.workflow_id = workflow_id

    @classmethod
    def from_task_data(cls, message: BaseModel, ctx: Context) -> "HatchetInvoker":
        task_key = ctx.additional_metadata.get(TASK_ID_PARAM_NAME, None)
        hatchet_ctx_metadata = ctx_additional_metadata.get() or {}
        hatchet_ctx_metadata.pop(TASK_ID_PARAM_NAME, None)
        ctx_additional_metadata.set(hatchet_ctx_metadata)
        task_key = RapyerKey(task_key) if task_key else None
        return cls(message, task_key, ctx.workflow_id)

    @classmethod
    def from_no_task(cls, message: BaseModel, task_id: RapyerKey) -> "HatchetInvoker":
        return cls(message, task_id, None)

    async def task_signature(self) -> Optional[TaskSignature]:
        if self.task_id:
            return await rapyer.afind_one(self.task_id)
        return None

    @property
    def task_id(self) -> RapyerKey | None:
        return self.task_key

    def is_vanilla_run(self):
        return self.task_id is None

    async def start_task(self) -> TaskSignature | None:
        task = await self.task_signature()
        if task:
            async with task.apipeline() as signature:
                await signature.change_status(SignatureStatus.ACTIVE)
                signature.worker_task_id = self.workflow_id
                return signature
        return None
