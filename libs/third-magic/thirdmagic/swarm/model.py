import asyncio
from typing import Self, Any, Optional, cast

import rapyer
from pydantic import Field, field_validator, BaseModel
from rapyer import AtomicRedisModel
from rapyer.fields import RapyerKey
from rapyer.types import RedisList, RedisInt

from thirdmagic.consts import REMOVED_TASK_TTL
from thirdmagic.container import ContainerTaskSignature
from thirdmagic.errors import TooManyTasksError, SwarmIsCanceledError
from thirdmagic.signature import Signature
from thirdmagic.signature.status import SignatureStatus
from thirdmagic.swarm.consts import SWARM_MESSAGE_PARAM_NAME
from thirdmagic.swarm.state import PublishState
from thirdmagic.task.creator import TaskSignatureConvertible, resolve_signatures
from thirdmagic.task.model import TaskSignature
from thirdmagic.utils import HAS_HATCHET

if HAS_HATCHET:
    from hatchet_sdk.clients.admin import TriggerWorkflowOptions
    from hatchet_sdk.runnables.types import EmptyModel
    from hatchet_sdk.runnables.workflow import TaskRunRef


class SwarmConfig(AtomicRedisModel):
    max_concurrency: int = 30
    stop_after_n_failures: Optional[int] = Field(default=None, gt=0)
    max_task_allowed: Optional[int] = Field(default=None, gt=0)
    send_swarm_message_to_return_field: bool = False

    def can_add_task(self, swarm: "SwarmTaskSignature") -> bool:
        return self.can_add_n_tasks(swarm, 1)

    def can_add_n_tasks(self, swarm: "SwarmTaskSignature", n: int) -> bool:
        if self.max_task_allowed is None:
            return True
        return len(swarm.tasks) + n <= self.max_task_allowed


class SwarmTaskSignature(ContainerTaskSignature):
    # TODO - TASKS list should be set once we enable this in rapyer
    tasks: RedisList[RapyerKey] = Field(default_factory=list)
    tasks_left_to_run: RedisList[RapyerKey] = Field(default_factory=list)
    finished_tasks: RedisList[RapyerKey] = Field(default_factory=list)
    failed_tasks: RedisList[RapyerKey] = Field(default_factory=list)
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
        await self.ClientAdapter.acall_swarm_item_done(results, self, sub_task)

    async def on_sub_task_error(
        self, sub_task: TaskSignature, error: Exception, original_msg: BaseModel
    ):
        await self.ClientAdapter.acall_swarm_item_error(error, self, sub_task)

    async def acall(self, msg: Any, set_return_field: bool = True, **kwargs):
        # We update the kwargs that everyone are using, we also tell weather we should put this in the Return value or just in the message
        async with self.apipeline():
            self.kwargs.update(**{SWARM_MESSAGE_PARAM_NAME: msg})
            self.config.send_swarm_message_to_return_field = set_return_field
        return await self.ClientAdapter.afill_swarm(self, **kwargs)

    if HAS_HATCHET:

        async def aio_run_no_wait(
            self, msg: BaseModel, options: "TriggerWorkflowOptions" = None
        ):
            return await self.acall(
                msg.model_dump(mode="json", exclude_unset=True),
                set_return_field=False,
                options=options,
            )

        async def aio_run_in_swarm(
            self,
            task: TaskSignatureConvertible,
            msg: BaseModel,
            options: TriggerWorkflowOptions = None,
            close_on_max_task: bool = True,
        ) -> Optional["TaskRunRef"]:
            sub_task = await self.add_task(task, close_on_max_task)
            await sub_task.kwargs.aupdate(**msg.model_dump(mode="json"))
            return await self.ClientAdapter.afill_swarm(
                self, max_tasks=1, options=options
            )

    async def change_status(self, status: SignatureStatus):
        paused_chain_tasks = [
            TaskSignature.safe_change_status(task, status) for task in self.tasks
        ]
        pause_chain = super().change_status(status)
        await asyncio.gather(pause_chain, *paused_chain_tasks, return_exceptions=True)

    async def add_tasks(
        self, tasks: list[TaskSignatureConvertible], close_on_max_task: bool = True
    ) -> list[Signature]:
        """
        tasks - tasks signature to add to swarm
        close_on_max_task - if true, and you set max task allowed on swarm, this swarm will close if the task reached maximum capacity
        """
        if not self.config.can_add_n_tasks(self, len(tasks)):
            raise TooManyTasksError(
                f"Swarm {self.task_name} has reached max tasks limit"
            )
        if self.task_status.is_canceled():
            raise SwarmIsCanceledError(
                f"Swarm {self.task_name} is {self.task_status} - can't add task"
            )

        tasks = await resolve_signatures(tasks)
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
    ) -> Signature:
        """
        task - task signature to add to swarm
        close_on_max_task - if true, and you set max task allowed on swarm, this swarm will close if the task reached maximum capacity
        """
        added_tasks = await self.add_tasks([task], close_on_max_task)
        return added_tasks[0]

    async def is_swarm_done(self):
        done_tasks = self.finished_tasks + self.failed_tasks
        finished_all_tasks = set(done_tasks) == set(self.tasks)
        return self.is_swarm_closed and finished_all_tasks

    def has_published_callback(self):
        return self.task_status.status == SignatureStatus.DONE

    def has_published_errors(self):
        return self.task_status.status == SignatureStatus.FAILED

    async def activate_success(self, msg):
        results = await self.tasks_results.aload()
        tasks_results = [res for res in results]

        await super().activate_success(tasks_results)
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
        await self.aupdate(is_swarm_closed=True)
        should_finish_swarm = await self.is_swarm_done()
        if should_finish_swarm:
            await self.ClientAdapter.afill_swarm(self, max_tasks=0)
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
