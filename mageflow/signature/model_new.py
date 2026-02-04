"""
Task signature model - task manager agnostic version.

This module provides the TaskSignature model that tracks task execution
state in Redis. It's designed to work with any task manager adapter.
"""
import asyncio
import contextlib
from datetime import datetime
from typing import Optional, Self, Any, TypeAlias, AsyncGenerator, ClassVar, cast

import rapyer
from pydantic import (
    BaseModel,
    field_validator,
    Field,
)
from rapyer import AtomicRedisModel
from rapyer.config import RedisConfig
from rapyer.errors.base import KeyNotFound
from rapyer.fields import SafeLoad
from rapyer.types import RedisDict, RedisList, RedisDatetime
from rapyer.utils.redis import acquire_lock
from typing_extensions import deprecated

from mageflow.errors import MissingSignatureError
from mageflow.models.message import DEFAULT_RESULT_NAME
from mageflow.signature.consts import TASK_ID_PARAM_NAME, REMOVED_TASK_TTL
from mageflow.signature.status import TaskStatus, SignatureStatus, PauseActionTypes
from mageflow.signature.types import TaskIdentifierType
from mageflow.startup import mageflow_config
from mageflow.task.model_new import TaskModel
from mageflow.utils.models import return_value_field


class TaskSignature(AtomicRedisModel):
    """
    Represents a task execution signature.

    A signature is created when a task is "signed" (scheduled for execution).
    It tracks:
    - Task name and parameters
    - Execution status
    - Success/error callbacks
    - Task results
    """

    task_name: str
    kwargs: RedisDict[Any] = Field(default_factory=dict)
    creation_time: RedisDatetime = Field(default_factory=datetime.now)
    model_validators: SafeLoad[Optional[Any]] = None
    return_field_name: str = DEFAULT_RESULT_NAME
    success_callbacks: RedisList[TaskIdentifierType] = Field(default_factory=list)
    error_callbacks: RedisList[TaskIdentifierType] = Field(default_factory=list)
    task_status: TaskStatus = Field(default_factory=TaskStatus)
    task_identifiers: RedisDict[Any] = Field(default_factory=dict)

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=24 * 60 * 60, refresh_ttl=False)

    @field_validator("success_callbacks", "error_callbacks", mode="before")
    @classmethod
    def validate_tasks_id(cls, v: list) -> list[TaskIdentifierType]:
        return [cls.validate_task_key(item) for item in v]

    @classmethod
    def validate_task_key(cls, v) -> TaskIdentifierType:
        if isinstance(v, bytes):
            return v.decode()
        if isinstance(v, TaskIdentifierType):
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
        task: Any,  # Task object (adapter-specific)
        success_callbacks: list[TaskIdentifierType | Self] = None,
        error_callbacks: list[TaskIdentifierType | Self] = None,
        **kwargs,
    ) -> Self:
        """Create a signature from a task object."""
        # Get task metadata (works with any adapter's task object)
        task_name = getattr(task, "name", str(task))
        input_validator = getattr(task, "input_validator", None)
        return_field_name = return_value_field(input_validator)

        signature = cls(
            task_name=task_name,
            model_validators=input_validator,
            return_field_name=return_field_name,
            success_callbacks=success_callbacks or [],
            error_callbacks=error_callbacks or [],
            **kwargs,
        )
        await signature.asave()
        return signature

    @classmethod
    async def get_safe(cls, task_key: TaskIdentifierType) -> Optional[Self]:
        """Get a signature by key, returning None if not found."""
        try:
            return await rapyer.aget(task_key)
        except KeyNotFound:
            return None

    @classmethod
    async def from_task_name(
        cls, task_name: str, model_validators: type[BaseModel] = None, **kwargs
    ) -> Self:
        """Create a signature from a task name."""
        if not model_validators:
            task_def = await TaskModel.safe_get(task_name)
            model_validators = task_def.input_validator if task_def else None
        return_field_name = return_value_field(model_validators)

        signature = cls(
            task_name=task_name,
            return_field_name=return_field_name,
            model_validators=model_validators,
            **kwargs,
        )
        await signature.asave()
        return signature

    async def add_callbacks(
        self, success: list[Self] = None, errors: list[Self] = None
    ):
        """Add success and/or error callbacks."""
        if success:
            success = [self.validate_task_key(s) for s in success]
        if errors:
            errors = [self.validate_task_key(e) for e in errors]
        async with self.apipeline() as signature:
            await signature.success_callbacks.aextend(success)
            await signature.error_callbacks.aextend(errors)

    async def workflow(self, use_return_field: bool = True, **task_additional_params):
        """
        Get a workflow adapter for executing this task.

        Returns a WorkflowAdapter from the configured task manager adapter.
        """
        total_kwargs = self.kwargs | task_additional_params
        task_def = await TaskModel.safe_get(self.task_name)
        task = task_def.task_name if task_def else self.task_name
        return_field = self.return_field_name if use_return_field else None

        # Get workflow from the configured adapter
        adapter = mageflow_config.task_adapter
        if adapter is not None:
            return adapter.workflow(
                name=task,
                input_validator=self.model_validators,
                task_ctx=self.task_ctx(),
                workflow_params=total_kwargs,
                return_value_field=return_field,
            )

        # Fallback for backwards compatibility with Hatchet
        if mageflow_config.hatchet_client is not None:
            from mageflow.workflows import MageflowWorkflow

            workflow = mageflow_config.hatchet_client.workflow(
                name=task, input_validator=self.model_validators
            )
            mageflow_wf = MageflowWorkflow(
                workflow,
                workflow_params=total_kwargs,
                return_value_field=return_field,
                task_ctx=self.task_ctx(),
            )
            return mageflow_wf

        raise RuntimeError(
            "No task adapter configured. Call Mageflow() to initialize."
        )

    def task_ctx(self) -> dict:
        """Get the task context dictionary for passing to callbacks."""
        return self.task_identifiers | {TASK_ID_PARAM_NAME: self.key}

    async def aio_run_no_wait(self, msg: BaseModel, **kwargs):
        """Trigger the task without waiting for result."""
        workflow = await self.workflow(use_return_field=False)
        return await workflow.aio_run_no_wait(msg, **kwargs)

    async def callback_workflows(
        self, with_success: bool = True, with_error: bool = True, **kwargs
    ) -> list:
        """Get workflow adapters for callbacks."""
        callback_ids = []
        if with_success:
            callback_ids.extend(self.success_callbacks)
        if with_error:
            callback_ids.extend(self.error_callbacks)
        callbacks_signatures = await rapyer.afind(*callback_ids)
        callbacks_signatures = cast(list[TaskSignature], callbacks_signatures)

        if any([sign is None for sign in callbacks_signatures]):
            raise MissingSignatureError(
                f"Some callbacks not found {callback_ids}, signature can be called only once"
            )
        workflows = await asyncio.gather(
            *[callback.workflow(**kwargs) for callback in callbacks_signatures]
        )
        return workflows

    async def activate_callbacks(
        self, msg, with_success: bool = True, with_error: bool = True, **kwargs
    ):
        """Activate (trigger) callback tasks."""
        workflows = await self.callback_workflows(with_success, with_error, **kwargs)
        await asyncio.gather(*[workflow.aio_run_no_wait(msg) for workflow in workflows])

    async def activate_success(self, msg, **kwargs):
        """Activate success callbacks."""
        return await self.activate_callbacks(
            msg, with_success=True, with_error=False, **kwargs
        )

    async def activate_error(self, msg, **kwargs):
        """Activate error callbacks."""
        return await self.activate_callbacks(
            msg,
            with_success=False,
            with_error=True,
            use_return_field=False,
            **kwargs,
        )

    async def remove_task(self):
        """Mark task for removal (set TTL)."""
        await self.aset_ttl(REMOVED_TASK_TTL)

    async def remove_branches(self, success: bool = True, errors: bool = True):
        """Remove callback branches."""
        keys_to_remove = []
        if errors:
            keys_to_remove.extend([error_id for error_id in self.error_callbacks])
        if success:
            keys_to_remove.extend([success_id for success_id in self.success_callbacks])

        signatures = cast(list[TaskSignature], await rapyer.afind(*keys_to_remove))
        await asyncio.gather(*[signature.remove() for signature in signatures])

    async def remove_references(self):
        """Remove references (override in subclasses)."""
        pass

    async def remove(self, with_error: bool = True, with_success: bool = True):
        """Remove the signature and its branches."""
        return await self._remove(with_error, with_success)

    async def _remove(self, with_error: bool = True, with_success: bool = True):
        """Internal remove implementation."""
        await self.remove_branches(with_success, with_error)
        await self.remove_references()
        await self.remove_task()

    @classmethod
    async def remove_from_key(cls, task_key: TaskIdentifierType):
        """Remove a signature by key."""
        async with rapyer.alock_from_key(task_key) as task:
            task = cast(TaskSignature, task)
            return await task.remove()

    async def handle_inactive_task(self, msg: BaseModel):
        """Handle a task that shouldn't run (suspended, canceled)."""
        if self.task_status.status == SignatureStatus.SUSPENDED:
            await self.on_pause_signature(msg)
        elif self.task_status.status == SignatureStatus.CANCELED:
            await self.on_cancel_signature(msg)

    async def should_run(self):
        """Check if the task should run based on status."""
        return self.task_status.should_run()

    async def change_status(self, status: SignatureStatus):
        """Change the task status."""
        await self.task_status.aupdate(
            last_status=self.task_status.status, status=status
        )

    async def aupdate_real_task_kwargs(self, **kwargs):
        """Update task kwargs."""
        return await self.kwargs.aupdate(**kwargs)

    @classmethod
    async def safe_change_status(
        cls, task_id: TaskIdentifierType, status: SignatureStatus
    ):
        """Safely change status with locking."""
        try:
            async with lock_from_key(cls, task_id) as task:
                return await task.change_status(status)
        except Exception as e:
            return False

    async def on_pause_signature(self, msg: BaseModel):
        """Handle pause - save current message to kwargs."""
        await self.kwargs.aupdate(**msg.model_dump(mode="json"))

    async def on_cancel_signature(self, msg: BaseModel):
        """Handle cancel - remove the signature."""
        await self.remove()

    @classmethod
    async def resume_from_key(cls, task_key: TaskIdentifierType):
        """Resume a task by key."""
        async with lock_from_key(cls, task_key) as task:
            await task.resume()

    async def resume(self):
        """Resume a suspended task."""
        from pydantic import BaseModel

        class EmptyMsg(BaseModel):
            pass

        last_status = self.task_status.last_status
        if last_status == SignatureStatus.ACTIVE:
            await self.change_status(SignatureStatus.PENDING)
            await self.aio_run_no_wait(EmptyMsg())
        else:
            await self.change_status(last_status)

    @classmethod
    async def suspend_from_key(cls, task_key: TaskIdentifierType):
        """Suspend a task by key."""
        async with lock_from_key(cls, task_key) as task:
            await task.suspend()

    async def done(self):
        """Mark task as done."""
        await self.task_status.aupdate(
            last_status=self.task_status.status, status=SignatureStatus.DONE
        )

    async def failed(self):
        """Mark task as failed."""
        await self.task_status.aupdate(
            last_status=self.task_status.status, status=SignatureStatus.FAILED
        )

    async def suspend(self):
        """Suspend the task."""
        await self.change_status(SignatureStatus.SUSPENDED)

    @classmethod
    async def interrupt_from_key(cls, task_key: TaskIdentifierType):
        """Interrupt a task by key."""
        async with lock_from_key(cls, task_key) as task:
            return task.interrupt()

    async def interrupt(self):
        """Interrupt the task (aggressive stop)."""
        # TODO - not implemented yet - implement
        await self.suspend()

    @classmethod
    async def pause_from_key(
        cls,
        task_key: TaskIdentifierType,
        pause_type: PauseActionTypes = PauseActionTypes.SUSPEND,
    ):
        """Pause a task by key."""
        async with lock_from_key(cls, task_key) as task:
            await task.pause_task(pause_type)

    async def pause_task(self, pause_type: PauseActionTypes = PauseActionTypes.SUSPEND):
        """Pause the task."""
        if pause_type == PauseActionTypes.SUSPEND:
            return await self.suspend()
        elif pause_type == PauseActionTypes.INTERRUPT:
            return await self.interrupt()
        raise NotImplementedError(f"Pause type {pause_type} not supported")


@contextlib.asynccontextmanager
@deprecated(f"You should switch to rapyer 1.1.1 with rapyer.lock_from_key")
async def lock_from_key(
    cls, key: str, action: str = "default", save_at_end: bool = False
) -> AsyncGenerator[TaskSignature, None]:
    """Lock a signature by key."""
    async with acquire_lock(cls.Meta.redis, f"{key}/{action}"):
        redis_model = await rapyer.aget(key)
        yield redis_model
        if save_at_end:
            await redis_model.asave()


SIGNATURES_NAME_MAPPING: dict[str, type[TaskSignature]] = {}
TaskInputType: TypeAlias = TaskIdentifierType | TaskSignature
