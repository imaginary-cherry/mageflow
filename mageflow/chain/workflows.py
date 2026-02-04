from hatchet_sdk import Context, EmptyModel

from mageflow.chain.messages import ChainCallbackMessage, ChainErrorMessage
from mageflow.invokers.hatchet import HatchetInvoker
from mageflow.signature.consts import TASK_ID_PARAM_NAME


async def chain_end_task(msg: ChainCallbackMessage, ctx: Context):
    try:
        invoker = HatchetInvoker.from_no_task(
            msg, {TASK_ID_PARAM_NAME: msg.chain_task_id}
        )
        chain_task_signature = await invoker.task_signature()

        if chain_task_signature is None:
            ctx.log(f"Chain task {msg.chain_task_id} already removed, skipping")
            return

        ctx.log(f"Chain task done {chain_task_signature.task_name}")

        # Calling error callback from a chain task - This is done before deletion because a deletion error should not disturb the workflow
        await invoker.task_success(msg.chain_results)
        ctx.log(f"Chain task success {chain_task_signature.task_name}")
    except Exception as e:
        ctx.log(f"MAJOR - infrastructure error in chain end task: {e}")
        raise


# This task needs to be added as a workflow
async def chain_error_task(msg: ChainErrorMessage, ctx: Context):
    try:
        invoker = HatchetInvoker.from_no_task(
            msg, {TASK_ID_PARAM_NAME: msg.chain_task_id}
        )
        chain_signature = await invoker.task_signature()

        if chain_signature is None:
            ctx.log(f"Chain task {chain_task_id} already removed, skipping")
            return

        ctx.log(f"Chain task failed {chain_signature.task_name}")

        # Calling error callback from chain task
        await invoker.task_failed(EmptyModel(**msg.original_msg), msg.error)
        ctx.log(f"Clean redis from chain tasks {chain_signature.task_name}")
    except Exception as e:
        ctx.log(f"MAJOR - infrastructure error in chain error task: {e}")
        raise
