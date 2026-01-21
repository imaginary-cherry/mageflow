import asyncio

from hatchet_sdk import Context
from hatchet_sdk.runnables.types import EmptyModel

from mageflow.invokers.hatchet import HatchetInvoker
from mageflow.signature.consts import TASK_ID_PARAM_NAME
from mageflow.signature.model import TaskSignature
from mageflow.swarm.consts import (
    SWARM_TASK_ID_PARAM_NAME,
    SWARM_ITEM_TASK_ID_PARAM_NAME,
    SWARM_FILL_TASK,
)
from mageflow.swarm.messages import SwarmResultsMessage, SwarmMessage
from mageflow.swarm.model import SwarmTaskSignature


async def swarm_start_tasks(msg: EmptyModel, ctx: Context):
    try:
        ctx.log(f"Swarm task started {msg}")
        task_data = HatchetInvoker(msg, ctx).task_ctx
        swarm_task_id = task_data[SWARM_TASK_ID_PARAM_NAME]
        swarm_task = await SwarmTaskSignature.get_safe(swarm_task_id)
        if swarm_task.has_swarm_started:
            ctx.log(f"Swarm task started but already running {msg}")
            return
        tasks_ids_to_run = swarm_task.tasks[: swarm_task.config.max_concurrency]
        tasks_left_to_run = swarm_task.tasks[swarm_task.config.max_concurrency :]
        async with swarm_task.apipeline() as swarm_task:
            await swarm_task.tasks_left_to_run.aclear()
            await swarm_task.tasks_left_to_run.aextend(tasks_left_to_run)
        tasks_to_run = await asyncio.gather(
            *[TaskSignature.get_safe(task_id) for task_id in tasks_ids_to_run]
        )
        await asyncio.gather(*[task.aio_run_no_wait(msg) for task in tasks_to_run])
        ctx.log(f"Swarm task started with tasks {tasks_ids_to_run} {msg}")
    except Exception:
        ctx.log(f"MAJOR - Error in swarm start tasks")
        raise


async def swarm_item_done(msg: SwarmResultsMessage, ctx: Context):
    invoker = HatchetInvoker(msg, ctx)
    task_data = invoker.task_ctx
    task_key = task_data[TASK_ID_PARAM_NAME]
    try:
        swarm_task_id = msg.swarm_task_id
        swarm_item_id = msg.swarm_item_id
        ctx.log(f"Swarm item done {swarm_item_id}")

        # Update swarm tasks
        swarm_task = await SwarmTaskSignature.aget(swarm_task_id)

        ctx.log(f"Swarm item done {swarm_item_id} - saving results")
        await swarm_task.finish_task(swarm_item_id, msg.results)

        # Publish next tasks
        fill_swarm_msg = SwarmMessage(swarm_task_id=swarm_task_id)
        await invoker.wait_task(SWARM_FILL_TASK, fill_swarm_msg)
    except Exception as e:
        ctx.log(f"MAJOR - Error in swarm start item done")
        raise
    finally:
        await TaskSignature.remove_from_key(task_key)


async def swarm_item_failed(msg: EmptyModel, ctx: Context):
    invoker = HatchetInvoker(msg, ctx)
    task_data = invoker.task_ctx
    task_key = task_data[TASK_ID_PARAM_NAME]
    try:
        swarm_task_key = task_data[SWARM_TASK_ID_PARAM_NAME]
        swarm_item_key = task_data[SWARM_ITEM_TASK_ID_PARAM_NAME]
        ctx.log(f"Swarm item failed {swarm_item_key}")
        # Check if the swarm should end
        swarm_task = await SwarmTaskSignature.get_safe(swarm_task_key)
        await swarm_task.task_failed(swarm_item_key)
        fill_swarm_msg = SwarmMessage(swarm_task_id=swarm_task_key)
        await invoker.wait_task(SWARM_FILL_TASK, fill_swarm_msg)
    except Exception as e:
        ctx.log(f"MAJOR - Error in swarm item failed")
        raise
    finally:
        await TaskSignature.remove_from_key(task_key)


async def fill_swarm_running_tasks(msg: SwarmMessage, ctx: Context):
    swarm_task = await SwarmTaskSignature.aget(msg.swarm_task_id)
    if swarm_task.has_swarm_failed():
        ctx.log(f"Swarm failed too much {msg.swarm_task_id}")
        swarm_task = await SwarmTaskSignature.get_safe(msg.swarm_task_id)
        if swarm_task is None:
            ctx.log(f"Swarm {msg.swarm_task_id} was deleted already deleted")
            return
        await swarm_task.interrupt()
        await swarm_task.activate_error(EmptyModel())
        await swarm_task.remove(with_error=False)
        return

    num_task_started = await swarm_task.fill_running_tasks()
    if num_task_started:
        ctx.log(f"Swarm item started new task {num_task_started}/{swarm_task.key}")
    else:
        ctx.log(f"Swarm item no new task to run in {swarm_task.key}")

    # Check if the swarm should end
    if await swarm_task.is_swarm_done() and swarm_task.has_published_callback():
        ctx.log(f"Swarm item done - closing swarm {swarm_task.key}")
        await swarm_task.done()
        await swarm_task.activate_success(msg)
        ctx.log(f"Swarm item done - closed swarm {swarm_task.key}")
