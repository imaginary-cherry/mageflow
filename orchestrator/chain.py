import asyncio
from logging import Logger
from typing import Annotated, Any

from hatchet_sdk import Hatchet
from hatchet_sdk.runnables.types import EmptyModel
from pydantic import field_validator, Field
from redis.asyncio import Redis

from orchestrator.hatchet.deps import deps_logger, deps_hatchet, deps_redis
from orchestrator.hatchet.models import CommandTaskMessage
from orchestrator.hatchet.signature import (
    ReturnValue,
    TaskSignatureConvertible,
    SignatureStatus,
)
from orchestrator.hatchet.signature import (
    TaskSignature,
    TaskIdentifierType,
    resolve_signature_id,
    validate_task_id,
)
from orchestrator.task_name.infrastructure import InfrastructureTasks


class ChainTaskSignature(TaskSignature):
    tasks: list[TaskIdentifierType] = Field(default_factory=list)

    @field_validator("tasks", mode="before")
    @classmethod
    def validate_tasks(cls, v):
        return [validate_task_id(item) for item in v]

    async def workflow(self, **task_additional_params):
        first_task = await TaskSignature.from_id(self.tasks[0])
        return await first_task.workflow(**task_additional_params)

    async def delete_chain_tasks(self, with_errors=True, with_success=True):
        signatures = await asyncio.gather(
            *[TaskSignature.from_id(signature_id) for signature_id in self.tasks],
            return_exceptions=True,
        )
        signatures = [sign for sign in signatures if isinstance(sign, TaskSignature)]
        delete_tasks = [
            signature.remove(with_errors, with_success) for signature in signatures
        ]
        await asyncio.gather(*delete_tasks)

    async def change_status(self, status: SignatureStatus):
        stop_chain_tasks = [
            TaskSignature.de_change_status(task, status) for task in self.tasks
        ]
        stop_chain = super().change_status(status)
        await asyncio.gather(stop_chain, *stop_chain_tasks, return_exceptions=True)


class ChainTaskCommandMessage(CommandTaskMessage):
    chain_task_id: TaskIdentifierType


class ChainSuccessTaskCommandMessage(ChainTaskCommandMessage):
    chain_results: Annotated[Any, ReturnValue()]


# This task needs to be added as a workflow
async def chain_end_task(
    msg: ChainSuccessTaskCommandMessage,
    ctx,
    logger: Annotated[Logger, deps_logger],
    redis: Annotated[Redis, deps_redis],
    hatchet: Annotated[Hatchet, deps_hatchet],
):
    try:
        current_task_id = msg.metadata.task_id
        chain_packed_task, current_task = await asyncio.gather(
            ChainTaskSignature.from_id(msg.chain_task_id),
            TaskSignature.from_id(current_task_id),
        )
        logger.info(f"Chain task done {chain_packed_task.task_name}")

        # Calling error callback from chain task - This is done before deletion because deletion error should not disturb workflow
        await chain_packed_task.activate_success(msg.chain_results, context=msg.context)
        logger.info(f"Chain task success {chain_packed_task.task_name}")

        # Remove tasks
        await asyncio.gather(
            chain_packed_task.remove(with_success=False), current_task.remove()
        )
    except Exception as e:
        logger.exception(f"MAJOR - infrastructure error in chain end task: {e}")


# This task needs to be added as a workflow
async def chain_error_task(
    msg: EmptyModel,
    ctx,
    logger: Annotated[Logger, deps_logger],
    redis: Annotated[Redis, deps_redis],
    hatchet: Annotated[Hatchet, deps_hatchet],
):
    try:
        chain_msg = ChainTaskCommandMessage.model_validate(msg.model_dump())
        current_task_id = chain_msg.metadata.task_id
        chain_packed_task, current_task = await asyncio.gather(
            ChainTaskSignature.from_id(chain_msg.chain_task_id),
            TaskSignature.from_id(current_task_id),
        )
        logger.info(
            f"Chain task failed {chain_packed_task.task_name} on task id - {chain_msg.metadata.task_id}"
        )

        # Calling error callback from chain task
        await chain_packed_task.activate_error(msg)
        logger.info(f"Chain task error {chain_packed_task.task_name}")

        # Remove tasks
        await chain_packed_task.delete_chain_tasks()
        await asyncio.gather(
            chain_packed_task.remove(with_error=False), current_task.remove()
        )
        logger.info(f"Clean redis from chain tasks {chain_packed_task.task_name}")
    except Exception as e:
        logger.exception(f"MAJOR - infrastructure error in chain error task: {e}")


async def chain(*args, **kwargs) -> ChainTaskSignature:
    chain_packed_task = await _chain(*args, **kwargs)
    return chain_packed_task


async def _chain(
    tasks: list[TaskSignatureConvertible],
    name: str = None,
    error: TaskIdentifierType = None,
    success: TaskIdentifierType = None,
) -> ChainTaskSignature:
    tasks = [await resolve_signature_id(task) for task in tasks]

    # Create a chain task that will be deleted only at the end of the chain
    first_task = tasks[0]
    packed_chain_task = ChainTaskSignature(
        task_name=f"chain-task:{name or first_task.task_name}",
        kwargs={},
        success_callbacks=[success] if success else [],
        error_callbacks=[error] if error else [],
        tasks=tasks,
    )
    await packed_chain_task.save()

    callback_kwargs = dict(chain_task_id=packed_chain_task.id)
    on_chain_error = TaskSignature(
        task_name=InfrastructureTasks.on_chain_error,
        kwargs=callback_kwargs,
        model_validators=ChainSuccessTaskCommandMessage,
    )
    on_chain_success = TaskSignature(
        task_name=InfrastructureTasks.on_chain_done,
        kwargs=callback_kwargs,
        model_validators=ChainSuccessTaskCommandMessage,
    )
    await _chain_task_to_previous_success(tasks, on_chain_error, on_chain_success)
    return packed_chain_task


async def _chain_task_to_previous_success(
    tasks: list[TaskSignature], error: TaskSignature, success: TaskSignature
) -> TaskIdentifierType:
    """
    Take a list of tasks and connect each one to the previous one.
    """
    if len(tasks) < 2:
        raise ValueError(
            "Chained tasks must contain at least two tasks. "
            "If you want to run a single task, use `create_workflow` instead."
        )

    total_tasks = tasks + [success]
    error_tasks = [TaskSignature.from_signature(error) for _ in tasks]
    store_errors = [error.save() for error in error_tasks]

    # Store tasks
    await asyncio.gather(success.save(), *store_errors)
    update_tasks = [
        task.add_callbacks(success=[total_tasks[i + 1]], errors=[error_tasks[i]])
        for i, task in enumerate(tasks)
    ]
    chained_tasks = await asyncio.gather(*update_tasks)
    return chained_tasks[0]
