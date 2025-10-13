import asyncio
import pickle
import uuid
from logging import Logger
from typing import Annotated, Self, Any, Optional

from pydantic import Field, field_validator, BaseModel
from redis.asyncio import Redis

from orchestrator.hatchet.models import ContextTaskMessage
from orchestrator.hatchet.deps import deps_redis, deps_logger
from orchestrator.hatchet.models import CommandTaskMessage
from orchestrator.hatchet.signature import (
    TaskSignature,
    TaskIdentifierType,
    validate_task_id,
    TaskSignatureConvertible,
    resolve_signature_id,
    SignatureStatus,
)
from orchestrator.hatchet.utils import FakeModel
from orchestrator.task_name.infrastructure import InfrastructureTasks


class BatchItemTaskSignature(TaskSignature):
    swarm_id: TaskIdentifierType
    original_task_id: TaskIdentifierType

    async def aio_run_no_wait(self, msg: BaseModel, **kwargs):
        swarm_task = await SwarmTaskSignature.from_id(self.swarm_id)
        original_task = await TaskSignature.from_id(self.original_task_id)
        can_run_task = await swarm_task.add_to_running_tasks(self)
        kwargs = deep_merge(self.kwargs, original_task.kwargs)
        kwargs = deep_merge(kwargs, swarm_task.task_kwargs)
        if can_run_task:
            await original_task.update(kwargs=kwargs)
            return await original_task.aio_run_no_wait(msg, **kwargs)
        kwargs = deep_merge(kwargs, msg.model_dump(mode="json"))
        await original_task.update(kwargs=kwargs)
        return None

    async def _remove(self, with_error: bool = True, with_success: bool = True):
        original_task = await TaskSignature.from_id(self.original_task_id)
        remove_self = super()._remove(with_error, with_success)
        remove_original = original_task.remove(with_error, with_success)
        return await asyncio.gather(remove_self, remove_original)


class SwarmConfig(BaseModel):
    max_concurrency: int = 30
    stop_after_n_failures: Optional[int] = None


class SwarmTaskSignature(TaskSignature):
    tasks: list[TaskIdentifierType] = Field(default_factory=list)
    tasks_left_to_run: list[TaskIdentifierType] = Field(default_factory=list)
    finished_tasks: list[TaskIdentifierType] = Field(default_factory=list)
    failed_tasks: list[TaskIdentifierType] = Field(default_factory=list)
    tasks_results: list[bytes] = Field(default_factory=list)
    # This flag is raised when no more tasks can be added to the swarm
    is_swarm_closed: bool = False
    # How many tasks can be added to the swarm at a time
    current_running_tasks: int = 0
    config: SwarmConfig = Field(default_factory=SwarmConfig)

    task_kwargs: dict = Field(default_factory=dict)

    @field_validator(
        "tasks", "tasks_left_to_run", "finished_tasks", "failed_tasks", mode="before"
    )
    @classmethod
    def validate_tasks(cls, v):
        return [validate_task_id(item) for item in v]

    async def aio_run_no_wait(self, msg: BaseModel, **kwargs):
        await self.update(task_kwargs=msg.model_dump(mode="json"))
        workflow = await self.workflow(use_return_field=False, context=msg.context)
        return await workflow.aio_run_no_wait(msg, **kwargs)

    async def workflow(self, use_return_field: bool = True, **task_additional_params):
        # Use on swarm start task name for wf
        task_name = self.task_name
        self.task_name = InfrastructureTasks.on_swarm_start
        workflow = await super().workflow(
            **task_additional_params, swarm_task_id=self.id, use_return_field=True
        )
        self.task_name = task_name
        return workflow

    async def try_delete_sub_tasks(
        self, with_error: bool = True, with_success: bool = True
    ):
        tasks = await asyncio.gather(
            *[TaskSignature.from_id(task_id) for task_id in self.tasks],
            return_exceptions=True,
        )
        tasks = [task for task in tasks if isinstance(task, TaskSignature)]
        await asyncio.gather(
            *[task.remove(with_error, with_success) for task in tasks],
            return_exceptions=True,
        )

    async def _remove(self, *args, **kwargs):
        delete_signature = super()._remove(*args, **kwargs)
        delete_tasks = self.try_delete_sub_tasks()

        return await asyncio.gather(delete_signature, delete_tasks)

    async def change_status(self, status: SignatureStatus):
        stop_chain_tasks = [
            TaskSignature.de_change_status(task, status) for task in self.tasks
        ]
        stop_chain = super().change_status(status)
        await asyncio.gather(stop_chain, *stop_chain_tasks, return_exceptions=True)

    async def add_task(self, task: TaskSignatureConvertible) -> BatchItemTaskSignature:
        task = await resolve_signature_id(task)
        dump = task.model_dump(exclude={"id", "task_name"})
        batch_task_name = f"batch-task-{task.task_name}"
        batch_task = BatchItemTaskSignature(
            **dump,
            task_name=batch_task_name,
            swarm_id=self.id,
            original_task_id=task.id,
        )
        on_success_swarm_item = await TaskSignature.from_task_name(
            task_name=InfrastructureTasks.on_swarm_done,
            input_validator=SwarmItemTaskDoneMessage,
            swarm_task_id=self.id,
            swarm_item_id=batch_task.id,
        )
        on_error_swarm_item = await TaskSignature.from_task_name(
            task_name=InfrastructureTasks.on_swarm_error,
            input_validator=SwarmItemTaskDoneMessage,
            swarm_task_id=self.id,
            swarm_item_id=batch_task.id,
        )
        task.success_callbacks.append(on_success_swarm_item.id)
        task.error_callbacks.append(on_error_swarm_item.id)
        await task.save()
        await batch_task.save()
        await self.append_to_list("tasks", batch_task.id)
        return batch_task

    async def add_to_running_tasks(self, task: TaskSignatureConvertible) -> bool:
        task = await resolve_signature_id(task)
        async with acquire_lock(self.Meta.redis, self.id):
            load_fields = await self.load_fields(self.key, "current_running_tasks")
            current_running_tasks = load_fields["current_running_tasks"]
            if current_running_tasks < self.config.max_concurrency:
                await self.increase_counter("current_running_tasks")
                return True
            else:
                await self.append_to_list("tasks_left_to_run", task.id)
                return False

    async def decrease_running_tasks_count(self):
        await self.increase_counter("current_running_tasks", -1)

    async def pop_task_to_run(self) -> TaskIdentifierType | None:
        task = await self.pop("tasks_left_to_run")
        return task

    async def add_to_finished_tasks(self, task: TaskIdentifierType):
        await self.append_to_list("finished_tasks", task)

    async def add_to_failed_tasks(self, task: TaskIdentifierType):
        await self.append_to_list("failed_tasks", task)

    async def is_swarm_done(self):
        await asyncio.gather(
            self.load("finished_tasks"),
            self.load("failed_tasks"),
            self.load("tasks"),
        )
        done_tasks = self.finished_tasks + self.failed_tasks
        return self.is_swarm_closed and set(done_tasks) == set(self.tasks)

    async def activate_success(self, msg, **kwargs):
        await self.load("tasks_results")
        tasks_results = [pickle.loads(res) for res in self.tasks_results]

        context = self.kwargs.get("context", {}) or msg.context
        await super().activate_success(tasks_results, context=context)
        await self.remove(with_success=False)

    async def close_swarm(self) -> Self:
        async with acquire_lock(self.Meta.redis, self.id):
            await self.update(is_swarm_closed=True)
            should_finish_swarm = await self.is_swarm_done()
        if should_finish_swarm:
            await self.activate_callbacks(ContextTaskMessage(context={}))

        return self


class BaseSwarmTaskMessage(CommandTaskMessage):
    swarm_task_id: TaskIdentifierType


class SwarmTaskCommandMessage(BaseSwarmTaskMessage):
    results: Any


class SwarmItemTaskDoneMessage(SwarmTaskCommandMessage):
    swarm_item_id: TaskIdentifierType


class SwarmItemTaskErrorMessage(BaseSwarmTaskMessage):
    swarm_item_id: TaskIdentifierType


async def swarm_start_tasks(
    msg: SwarmTaskCommandMessage, ctx, logger: Annotated[Logger, deps_logger]
):
    try:
        logger.info(f"Swarm task started {msg}")
        swarm_task = await SwarmTaskSignature.from_id(msg.swarm_task_id)
        if swarm_task.current_running_tasks:
            logger.warning(f"Swarm task started but already running {msg}")
            return
        tasks_msg = msg.results
        tasks_ids_to_run = swarm_task.tasks[: swarm_task.config.max_concurrency]
        tasks_to_run = await asyncio.gather(
            *[TaskSignature.from_id(task_id) for task_id in tasks_ids_to_run]
        )
        await asyncio.gather(
            *[task.aio_run_no_wait(tasks_msg) for task in tasks_to_run]
        )
        logger.info(f"Swarm task started with tasks {tasks_ids_to_run} {msg}")
    except Exception as e:
        logger.exception(f"MAJOR - Error in swarm start tasks: {e}")


async def swarm_item_done(
    msg: SwarmItemTaskDoneMessage,
    ctx,
    logger: Annotated[Logger, deps_logger],
    redis: Annotated[Redis, deps_redis],
):
    try:
        logger.info(f"Swarm item done {msg.swarm_item_id}")
        # Update swarm tasks
        swarm_task = await SwarmTaskSignature.from_id(msg.swarm_task_id)
        finish_task = swarm_task.append_to_list("finished_tasks", msg.swarm_item_id)
        res = pickle.dumps(msg.results)
        update_result = swarm_task.append_to_list("tasks_results", res)
        async with acquire_lock(redis, swarm_task.id):
            await asyncio.gather(finish_task, update_result)
        await handle_finish_tasks(redis, swarm_task, logger, msg)
    except Exception as e:
        logger.exception(f"MAJOR - Error in swarm start item done: {e}")


async def swarm_item_failed(
    msg: SwarmItemTaskErrorMessage,
    ctx,
    logger: Annotated[Logger, deps_logger],
    redis: Annotated[Redis, deps_redis],
):
    try:
        logger.info(f"Swarm item failed {msg.swarm_item_id}")
        # Check if the swarm should end
        swarm_task = await SwarmTaskSignature.from_id(msg.swarm_task_id)
        async with acquire_lock(redis, swarm_task.id):
            await swarm_task.add_to_failed_tasks(msg.swarm_item_id)
            await swarm_task.load("failed_tasks")
        should_stop_after_failures = swarm_task.config.stop_after_n_failures is not None
        too_many_errors = (
            len(swarm_task.failed_tasks) >= swarm_task.config.stop_after_n_failures
        )
        if should_stop_after_failures and too_many_errors:
            logger.info(
                f"Swarm item failed - stopping swarm {swarm_task.id} after {len(swarm_task.failed_tasks)} failures"
            )
            await swarm_task.change_status(SignatureStatus.CANCELED)
            await swarm_task.load("tasks_results")
            context = swarm_task.kwargs.get("context", {}) or msg.context
            result = swarm_task.task_kwargs | {
                "results": swarm_task.tasks_results,
                "context": context,
            }
            await swarm_task.activate_error(result)
            logger.info(f"Swarm item failed - stopped swarm {swarm_task.id}")
            return

        await handle_finish_tasks(redis, swarm_task, logger, msg)
    except Exception as e:
        logger.exception(f"MAJOR - Error in swarm item failed: {e}")


async def handle_finish_tasks(
    redis: Redis,
    swarm_task: SwarmTaskSignature,
    logger: Logger,
    msg: CommandTaskMessage,
):
    async with acquire_lock(redis, swarm_task.id):
        next_task = await swarm_task.pop_task_to_run()
        if next_task:
            next_task_signature = await TaskSignature.from_id(next_task)
            # The message is already stored in the task signature
            await next_task_signature.aio_run_no_wait(FakeModel())
            logger.info(f"Swarm item started new task {next_task}/{swarm_task.id}")
        else:
            await swarm_task.decrease_running_tasks_count()
            logger.info(f"Swarm item no new task to run in {swarm_task.id}")

    # Check if the swarm should end
    if await swarm_task.is_swarm_done():
        logger.info(f"Swarm item done - closing swarm {swarm_task.id}")
        await swarm_task.activate_success(msg)
        logger.info(f"Swarm item done - closed swarm {swarm_task.id}")

    # Delete internal task
    curr_task = await TaskSignature.from_id(msg.metadata.task_id)
    await curr_task.remove()


async def swarm(
    tasks: list[TaskSignatureConvertible] = None, task_name: str = None, **kwargs
) -> SwarmTaskSignature:
    tasks = tasks or []
    task_name = task_name or f"swarm-task-{uuid.uuid4()}"
    swarm_signature = SwarmTaskSignature(**kwargs, task_name=task_name)
    await swarm_signature.save()
    await asyncio.gather(*[swarm_signature.add_task(task) for task in tasks])
    return swarm_signature


# TODO - fix pipeline in chain git

# TODO - what happens when swarm finish tasks before it closes
# TODO - add callback for swarm per task
# TODO - if task is closed, you can still add tasks to it - check it in unit tests
# TODO - test:
#       1. check that all sub task use the same config - DONE
#       2. check that both config are merged (if 2 are send)
#       3. check that kwargs are sent to callback for swarm
#       4. check workflow_params is sent to swarm callback - NOT NOW
#       5. Check that error is sent once I reach max failure, check that no more tasks were called
#       6. Check each task callback is called
#       7. check each task failure is called if needed
#       8. Check that tasks run concurrently, and no more than max concurrency
#       8. Check that callback is called only once - DONE
#       9. Test when we finish at failed task - but the swarm succeded
#       10. Test chain task and a swarm task nested in each other
# TODO - If I start a swarm, how to ensure I reach the max concurrency? (I start with 3 and add tasks, how to ensure I reach max concurrency?)
# TODO - extract all tests to fixtures and assert functions
# TODO - what to do in chain if error has tree, need to duplicate the entire tree
# TODO - allow only certain errors for change status
# TODO - deps for logger should change to hatchet logger with context
# TODO - make sure you cant call swarm twice
# TODO - Allow user to chose to run without additional flows (callback on the same task)
# TODO - make result in order for final callback
# TODO - what to do when we send new task to a failed swarm? - dont run and, it is likly the signature was already deleted, should be tested


# NOT QUITE IMPORTANT
# TODO - add kwargs for each task (in additional parameter)
# TODO - what happen if both task, chain task and swarm give a context, how is it all merged?
# TODO - add option to run chain and swarm without additional tasks and wf (all inside the current task)
# TODO - understand how to work with honeycomb and add logs for current state in it
# TODO - extract hatchet activation to a separate class
# TODO - add deep merge for redis functionallity and use it - the merge should be atomic
