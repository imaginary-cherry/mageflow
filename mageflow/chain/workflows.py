import asyncio

from hatchet_sdk import Context

from mageflow.chain.messages import ChainCallbackMessage
from mageflow.chain.model import ChainTaskSignature
from mageflow.invokers.hatchet import HatchetInvoker
from mageflow.signature.consts import TASK_ID_PARAM_NAME
from mageflow.signature.model import TaskSignature


async def chain_end_task(msg: ChainCallbackMessage, ctx: Context):
    try:
        task_data = HatchetInvoker(msg, ctx).task_ctx
        current_task_id = task_data[TASK_ID_PARAM_NAME]

        chain_task_signature = await ChainTaskSignature.get_safe(msg.chain_task_id)
        ctx.log(f"Chain task done {chain_task_signature.task_name}")

        # Calling error callback from a chain task - This is done before deletion because a deletion error should not disturb the workflow
        await chain_task_signature.activate_success(msg.chain_results)
        ctx.log(f"Chain task success {chain_task_signature.task_name}")

        # Remove tasks
        await asyncio.gather(
            chain_task_signature.remove(with_success=False),
            TaskSignature.adelete(current_task_id),
        )
    except Exception as e:
        ctx.log(f"MAJOR - infrastructure error in chain end task: {e}")
        raise


# This task needs to be added as a workflow
async def chain_error_task(msg: ChainCallbackMessage, ctx: Context):
    try:
        task_data = HatchetInvoker(msg, ctx).task_ctx
        current_task_id = task_data[TASK_ID_PARAM_NAME]
        chain_signature = await ChainTaskSignature.get_safe(msg.chain_task_id)
        ctx.log(
            f"Chain task failed {chain_signature.task_name} on task id - {current_task_id}"
        )

        # Calling error callback from chain task
        await chain_signature.activate_error(msg)
        ctx.log(f"Chain task error {chain_signature.task_name}")

        # Remove tasks
        await asyncio.gather(
            chain_signature.remove(with_error=False),
            TaskSignature.adelete(current_task_id),
        )
        ctx.log(f"Clean redis from chain tasks {chain_signature.task_name}")
    except Exception as e:
        ctx.log(f"MAJOR - infrastructure error in chain error task: {e}")
        raise
