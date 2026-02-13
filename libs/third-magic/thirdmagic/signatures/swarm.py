import asyncio
from typing import Self, Any, Optional, cast

import rapyer
from hatchet_sdk.clients.admin import TriggerWorkflowOptions
from hatchet_sdk.runnables.types import EmptyModel
from pydantic import Field, field_validator, BaseModel
from rapyer import AtomicRedisModel
from rapyer.types import RedisList, RedisInt

from mageflow import TooManyTasksError, SwarmIsCanceledError
from mageflow.invokers.hatchet import HatchetInvoker
from mageflow import REMOVED_TASK_TTL
from mageflow.signature.container import ContainerTaskSignature
from mageflow import (
    TaskSignatureConvertible,
    resolve_signature_keys,
)
from mageflow import TaskSignature
from mageflow import SignatureStatus
from mageflow.signature.types import TaskIdentifierType
from mageflow.swarm import (
    ON_SWARM_END,
    ON_SWARM_ERROR,
    ON_SWARM_START,
)
from mageflow.swarm import (
    SwarmResultsMessage,
    SwarmErrorMessage,
    SwarmMessage,
)
from mageflow.swarm import PublishState


class SwarmConfig(AtomicRedisModel):
    max_concurrency: int = 30
    stop_after_n_failures: Optional[int] = None
    max_task_allowed: Optional[int] = None

    def can_add_task(self, swarm: "SwarmTaskSignature") -> bool:
        return self.can_add_n_tasks(swarm, 1)

    def can_add_n_tasks(self, swarm: "SwarmTaskSignature", n: int) -> bool:
        if self.max_task_allowed is None:
            return True
        return len(swarm.tasks) + n <= self.max_task_allowed


class SwarmTaskSignature(ContainerTaskSignature):
    # TODO - TASKS list should be set once we enable this in rapyer
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

    @property
    def task_ids(self):
        return self.tasks

    async def sub_tasks(self) -> list[TaskSignature]:
        tasks = await rapyer.afind(*self.tasks)
        return cast(list[TaskSignature], tasks)

    async def on_sub_task_done(self, sub_task: TaskSignature, results: Any):
        swarm_done_msg = SwarmResultsMessage(
            swarm_task_id=self.key,
            swarm_item_id=sub_task.key,
            mageflow_results=results,
        )
        await HatchetInvoker.run_task(ON_SWARM_END, swarm_done_msg)

    async def on_sub_task_error(
        self, sub_task: TaskSignature, error: Exception, original_msg: BaseModel
    ):
        swarm_error_msg = SwarmErrorMessage(
            swarm_task_id=self.key, swarm_item_id=sub_task.key, error=str(error)
        )
        await HatchetInvoker.run_task(ON_SWARM_ERROR, swarm_error_msg)

    @property
    def has_swarm_started(self):
        return self.current_running_tasks or self.failed_tasks or self.finished_tasks

    async def aio_run_no_wait(
        self, msg: BaseModel, options: TriggerWorkflowOptions = None, **kwargs
    ):
        dump = msg.model_dump(mode="json", exclude_unset=True)
        dump |= kwargs
        await self.kwargs.aupdate(**dump)
        start_swarm_msg = SwarmMessage(swarm_task_id=self.key)
        params = dict(options=options) if options else {}
        await HatchetInvoker.run_task(ON_SWARM_START, start_swarm_msg, **params)

    async def aio_run_in_swarm(
        self,
        task: TaskSignatureConvertible,
        msg: BaseModel,
        options: TriggerWorkflowOptions = None,
        close_on_max_task: bool = True,
    ) -> Optional[TaskSignature]:
        sub_task = await self.add_task(task, close_on_max_task)
        await sub_task.kwargs.aupdate(**msg.model_dump(mode="json"))
        published_tasks = await self.fill_running_tasks(max_tasks=1, options=options)
        return published_tasks[0] if published_tasks else None

    async def change_status(self, status: SignatureStatus):
        paused_chain_tasks = [
            TaskSignature.safe_change_status(task, status) for task in self.tasks
        ]
        pause_chain = super().change_status(status)
        await asyncio.gather(pause_chain, *paused_chain_tasks, return_exceptions=True)

    async def add_tasks(
        self, tasks: list[TaskSignatureConvertible], close_on_max_task: bool = True
    ) -> list[TaskSignature]:
        """
        tasks - tasks signature to add to swarm
        close_on_max_task - if true, and you set max task allowed on swarm, this swarm will close if the task reached maximum capcity
        """
        if not self.config.can_add_n_tasks(self, len(tasks)):
            raise TooManyTasksError(
                f"Swarm {self.task_name} has reached max tasks limit"
            )
        if self.task_status.is_canceled():
            raise SwarmIsCanceledError(
                f"Swarm {self.task_name} is {self.task_status} - can't add task"
            )

        tasks = await resolve_signature_keys(tasks)
        task_keys = [task.key for task in tasks]

        async with self.apipeline():
            for task in tasks:
                task.signature_container_id = self.key
            self.tasks.extend(task_keys)
            self.tasks_left_to_run.extend(task_keys)

        if close_on_max_task and not self.config.can_add_task(self):
            await self.close_swarm()

        return tasks

    async def add_task(
        self, task: TaskSignatureConvertible, close_on_max_task: bool = True
    ) -> TaskSignature:
        """
        task - task signature to add to swarm
        close_on_max_task - if true, and you set max task allowed on swarm, this swarm will close if the task reached maximum capcity
        """
        added_tasks = await self.add_tasks([task], close_on_max_task)
        return added_tasks[0]

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
                tasks = await rapyer.afind(*task_ids_to_run)
                tasks = cast(list[TaskSignature], tasks)
                full_kwargs = swarm_task.kwargs | pub_kwargs
                publish_coroutine = [
                    next_task.aio_run_no_wait(EmptyModel(), **full_kwargs)
                    for next_task in tasks
                ]
                await asyncio.gather(*publish_coroutine)
                async with publish_state.apipeline():
                    publish_state.task_ids.clear()
                    swarm_task.current_running_tasks += num_of_task_to_run
                return tasks
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

    async def finish_task(self, task_key: str, results: Any):
        async with self.apipeline() as swarm_task:
            # In case this was already updated
            if task_key in swarm_task.finished_tasks:
                return
            swarm_task.finished_tasks.append(task_key)
            swarm_task.tasks_results.append(results)
            swarm_task.current_running_tasks -= 1

    async def task_failed(self, task_key: str):
        async with self.apipeline() as swarm_task:
            if task_key in swarm_task.failed_tasks:
                return
            swarm_task.failed_tasks.append(task_key)
            swarm_task.current_running_tasks -= 1

    async def remove_task(self):
        publish_state = await PublishState.aget(self.publishing_state_id)
        async with self.apipeline():
            # TODO - this should be removed once we use foreign key
            await publish_state.aset_ttl(REMOVED_TASK_TTL)
            return await super().remove_task()
