import asyncio
from datetime import datetime
from typing import Optional, Self, Any, TypeAlias, ClassVar, cast

import rapyer
from pydantic import BaseModel, field_validator, Field
from rapyer import AtomicRedisModel
from rapyer.config import RedisConfig
from rapyer.errors.base import KeyNotFound
from rapyer.fields import SafeLoad, RapyerKey
from rapyer.types import RedisDict, RedisList, RedisDatetime

from thirdmagic.clients import BaseClientAdapter, DefaultClientAdapter
from thirdmagic.consts import REMOVED_TASK_TTL
from thirdmagic.message import DEFAULT_RESULT_NAME
from thirdmagic.signature.status import TaskStatus, PauseActionTypes, SignatureStatus
from thirdmagic.task import MageflowTaskDefinition
from thirdmagic.utils import return_value_field, HAS_HATCHET, HatchetTaskType

if HAS_HATCHET:
    from hatchet_sdk.clients.admin import TriggerWorkflowOptions


class TaskSignature(AtomicRedisModel):
    task_name: str
    kwargs: RedisDict[Any] = Field(default_factory=dict)
    creation_time: RedisDatetime = Field(default_factory=datetime.now)
    model_validators: SafeLoad[Optional[type[BaseModel]]] = None
    return_field_name: str = DEFAULT_RESULT_NAME
    success_callbacks: RedisList[RapyerKey] = Field(default_factory=list)
    error_callbacks: RedisList[RapyerKey] = Field(default_factory=list)
    task_status: TaskStatus = Field(default_factory=TaskStatus)
    signature_container_id: Optional[RapyerKey] = None

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=24 * 60 * 60, refresh_ttl=False)
    ClientAdapter: ClassVar[BaseClientAdapter] = DefaultClientAdapter()

    @field_validator("success_callbacks", "error_callbacks", mode="before")
    @classmethod
    def validate_tasks_id(cls, v: list) -> list[RapyerKey]:
        return [cls.validate_task_key(item) for item in v]

    @classmethod
    def validate_task_key(cls, v) -> RapyerKey:
        if isinstance(v, bytes):
            return RapyerKey(v.decode())
        if isinstance(v, str):
            return v
        elif isinstance(v, TaskSignature):
            return v.key
        else:
            raise ValueError(
                f"Expected task ID or TaskSignature, got {type(v).__name__}"
            )

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
    async def get_safe(cls, task_key: RapyerKey) -> Optional[Self]:
        try:
            return await rapyer.aget(task_key)
        except KeyNotFound:
            return None

    @classmethod
    async def from_task_name(
        cls, task_name: str, model_validators: type[BaseModel] = None, **kwargs
    ) -> Self:
        if not model_validators:
            task_def = await MageflowTaskDefinition.aget(task_name)
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

    if HAS_HATCHET:

        async def aio_run_no_wait(
            self, msg: BaseModel, options: TriggerWorkflowOptions = None, **kwargs
        ):
            params = dict(options=options) if options else {}
            return await self.ClientAdapter.acall_signature(
                self, msg, set_return_field=False, **params, **kwargs
            )

    async def activate_success(self, msg):
        success_signatures = await rapyer.afind(*self.success_callbacks)
        success_signatures = cast(list[TaskSignature], success_signatures)
        return await self.ClientAdapter.acall_signatures(
            success_signatures, [msg] * len(success_signatures), True
        )

    async def activate_error(self, msg):
        error_signatures = await rapyer.afind(*self.error_callbacks)
        error_signatures = cast(list[TaskSignature], error_signatures)
        return await self.ClientAdapter.acall_signatures(
            error_signatures, [msg] * len(error_signatures), True
        )

    async def remove_task(self):
        await self.aset_ttl(REMOVED_TASK_TTL)

    async def remove_branches(self, success: bool = True, errors: bool = True):
        keys_to_remove = []
        if errors:
            keys_to_remove.extend([error_id for error_id in self.error_callbacks])
        if success:
            keys_to_remove.extend([success_id for success_id in self.success_callbacks])

        signatures = cast(list[TaskSignature], await rapyer.afind(*keys_to_remove))
        await asyncio.gather(*[signature.remove() for signature in signatures])

    async def remove_references(self):
        pass

    async def remove(self, with_error: bool = True, with_success: bool = True):
        return await self._remove(with_error, with_success)

    async def _remove(self, with_error: bool = True, with_success: bool = True):
        await self.remove_branches(with_success, with_error)
        await self.remove_references()
        await self.remove_task()

    @classmethod
    async def remove_from_key(cls, task_key: RapyerKey):
        async with rapyer.alock_from_key(task_key) as task:
            task = cast(TaskSignature, task)
            return await task.remove()

    async def handle_inactive_task(self, msg: BaseModel):
        if self.task_status.status == SignatureStatus.SUSPENDED:
            await self.on_pause_signature(msg)
        elif self.task_status.status == SignatureStatus.CANCELED:
            await self.on_cancel_signature(msg)

    async def should_run(self):
        return self.task_status.should_run()

    async def change_status(self, status: SignatureStatus):
        await self.task_status.aupdate(
            last_status=self.task_status.status, status=status
        )

    # When pausing signature from outside the task
    @classmethod
    async def safe_change_status(cls, task_id: RapyerKey, status: SignatureStatus):
        try:
            async with rapyer.alock_from_key(task_id) as task:
                return await task.change_status(status)
        except Exception as e:
            return False

    async def on_pause_signature(self, msg: BaseModel):
        await self.kwargs.aupdate(**msg.model_dump(mode="json"))

    async def on_cancel_signature(self, msg: BaseModel):
        await self.remove()

    @classmethod
    async def resume_from_key(cls, task_key: RapyerKey):
        async with rapyer.alock_from_key(task_key) as task:
            task = cast(TaskSignature, task)
            await task.resume()

    async def resume(self):
        last_status = self.task_status.last_status
        if last_status == SignatureStatus.ACTIVE:
            await self.change_status(SignatureStatus.PENDING)
            await self.ClientAdapter.acall_signature(None)
        else:
            await self.change_status(last_status)

    @classmethod
    async def suspend_from_key(cls, task_key: RapyerKey):
        async with rapyer.alock_from_key(task_key) as task:
            task = cast(TaskSignature, task)
            await task.suspend()

    async def done(self):
        await self.task_status.aupdate(
            last_status=self.task_status.status, status=SignatureStatus.DONE
        )

    async def failed(self):
        await self.task_status.aupdate(
            last_status=self.task_status.status, status=SignatureStatus.FAILED
        )

    async def suspend(self):
        """
        Task suspension will try and stop the task at before it starts
        """
        await self.change_status(SignatureStatus.SUSPENDED)

    @classmethod
    async def interrupt_from_key(cls, task_key: RapyerKey):
        async with rapyer.alock_from_key(task_key) as task:
            task = cast(TaskSignature, task)
            return task.interrupt()

    async def interrupt(self):
        """
        Task interrupt will try to aggressively take hold of the async loop and stop the task
        """
        # TODO - not implemented yet - implement
        await self.suspend()

    @classmethod
    async def pause_from_key(
        cls,
        task_key: RapyerKey,
        pause_type: PauseActionTypes = PauseActionTypes.SUSPEND,
    ):
        async with rapyer.alock_from_key(task_key) as task:
            task = cast(TaskSignature, task)
            await task.pause_task(pause_type)

    async def pause_task(self, pause_type: PauseActionTypes = PauseActionTypes.SUSPEND):
        if pause_type == PauseActionTypes.SUSPEND:
            return await self.suspend()
        elif pause_type == PauseActionTypes.INTERRUPT:
            return await self.interrupt()
        raise NotImplementedError(f"Pause type {pause_type} not supported")


TaskInputType: TypeAlias = RapyerKey | TaskSignature
