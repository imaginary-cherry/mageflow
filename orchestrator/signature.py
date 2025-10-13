import asyncio
import dataclasses
from datetime import datetime
from enum import Enum
from typing import Optional, Annotated, Callable, Self, TypeAlias

from hatchet_sdk import Hatchet
from hatchet_sdk.runnables.workflow import BaseWorkflow, Workflow
from pydantic import (
    BeforeValidator,
    PlainSerializer,
    BaseModel,
    field_validator,
    ConfigDict,
    Field,
)
from redis.asyncio.client import Redis

from orchestrator.hatchet.config import orchestrator_config
from orchestrator.hatchet.redis import RedisModel
from orchestrator.hatchet.register import load_name, load_validator
from orchestrator.hatchet.utils import serialize_model_validator, parse_model_validator
from orchestrator.hatchet.workflows import OrchestratorWorkflow
from orchestrator.utils.models import get_marked_fields

TaskIdentifierType = str
HatchetTaskType = BaseWorkflow | Callable


class SignatureStatus(str, Enum):
    ACTIVE = "active"
    STOPPED = "stopped"
    CANCELED = "canceled"


@dataclasses.dataclass
class ReturnValue:
    pass


def validate_task_id(v):
    if isinstance(v, bytes):
        return v.decode()
    if isinstance(v, TaskIdentifierType):
        return v
    elif isinstance(v, TaskSignature):
        return v.id
    else:
        raise ValueError(f"Expected task ID or TaskSignature, got {type(v).__name__}")


class TaskSignature(RedisModel):
    task_name: str
    kwargs: dict = Field(default_factory=dict)
    workflow_params: dict = Field(default_factory=dict)
    creation_time: datetime = Field(default_factory=datetime.now)
    model_validators: Annotated[
        Optional[type[BaseModel]],
        BeforeValidator(parse_model_validator),
        PlainSerializer(serialize_model_validator, return_type=str),
    ] = None
    success_callbacks: list[TaskIdentifierType] = Field(default_factory=list)
    error_callbacks: list[TaskIdentifierType] = Field(default_factory=list)
    status: SignatureStatus = SignatureStatus.ACTIVE

    model_config = ConfigDict(validate_assignment=True)

    @property
    def id(self) -> str:
        return f"{self.__class__.__name__}:{self.key}"

    @field_validator("success_callbacks", "error_callbacks", mode="before")
    @classmethod
    def validate_tasks_id(cls, v: list):
        return [validate_task_id(item) for item in v]

    @classmethod
    async def from_task(
        cls,
        task: HatchetTaskType,
        workflow_params: dict = None,
        success_callbacks: list[TaskIdentifierType | Self] = None,
        error_callbacks: list[TaskIdentifierType | Self] = None,
        **kwargs,
    ) -> Self:
        signature = cls(
            task_name=task.name,
            kwargs=kwargs,
            model_validators=task.input_validator,
            success_callbacks=success_callbacks or [],
            error_callbacks=error_callbacks or [],
            workflow_params=workflow_params or {},
        )
        await signature.save()
        return signature

    @classmethod
    def from_signature(cls, signature: Self) -> Self:
        signature_data = signature.model_dump(exclude={"pk"})
        return cls(**signature_data)

    @classmethod
    async def from_id(cls, task_id: TaskIdentifierType) -> Self:
        signature_class, pk = extract_class_and_id(task_id)
        return await signature_class.get(pk)

    @classmethod
    async def from_task_name(
        cls, task_name: str, input_validator: type[BaseModel] = None, **kwargs
    ) -> Self:
        if not input_validator:
            input_validator = await load_validator(
                orchestrator_config.redis_client, task_name
            )

        return await _signature_from_task_name(
            cls,
            task_name,
            input_validator=input_validator,
            **kwargs,
        )

    @classmethod
    async def delete_signature(cls, task_id: TaskIdentifierType):
        result = await orchestrator_config.redis_client.remove(task_id)
        return result

    async def add_callbacks(
        self, success: list[Self] = None, errors: list[Self] = None
    ) -> bool:
        all_success = self.success_callbacks
        all_errors = self.error_callbacks

        if success:
            success = [validate_task_id(s) for s in success]
            success_ids = [signature for signature in success]
            all_success.extend(success_ids)
        if errors:
            errors = [validate_task_id(e) for e in errors]
            error_ids = [signature for signature in errors]
            all_errors.extend(error_ids)
        return await self.update(
            success_callbacks=all_success, error_callbacks=all_errors
        )

    async def workflow(self, **task_additional_params):
        return await create_workflow_from_signature(
            orchestrator_config.hatchet_client,
            orchestrator_config.redis_client,
            self,
            **task_additional_params,
        )

    async def aio_run_no_wait(self, msg: BaseModel, **kwargs):
        workflow = await self.workflow(use_return_field=False)
        return await workflow.aio_run_no_wait(msg, **kwargs)

    async def callback_workflows(
        self, with_success: bool = True, with_error: bool = True, **kwargs
    ) -> list[Workflow]:
        callback_ids = []
        if with_success:
            callback_ids.extend(self.success_callbacks)
        if with_error:
            callback_ids.extend(self.error_callbacks)
        callbacks_signatures = await asyncio.gather(
            *[TaskSignature.from_id(callback_id) for callback_id in callback_ids]
        )
        workflows = await asyncio.gather(
            *[callback.workflow(**kwargs) for callback in callbacks_signatures]
        )
        return workflows

    async def activate_callbacks(
        self, msg, with_success: bool = True, with_error: bool = True, **kwargs
    ):
        workflows = await self.callback_workflows(with_success, with_error, **kwargs)
        await asyncio.gather(*[workflow.aio_run_no_wait(msg) for workflow in workflows])

    async def activate_success(self, msg, **kwargs):
        return await self.activate_callbacks(
            msg, with_success=True, with_error=False, **kwargs
        )

    async def activate_error(self, msg, **kwargs):
        return await self.activate_callbacks(
            msg,
            with_success=False,
            with_error=True,
            use_return_field=False,
            **kwargs,
        )

    async def remove(self, with_error: bool = True, with_success: bool = True):
        return await self._remove(with_error, with_success)

    async def _remove(self, with_error: bool = True, with_success: bool = True):
        addition_tasks_to_delete = []
        if with_error:
            addition_tasks_to_delete.extend(
                [error_id for error_id in self.error_callbacks]
            )
        if with_success:
            addition_tasks_to_delete.extend(
                [success_id for success_id in self.success_callbacks]
            )

        signatures_to_delete = await asyncio.gather(
            *[TaskSignature.from_id(task_id) for task_id in addition_tasks_to_delete]
        )

        delete_tasks = [self.delete()]
        delete_tasks.extend(
            [
                signature_to_delete.remove()
                for signature_to_delete in signatures_to_delete
            ]
        )

        return await asyncio.gather(*delete_tasks)

    async def handle_inactive_task(self, msg: BaseModel):
        if self.status == SignatureStatus.STOPPED:
            await self.on_stop_signature(msg)
        if self.status == SignatureStatus.CANCELED:
            await self.on_cancel_signature(msg)

    async def should_run(self):
        return self.status == SignatureStatus.ACTIVE

    async def change_status(self, status: SignatureStatus) -> bool:
        return await self.update_from_id(self.key, status=status)

    # When stopping signature from outside the task
    @classmethod
    async def de_change_status(
        cls, task_id: TaskIdentifierType, status: SignatureStatus
    ) -> bool:
        task = await cls.from_id(task_id)
        return await task.change_status(status)

    async def on_stop_signature(self, msg: BaseModel):
        self.kwargs |= msg.model_dump()
        await self.save()

    async def on_cancel_signature(self, msg: BaseModel):
        await self.remove()


SIGNATURES_NAME_MAPPING: dict[str, type[TaskSignature]] = {}


async def _signature_from_task_name(
    signature_cls: type[TaskSignature],
    task_name: str,
    input_validator: BaseModel = None,
    success_callbacks: list[TaskIdentifierType] = None,
    error_callbacks: list[TaskIdentifierType] = None,
    **kwargs,
) -> TaskSignature:
    signature = signature_cls(
        task_name=task_name,
        kwargs=kwargs,
        model_validators=input_validator,
        success_callbacks=success_callbacks or [],
        error_callbacks=error_callbacks or [],
    )
    await signature.save()
    return signature


async def create_workflow(
    hatchet: Hatchet,
    redis: Redis,
    task: str,
    input_validators: type[BaseModel],
    kwargs,
    use_return_field: bool = True,
) -> Workflow:
    task = await load_name(redis, task)

    return_field = "results" if use_return_field else None
    if input_validators and return_field:
        return_value_fields = get_marked_fields(input_validators, ReturnValue)
        if return_value_fields:
            return_field = return_value_fields[0][1]

    workflow = hatchet.workflow(name=task, input_validator=input_validators)
    orc_workflow = OrchestratorWorkflow(
        workflow, workflow_params=kwargs, return_value_field=return_field
    )
    return orc_workflow


async def create_workflow_from_signature(
    hatchet: Hatchet,
    redis: Redis,
    signature: TaskSignature,
    use_return_field: bool = True,
    **task_additional_params,
) -> Workflow:
    input_validators = signature.model_validators
    kwargs = signature.kwargs
    total_kwargs = kwargs | task_additional_params | create_task_id_params(signature.id)
    return await create_workflow(
        hatchet,
        redis,
        signature.task_name,
        input_validators,
        total_kwargs,
        use_return_field,
    )


def create_task_id_params(task_id: TaskIdentifierType) -> dict:
    return dict(metadata=dict(task_id=task_id))


TaskSignatureConvertible: TypeAlias = (
    TaskIdentifierType | TaskSignature | HatchetTaskType
)


async def resolve_signature_id(task: TaskSignatureConvertible) -> TaskSignature:
    if isinstance(task, TaskSignature):
        return task
    elif isinstance(task, TaskIdentifierType):
        return await TaskSignature.from_id(task)
    else:
        return await TaskSignature.from_task(task)


def extract_class_and_id(
    task_id: TaskIdentifierType,
) -> tuple[type[TaskSignature], str]:
    class_name, pk = task_id.split(":", 1)
    signature_class = SIGNATURES_NAME_MAPPING.get(class_name, TaskSignature)
    return signature_class, pk


async def sign(task: str | HatchetTaskType, **kwargs):
    if isinstance(task, str):
        return await TaskSignature.from_task_name(task, **kwargs)
    else:
        return await TaskSignature.from_task(task, **kwargs)


async def load_signature(task_id: TaskIdentifierType) -> TaskSignature:
    return await TaskSignature.from_id(task_id)
