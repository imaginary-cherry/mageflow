import asyncio
from typing import Self, Any, Optional, cast

import rapyer
from hatchet_sdk.runnables.types import EmptyModel
from pydantic import Field, field_validator, BaseModel
from rapyer import AtomicRedisModel
from rapyer.types import RedisList, RedisInt

from mageflow.errors import (
    MissingSignatureError,
    MissingSwarmItemError,
    TooManyTasksError,
    SwarmIsCanceledError,
)
from mageflow.signature.consts import REMOVED_TASK_TTL
from mageflow.signature.container import ContainerTaskSignature
from mageflow.signature.creator import (
    TaskSignatureConvertible,
    resolve_signature_key,
)
from mageflow.signature.model import TaskSignature
from mageflow.signature.status import SignatureStatus
from mageflow.signature.types import TaskIdentifierType
from mageflow.swarm.consts import (
    BATCH_TASK_NAME_INITIALS,
    SWARM_TASK_ID_PARAM_NAME,
    SWARM_ITEM_TASK_ID_PARAM_NAME,
    ON_SWARM_END,
    ON_SWARM_ERROR,
    ON_SWARM_START,
)
from mageflow.swarm.messages import SwarmResultsMessage
from mageflow.swarm.state import PublishState
from mageflow.utils.pythonic import deep_merge


class BatchItemTaskSignature(TaskSignature):
    swarm_id: TaskIdentifierType
    original_task_id: TaskIdentifierType

    async def aio_run_no_wait(self, msg: BaseModel, **orig_task_kwargs):
        async with self.alock() as swarm_item:
            swarm_task = await SwarmTaskSignature.get_safe(self.swarm_id)
            original_task = await TaskSignature.get_safe(self.original_task_id)
            if swarm_task is None:
                raise MissingSignatureError(
                    f"Swarm {self.swarm_id} was deleted before finish"
                )
            if original_task is None:
                raise MissingSwarmItemError(
                    f"Task {self.original_task_id} was deleted before it was run in swarm"
                )
            kwargs = deep_merge(self.kwargs.clone(), original_task.kwargs.clone())
            kwargs = deep_merge(kwargs, swarm_task.kwargs.clone())
            kwargs = deep_merge(kwargs, msg.model_dump(mode="json"))
            # For tasks are just represent larger tasks (like chain)
            await original_task.aupdate_real_task_kwargs(**kwargs)
            if self.key not in swarm_task.tasks_left_to_run:
                await swarm_task.tasks_left_to_run.aappend(self.key)

            return await swarm_task.fill_running_tasks(max_tasks=1, **orig_task_kwargs)

    async def remove_references(self):
        orignal_task = await TaskSignature.get_safe(self.original_task_id)
        if orignal_task:
            await orignal_task.remove()

    async def change_status(self, status: SignatureStatus):
        return await TaskSignature.safe_change_status(self.original_task_id, status)

    async def resume(self):
        async with TaskSignature.alock_from_key(self.original_task_id) as task:
            await task.resume()
            return await super().change_status(task.task_status.last_status)

    async def suspend(self):
        await TaskSignature.suspend_from_key(self.original_task_id)
        return await super().change_status(SignatureStatus.SUSPENDED)

    async def interrupt(self):
        await TaskSignature.interrupt_from_key(self.original_task_id)
        return await super().change_status(SignatureStatus.INTERRUPTED)


class SwarmConfig(AtomicRedisModel):
    max_concurrency: int = 30
    stop_after_n_failures: Optional[int] = None
    max_task_allowed: Optional[int] = None

    def can_add_task(self, swarm: "SwarmTaskSignature") -> bool:
        if self.max_task_allowed is None:
            return True
        return len(swarm.tasks) < self.max_task_allowed


class SwarmTaskSignature(ContainerTaskSignature):
    tasks: RedisList[TaskIdentifierType] = Field(default_factory=list)
    tasks_left_to_run: RedisList[TaskIdentifierType] = Field(default_factory=list)
    finished_tasks: RedisList[TaskIdentifierType] = Field(default_factory=list)
    failed_tasks: RedisList[TaskIdentifierType] = Field(default_factory=list)
    tasks_results: RedisList[Any] = Field(default_factory=list)
    # This flag is raised when no more tasks can be added to the swarm
    is_swarm_closed: bool = False
    # How many tasks can be added to the swarm at a time
    current_running_tasks: RedisInt = 0
    publishing_state_id: str
    config: SwarmConfig = Field(default_factory=SwarmConfig)

    @field_validator(
        "tasks", "tasks_left_to_run", "finished_tasks", "failed_tasks", mode="before"
    )
    @classmethod
    def validate_tasks(cls, v):
        return [cls.validate_task_key(item) for item in v]

    async def sub_tasks(self) -> list[TaskSignature]:
        batch_items = await BatchItemTaskSignature.afind(*self.tasks)
        original_keys = [item.original_task_id for item in batch_items]
        return cast(list[TaskSignature], await rapyer.afind(*original_keys))

    @property
    def has_swarm_started(self):
        return self.current_running_tasks or self.failed_tasks or self.finished_tasks

    async def aio_run_no_wait(self, msg: BaseModel, **kwargs):
        await self.kwargs.aupdate(**msg.model_dump(mode="json", exclude_unset=True))
        workflow = await self.workflow(use_return_field=False)
        return await workflow.aio_run_no_wait(msg, **kwargs)

    async def workflow(self, use_return_field: bool = True, **task_additional_params):
        # Use on swarm start task name for wf
        task_name = self.task_name
        self.task_name = ON_SWARM_START
        additional_swarm_params = {SWARM_TASK_ID_PARAM_NAME: self.key}
        workflow = await super().workflow(
            **task_additional_params,
            **additional_swarm_params,
            use_return_field=use_return_field,
        )
        self.task_name = task_name
        return workflow

    async def change_status(self, status: SignatureStatus):
        paused_chain_tasks = [
            TaskSignature.safe_change_status(task, status) for task in self.tasks
        ]
        pause_chain = super().change_status(status)
        await asyncio.gather(pause_chain, *paused_chain_tasks, return_exceptions=True)

    async def add_task(
        self, task: TaskSignatureConvertible, close_on_max_task: bool = True
    ) -> BatchItemTaskSignature:
        """
        task - task signature to add to swarm
        close_on_max_task - if true, and you set max task allowed on swarm, this swarm will close if the task reached maximum capcity
        """
        if not self.config.can_add_task(self):
            raise TooManyTasksError(
                f"Swarm {self.task_name} has reached max tasks limit"
            )
        if self.task_status.is_canceled():
            raise SwarmIsCanceledError(
                f"Swarm {self.task_name} is {self.task_status} - can't add task"
            )
        task = await resolve_signature_key(task)
        dump = task.model_dump(exclude={"task_name"})
        batch_task_name = f"{BATCH_TASK_NAME_INITIALS}{task.task_name}"
        batch_task = BatchItemTaskSignature(
            **dump,
            task_name=batch_task_name,
            swarm_id=self.key,
            original_task_id=task.key,
        )

        swarm_identifiers = {
            SWARM_TASK_ID_PARAM_NAME: self.key,
            SWARM_ITEM_TASK_ID_PARAM_NAME: batch_task.key,
        }
        on_success_swarm_item = await TaskSignature.from_task_name(
            task_name=ON_SWARM_END,
            kwargs=swarm_identifiers,
            input_validator=SwarmResultsMessage,
        )
        on_error_swarm_item = await TaskSignature.from_task_name(
            task_name=ON_SWARM_ERROR,
            kwargs=swarm_identifiers,
        )
        task.success_callbacks.append(on_success_swarm_item.key)
        task.error_callbacks.append(on_error_swarm_item.key)
        await task.asave()
        await batch_task.asave()
        await self.tasks.aappend(batch_task.key)

        if close_on_max_task and not self.config.can_add_task(self):
            await self.close_swarm()

        return batch_task

    async def fill_running_tasks(
        self, max_tasks: Optional[int] = None, **pub_kwargs
    ) -> list[TaskSignature]:
        async with self.alock() as swarm_task:
            publish_state = await PublishState.aget(swarm_task.publishing_state_id)
            task_ids_to_run = list(publish_state.task_ids)
            num_of_task_to_run = len(task_ids_to_run)
            if not task_ids_to_run:
                resource_to_run = (
                    swarm_task.config.max_concurrency - swarm_task.current_running_tasks
                )
                if max_tasks is not None:
                    resource_to_run = min(max_tasks, resource_to_run)
                if resource_to_run <= 0:
                    return []
                num_of_task_to_run = min(
                    resource_to_run, len(swarm_task.tasks_left_to_run)
                )
                async with swarm_task.apipeline():
                    task_ids_to_run = swarm_task.tasks_left_to_run[:num_of_task_to_run]
                    publish_state.task_ids.extend(task_ids_to_run)
                    swarm_task.tasks_left_to_run.remove_range(0, num_of_task_to_run)

            if task_ids_to_run:
                tasks = await BatchItemTaskSignature.afind(*task_ids_to_run)
                original_task_ids = [
                    batch_item.original_task_id for batch_item in tasks
                ]
                original_tasks = await rapyer.afind(*original_task_ids)
                original_tasks = cast(list[TaskSignature], original_tasks)
                publish_coroutine = [
                    next_task.aio_run_no_wait(EmptyModel(), **pub_kwargs)
                    for next_task in original_tasks
                ]
                await asyncio.gather(*publish_coroutine)
                async with publish_state.apipeline():
                    publish_state.task_ids.clear()
                    swarm_task.current_running_tasks += num_of_task_to_run
                return original_tasks
            return []

    async def is_swarm_done(self):
        done_tasks = self.finished_tasks + self.failed_tasks
        finished_all_tasks = set(done_tasks) == set(self.tasks)
        return self.is_swarm_closed and finished_all_tasks

    def has_published_callback(self):
        return self.task_status.status == SignatureStatus.DONE

    def has_published_errors(self):
        return self.task_status.status == SignatureStatus.FAILED

    async def activate_error(self, msg, **kwargs):
        full_kwargs = self.kwargs | kwargs
        return await super().activate_error(msg, **full_kwargs)

    async def activate_success(self, msg, **kwargs):
        results = await self.tasks_results.aload()
        tasks_results = [res for res in results]

        await super().activate_success(tasks_results, **kwargs)
        await self.remove_branches(success=False)
        await self.remove_task()

    async def suspend(self):
        await asyncio.gather(
            *[TaskSignature.suspend_from_key(swarm_id) for swarm_id in self.tasks],
            return_exceptions=True,
        )
        await super().change_status(SignatureStatus.SUSPENDED)

    async def resume(self):
        await asyncio.gather(
            *[TaskSignature.resume_from_key(task_id) for task_id in self.tasks],
            return_exceptions=True,
        )
        await super().change_status(self.task_status.last_status)

    async def close_swarm(self) -> Self:
        async with self.alock() as swarm_task:
            await swarm_task.aupdate(is_swarm_closed=True)
            should_finish_swarm = await swarm_task.is_swarm_done()
            not_yet_published = not swarm_task.has_published_callback()
            if should_finish_swarm and not_yet_published:
                await swarm_task.activate_success(EmptyModel())
                await swarm_task.done()
        return self

    def has_swarm_failed(self):
        should_stop_after_failures = self.config.stop_after_n_failures is not None
        stop_after_n_failures = self.config.stop_after_n_failures or 0
        too_many_errors = len(self.failed_tasks) >= stop_after_n_failures
        return should_stop_after_failures and too_many_errors

    async def finish_task(self, batch_item_key: str, results: Any):
        async with self.apipeline() as swarm_task:
            # In case this was already updated
            if batch_item_key in swarm_task.finished_tasks:
                return
            swarm_task.finished_tasks.append(batch_item_key)
            swarm_task.tasks_results.append(results)
            swarm_task.current_running_tasks -= 1

    async def task_failed(self, batch_item_key: str):
        async with self.apipeline() as swarm_task:
            if batch_item_key in swarm_task.failed_tasks:
                return
            swarm_task.failed_tasks.append(batch_item_key)
            swarm_task.current_running_tasks -= 1

    async def remove_task(self):
        batch_tasks = await BatchItemTaskSignature.afind(*self.tasks)
        publish_state = await PublishState.aget(self.publishing_state_id)
        async with self.apipeline():
            # TODO - this should be removed once we use foreign key
            await publish_state.aset_ttl(REMOVED_TASK_TTL)
            for batch_task in batch_tasks:
                await batch_task.remove_task()
            return await super().remove_task()
