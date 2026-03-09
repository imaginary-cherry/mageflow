from typing import Any, Optional, Self

from pydantic import BaseModel
from rapyer.fields import RapyerKey, SafeLoad

from thirdmagic.errors import UnrecognizedTaskError
from thirdmagic.message import DEFAULT_RESULT_NAME
from thirdmagic.signature import Signature
from thirdmagic.signature.status import SignatureStatus
from thirdmagic.task_def import MageflowTaskDefinition
from thirdmagic.utils import HAS_HATCHET, HatchetTaskType, return_value_field

if HAS_HATCHET:
    from hatchet_sdk.clients.admin import TriggerWorkflowOptions


class TaskSignature(Signature):
    model_validators: SafeLoad[Optional[type[BaseModel]]] = None
    return_field_name: str = DEFAULT_RESULT_NAME
    worker_task_id: str = ""

    @classmethod
    async def from_task(
        cls,
        task: HatchetTaskType,
        success_callbacks: list[RapyerKey | Self] = None,
        error_callbacks: list[RapyerKey | Self] = None,
        **kwargs,
    ) -> Self:
        validator = cls.ClientAdapter.extract_validator(task)
        return_field_name = return_value_field(validator)
        signature = cls(
            task_name=cls.ClientAdapter.task_name(task),
            model_validators=validator,
            return_field_name=return_field_name,
            success_callbacks=success_callbacks or [],
            error_callbacks=error_callbacks or [],
            **kwargs,
        )
        await signature.asave()
        return signature

    @classmethod
    async def from_task_name(
        cls, task_name: str, model_validators: type[BaseModel] = None, **kwargs
    ) -> Self:
        if not model_validators:
            task_def = await MageflowTaskDefinition.afind_one(task_name)
            if not task_def:
                raise UnrecognizedTaskError(f"Task {task_name} was not initialized")
            model_validators = task_def.input_validator
            task_name = task_def.mageflow_task_name if task_def else task_name
        return_field_name = return_value_field(model_validators)

        signature = cls(
            task_name=task_name,
            return_field_name=return_field_name,
            model_validators=model_validators,
            **kwargs,
        )
        await signature.asave()
        return signature

    async def acall(self, msg: Any, set_return_field: bool = True, **kwargs):
        return await self.ClientAdapter.acall_signature(
            self, msg, set_return_field, **kwargs
        )

    if HAS_HATCHET:

        async def aio_run_no_wait(
            self, msg: BaseModel, options: TriggerWorkflowOptions = None
        ):
            params = dict(options=options) if options else {}
            return await self.acall(msg, set_return_field=False, **params)

        async def aio_run(self, msg: BaseModel, options: TriggerWorkflowOptions = None):
            params = dict(options=options) if options else {}
            return await self.ClientAdapter.await_signature(
                self, msg, set_return_field=False, **params
            )

    async def resume(self):
        last_status = self.task_status.last_status
        if last_status == SignatureStatus.ACTIVE:
            await self.change_status(SignatureStatus.PENDING)
            await self.ClientAdapter.acall_signature(self, None, set_return_field=False)
        else:
            await self.change_status(last_status)
