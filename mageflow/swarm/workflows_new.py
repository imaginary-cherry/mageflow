"""
Swarm workflow handlers - task manager agnostic version.

This module provides the swarm task handlers that work with any task manager.
They use TaskContext instead of Hatchet's Context directly.
"""
from typing import cast, TYPE_CHECKING

import rapyer
from pydantic import BaseModel

from mageflow.adapters.protocols import TaskContext, TaskExecutionInfo
from mageflow.invokers.base import BaseInvoker
from mageflow.signature.consts import TASK_ID_PARAM_NAME
from mageflow.signature.model import TaskSignature
from mageflow.startup import mageflow_config
from mageflow.swarm.consts import (
    SWARM_TASK_ID_PARAM_NAME,
    SWARM_ITEM_TASK_ID_PARAM_NAME,
    SWARM_FILL_TASK,
    SWARM_ACTION_FILL,
)
from mageflow.swarm.messages import SwarmResultsMessage, SwarmMessage
from mageflow.swarm.model import SwarmTaskSignature, BatchItemTaskSignature

if TYPE_CHECKING:
    from mageflow.adapters.protocols import TaskManagerAdapter


async def swarm_start_tasks_handler(
    msg: BaseModel,
    task_context: TaskContext,
    invoker: BaseInvoker,
):
    """
    Handle swarm start - task manager agnostic.

    Args:
        msg: The swarm start message
        task_context: Normalized task context
        invoker: Task invoker for lifecycle management
    """
    try:
        task_context.log(f"Swarm task started {msg}")
        msg_data = msg.model_dump() if hasattr(msg, "model_dump") else msg
        swarm_task_id = msg_data[SWARM_TASK_ID_PARAM_NAME]
        swarm_task = await SwarmTaskSignature.get_safe(swarm_task_id)

        if swarm_task.has_swarm_started:
            task_context.log(f"Swarm task started but already running {msg}")
            return

        fill_swarm_msg = SwarmMessage(swarm_task_id=swarm_task_id)
        await swarm_task.tasks_left_to_run.aextend(swarm_task.tasks)

        tasks = await rapyer.afind(*swarm_task.tasks)
        tasks = cast(list[BatchItemTaskSignature], tasks)
        original_tasks = await rapyer.afind(*[task.original_task_id for task in tasks])
        original_tasks = cast(list[TaskSignature], original_tasks)

        async with swarm_task.apipeline():
            for task in original_tasks:
                await task.aupdate_real_task_kwargs(**swarm_task.kwargs)

        await invoker.wait_task(SWARM_FILL_TASK, fill_swarm_msg)
        task_context.log(
            f"Swarm task started running {swarm_task.config.max_concurrency} tasks"
        )
    except Exception:
        task_context.log("MAJOR - Error in swarm start tasks")
        raise


async def swarm_item_done_handler(
    msg: SwarmResultsMessage,
    task_context: TaskContext,
    invoker: BaseInvoker,
):
    """
    Handle swarm item completion - task manager agnostic.

    Args:
        msg: The swarm results message
        task_context: Normalized task context
        invoker: Task invoker for lifecycle management
    """
    task_data = invoker.task_ctx
    task_key = task_data[TASK_ID_PARAM_NAME]

    try:
        swarm_task_id = msg.swarm_task_id
        swarm_item_id = msg.swarm_item_id
        task_context.log(f"Swarm item done {swarm_item_id}")

        # Update swarm tasks
        swarm_task = await SwarmTaskSignature.aget(swarm_task_id)

        task_context.log(f"Swarm item done {swarm_item_id} - saving results")
        await swarm_task.finish_task(swarm_item_id, msg.mageflow_results)

        # Publish next tasks
        fill_swarm_msg = SwarmMessage(swarm_task_id=swarm_task_id)
        await invoker.wait_task(SWARM_FILL_TASK, fill_swarm_msg)
    except Exception as e:
        task_context.log("MAJOR - Error in swarm start item done")
        raise
    finally:
        await TaskSignature.remove_from_key(task_key)


async def swarm_item_failed_handler(
    msg: BaseModel,
    task_context: TaskContext,
    invoker: BaseInvoker,
):
    """
    Handle swarm item failure - task manager agnostic.

    Args:
        msg: The failure message
        task_context: Normalized task context
        invoker: Task invoker for lifecycle management
    """
    task_data = invoker.task_ctx
    task_key = task_data[TASK_ID_PARAM_NAME]

    try:
        msg_data = msg.model_dump() if hasattr(msg, "model_dump") else msg
        swarm_task_key = msg_data[SWARM_TASK_ID_PARAM_NAME]
        swarm_item_key = msg_data[SWARM_ITEM_TASK_ID_PARAM_NAME]
        task_context.log(f"Swarm item failed {swarm_item_key}")

        # Check if the swarm should end
        swarm_task = await SwarmTaskSignature.get_safe(swarm_task_key)
        await swarm_task.task_failed(swarm_item_key)

        fill_swarm_msg = SwarmMessage(swarm_task_id=swarm_task_key)
        await invoker.wait_task(SWARM_FILL_TASK, fill_swarm_msg)
    except Exception as e:
        task_context.log("MAJOR - Error in swarm item failed")
        raise
    finally:
        await TaskSignature.remove_from_key(task_key)


async def fill_swarm_running_tasks_handler(
    msg: SwarmMessage,
    task_context: TaskContext,
):
    """
    Handle swarm fill - task manager agnostic.

    Args:
        msg: The swarm fill message
        task_context: Normalized task context
    """
    # Import here to avoid circular import - EmptyModel is Hatchet-specific
    # but we need something for activate_error. Use a dict or create a generic.
    from pydantic import BaseModel as EmptyModel

    async with SwarmTaskSignature.alock_from_key(
        msg.swarm_task_id, action=SWARM_ACTION_FILL
    ) as swarm_task:
        if swarm_task.has_swarm_failed():
            task_context.log(f"Swarm failed too much {msg.swarm_task_id}")
            swarm_task = await SwarmTaskSignature.get_safe(msg.swarm_task_id)
            if swarm_task is None or swarm_task.has_published_errors():
                task_context.log(
                    f"Swarm {msg.swarm_task_id} was deleted already deleted or failed"
                )
                return
            await swarm_task.interrupt()
            await swarm_task.activate_error({})  # Empty dict instead of EmptyModel
            await swarm_task.remove(with_error=False)
            await swarm_task.failed()
            return

        num_task_started = await swarm_task.fill_running_tasks()
        if num_task_started:
            task_context.log(
                f"Swarm item started new task {num_task_started}/{swarm_task.key}"
            )
        else:
            task_context.log(f"Swarm item no new task to run in {swarm_task.key}")

        # Check if the swarm should end
        not_yet_published = not swarm_task.has_published_callback()
        is_swarm_finished_running = await swarm_task.is_swarm_done()
        if is_swarm_finished_running and not_yet_published:
            task_context.log(f"Swarm item done - closing swarm {swarm_task.key}")
            await swarm_task.activate_success(msg)
            await swarm_task.done()
            task_context.log(f"Swarm item done - closed swarm {swarm_task.key}")
