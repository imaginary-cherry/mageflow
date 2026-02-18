from hatchet_sdk import Context
from hatchet_sdk.runnables.types import EmptyModel
from thirdmagic.swarm.model import SwarmTaskSignature

from mageflow.invokers.hatchet import HatchetInvoker
from mageflow.swarm.consts import SWARM_ACTION_FILL
from mageflow.swarm.messages import SwarmResultsMessage, SwarmMessage, SwarmErrorMessage


async def swarm_item_done(msg: SwarmResultsMessage, ctx: Context):
    try:
        swarm_task_id = msg.swarm_task_id
        swarm_item_id = msg.swarm_item_id
        ctx.log(f"Swarm item done {swarm_item_id}")

        # Update swarm tasks
        swarm_task = await SwarmTaskSignature.aget(swarm_task_id)

        ctx.log(f"Swarm item done {swarm_item_id} - saving results")
        await swarm_task.finish_task(swarm_item_id, msg.mageflow_results)

        # Publish next tasks
        await SwarmTaskSignature.ClientAdapter.afill_swarm(swarm_task)
    except Exception as e:
        ctx.log(f"MAJOR - Error in swarm start item done")
        raise


async def swarm_item_failed(msg: SwarmErrorMessage, ctx: Context):
    try:
        swarm_task_key = msg.swarm_task_id
        swarm_item_key = msg.swarm_item_id
        ctx.log(f"Swarm item failed {swarm_item_key} - {msg.error}")
        # Check if the swarm should end
        swarm_task = await SwarmTaskSignature.aget(swarm_task_key)
        await swarm_task.task_failed(swarm_item_key)
        await SwarmTaskSignature.ClientAdapter.afill_swarm(swarm_task)
    except Exception as e:
        ctx.log(f"MAJOR - Error in swarm item failed")
        raise


async def fill_swarm_running_tasks(msg: SwarmMessage, ctx: Context):
    async with SwarmTaskSignature.alock_from_key(
        msg.swarm_task_id, action=SWARM_ACTION_FILL
    ) as swarm_task:
        invoker = HatchetInvoker.from_no_task(msg, msg.swarm_task_id)
        if swarm_task.has_swarm_failed():
            ctx.log(f"Swarm failed too much {msg.swarm_task_id}")

            if swarm_task is None or swarm_task.has_published_errors():
                ctx.log(
                    f"Swarm {msg.swarm_task_id} was deleted already deleted or failed"
                )
                return
            await swarm_task.interrupt()
            await invoker.task_failed(
                EmptyModel(), RuntimeError("Swarm failed too much")
            )
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
            await invoker.task_success(EmptyModel())
            ctx.log(f"Swarm item done - closed swarm {swarm_task.key}")
