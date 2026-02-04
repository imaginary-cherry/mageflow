from typing import cast

import rapyer
from hatchet_sdk import Context
from hatchet_sdk.runnables.types import EmptyModel

from mageflow.invokers.hatchet import HatchetInvoker
from mageflow.signature.model import TaskSignature
from mageflow.swarm.consts import SWARM_FILL_TASK, SWARM_ACTION_FILL
from mageflow.swarm.messages import SwarmResultsMessage, SwarmMessage, SwarmErrorMessage
from mageflow.swarm.model import SwarmTaskSignature, BatchItemTaskSignature


async def swarm_start_tasks(msg: SwarmMessage, ctx: Context):
    try:
        ctx.log(f"Swarm task started {msg}")
        swarm_task_id = msg.swarm_task_id
        swarm_task = await SwarmTaskSignature.get_safe(swarm_task_id)
        if swarm_task.has_swarm_started:
            ctx.log(f"Swarm task started but already running {msg}")
            return

        fill_swarm_msg = SwarmMessage(swarm_task_id=swarm_task_id)
        await swarm_task.tasks_left_to_run.aextend(swarm_task.tasks)
        tasks = await rapyer.afind(*swarm_task.tasks)
        tasks = cast(list[BatchItemTaskSignature], tasks)
        original_tasks = await rapyer.afind(*[task.original_task_id for task in tasks])
        original_tasks = cast(list[TaskSignature], original_tasks)
        await HatchetInvoker.wait_task(SWARM_FILL_TASK, fill_swarm_msg)
        ctx.log(f"Swarm task started running {swarm_task.config.max_concurrency} tasks")
    except Exception:
        ctx.log(f"MAJOR - Error in swarm start tasks")
        raise


async def swarm_item_done(msg: SwarmResultsMessage, ctx: Context):
    try:
        swarm_task_id = msg.swarm_task_id
        swarm_item_id = msg.swarm_item_id
        ctx.log(f"Swarm item done {swarm_item_id}")

        # Update swarm tasks
        swarm_task = await SwarmTaskSignature.aget(swarm_task_id)

        ctx.log(f"Swarm item done {swarm_item_id} - saving results")
        batch = await swarm_task.get_batch_from_key(swarm_item_id)
        await swarm_task.finish_task(batch.key, msg.mageflow_results)

        # Publish next tasks
        fill_swarm_msg = SwarmMessage(swarm_task_id=swarm_task_id)
        await HatchetInvoker.wait_task(SWARM_FILL_TASK, fill_swarm_msg)
    except Exception as e:
        ctx.log(f"MAJOR - Error in swarm start item done")
        raise


async def swarm_item_failed(msg: SwarmErrorMessage, ctx: Context):
    try:
        swarm_task_key = msg.swarm_task_id
        swarm_item_key = msg.swarm_item_id
        ctx.log(f"Swarm item failed {swarm_item_key} - {msg.error}")
        # Check if the swarm should end
        swarm_task = await SwarmTaskSignature.get_safe(swarm_task_key)
        batch = await swarm_task.get_batch_from_key(swarm_item_key)
        await swarm_task.task_failed(batch.key)
        fill_swarm_msg = SwarmMessage(swarm_task_id=swarm_task_key)
        await HatchetInvoker.wait_task(SWARM_FILL_TASK, fill_swarm_msg)
    except Exception as e:
        ctx.log(f"MAJOR - Error in swarm item failed")
        raise


async def fill_swarm_running_tasks(msg: SwarmMessage, ctx: Context):
    async with SwarmTaskSignature.alock_from_key(
        msg.swarm_task_id, action=SWARM_ACTION_FILL
    ) as swarm_task:
        if swarm_task.has_swarm_failed():
            ctx.log(f"Swarm failed too much {msg.swarm_task_id}")
            swarm_task = await SwarmTaskSignature.get_safe(msg.swarm_task_id)
            if swarm_task is None or swarm_task.has_published_errors():
                ctx.log(
                    f"Swarm {msg.swarm_task_id} was deleted already deleted or failed"
                )
                return
            await swarm_task.interrupt()
            await swarm_task.activate_error(EmptyModel())
            await swarm_task.remove(with_error=False)
            await swarm_task.failed()
            return

        num_task_started = await swarm_task.fill_running_tasks()
        if num_task_started:
            ctx.log(f"Swarm item started new task {num_task_started}/{swarm_task.key}")
        else:
            ctx.log(f"Swarm item no new task to run in {swarm_task.key}")

        # Check if the swarm should end
        not_yet_published = not swarm_task.has_published_callback()
        is_swarm_finished_running = await swarm_task.is_swarm_done()
        if is_swarm_finished_running and not_yet_published:
            ctx.log(f"Swarm item done - closing swarm {swarm_task.key}")
            await swarm_task.activate_success(msg)
            await swarm_task.done()
            ctx.log(f"Swarm item done - closed swarm {swarm_task.key}")
