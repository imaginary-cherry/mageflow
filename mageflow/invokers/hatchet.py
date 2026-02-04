from typing import Optional

from hatchet_sdk import Context, Hatchet
from hatchet_sdk.runnables.contextvars import ctx_additional_metadata
from pydantic import BaseModel

from mageflow.invokers.base import BaseInvoker
from mageflow.signature.consts import TASK_ID_PARAM_NAME
from mageflow.signature.model import TaskSignature
from mageflow.signature.status import SignatureStatus
from mageflow.workflows import TASK_DATA_PARAM_NAME


class HatchetInvoker(BaseInvoker):
    # TODO - This should be in init, and the entire class created via factory in mageflow_config
    client: Hatchet = None

    def __init__(self, message: BaseModel, task_data: dict, workflow_id: Optional[str]):
        self.message = message
        self.task_data = task_data
        self.workflow_id = workflow_id

    @classmethod
    def from_task_data(cls, message: BaseModel, ctx: Context) -> "HatchetInvoker":
        task_data = ctx.additional_metadata.get(TASK_DATA_PARAM_NAME, {})
        hatchet_ctx_metadata = ctx_additional_metadata.get() or {}
        hatchet_ctx_metadata.pop(TASK_DATA_PARAM_NAME, None)
        ctx_additional_metadata.set(hatchet_ctx_metadata)
        return cls(message, task_data, ctx.workflow_id)

    @classmethod
    def from_no_task(cls, message: BaseModel, task_id: str) -> "HatchetInvoker":
        task_data = {TASK_ID_PARAM_NAME: task_id}
        return cls(message, task_data, None)

    async def task_signature(self) -> Optional[TaskSignature]:
        if self.task_id:
            return await TaskSignature.get_safe(self.task_id)
        return None

    @property
    def task_id(self) -> str | None:
        return self.task_data.get(TASK_ID_PARAM_NAME, None)

    def is_vanilla_run(self):
        return self.task_id is None

    async def start_task(self) -> TaskSignature | None:
        task_id = self.task_id
        if task_id:
            async with TaskSignature.alock_from_key(task_id) as signature:
                await signature.change_status(SignatureStatus.ACTIVE)
                await signature.task_status.aupdate(worker_task_id=self.workflow_id)
                return signature
        return None

    @classmethod
    async def wait_task(
        cls,
        task_name: str,
        msg: BaseModel,
        validator: type[BaseModel] = None,
        **request_kwargs,
    ):
        validator = validator or type(msg)
        wf = cls.client.workflow(name=task_name, input_validator=validator)
        return await wf.aio_run(msg, **request_kwargs)

    @classmethod
    async def run_task(
        cls,
        task_name: str,
        msg: BaseModel,
        validator: type[BaseModel] = None,
        **request_kwargs,
    ):
        validator = validator or type(msg)
        wf = cls.client.workflow(name=task_name, input_validator=validator)
        return await wf.aio_run_no_wait(
            msg,
            **request_kwargs,
        )
