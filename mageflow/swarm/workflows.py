from hatchet_sdk import Context
from hatchet_sdk.runnables.types import EmptyModel

from mageflow.invokers.hatchet import HatchetInvoker
from mageflow.signature.consts import TASK_ID_PARAM_NAME
from mageflow.signature.model import TaskSignature
from mageflow.swarm.consts import (
    SWARM_TASK_ID_PARAM_NAME,
    SWARM_ITEM_TASK_ID_PARAM_NAME,
    SWARM_FILL_TASK,
    SWARM_ACTION_FILL,
)
from mageflow.swarm.messages import SwarmResultsMessage, SwarmMessage
from mageflow.swarm.model import SwarmTaskSignature


async def swarm_start_tasks(msg: EmptyModel, ctx: Context):
    try:
        ctx.log(f"Swarm task started {msg}")
        swarm_task_id = msg.model_dump()[SWARM_TASK_ID_PARAM_NAME]
        swarm_task = await SwarmTaskSignature.get_safe(swarm_task_id)
        if swarm_task.has_swarm_started:
            ctx.log(f"Swarm task started but already running {msg}")
            return

        invoker = HatchetInvoker(msg, ctx)
        fill_swarm_msg = SwarmMessage(swarm_task_id=swarm_task_id)
        await swarm_task.tasks_left_to_run.aextend(swarm_task.tasks)
        await invoker.wait_task(SWARM_FILL_TASK, fill_swarm_msg)
        ctx.log(f"Swarm task started running {swarm_task.config.max_concurrency} tasks")
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
        await swarm_task.finish_task(swarm_item_id, msg.mageflow_results)

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
        msg_data = msg.model_dump()
        swarm_task_key = msg_data[SWARM_TASK_ID_PARAM_NAME]
        swarm_item_key = msg_data[SWARM_ITEM_TASK_ID_PARAM_NAME]
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
    async with SwarmTaskSignature.alock_from_key(
        msg.swarm_task_id, action=SWARM_ACTION_FILL
    ) as swarm_task:
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
        still_should_publish = not swarm_task.has_published_callback()
        is_swarm_finished_running = await swarm_task.is_swarm_done()
        if is_swarm_finished_running and still_should_publish:
            ctx.log(f"Swarm item done - closing swarm {swarm_task.key}")
            await swarm_task.done()
            await swarm_task.activate_success(msg)
            ctx.log(f"Swarm item done - closed swarm {swarm_task.key}")
