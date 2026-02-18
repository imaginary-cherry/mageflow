from hatchet_sdk import Context, EmptyModel
from thirdmagic.chain import ChainTaskSignature

from mageflow.chain.messages import ChainCallbackMessage, ChainErrorMessage


async def chain_end_task(msg: ChainCallbackMessage, ctx: Context):
    try:
        lifecycle_manager = (
            await ChainTaskSignature.ClientAdapter.lifecycle_from_signature(
                msg, ctx, msg.chain_task_id
            )
        )

        if lifecycle_manager is None:
            ctx.log(f"Chain task {lifecycle_manager} already removed, skipping")
            return

        ctx.log(f"Chain task done {lifecycle_manager}")

        # Calling error callback from a chain task - This is done before deletion because a deletion error should not disturb the workflow
        await lifecycle_manager.task_success(msg.chain_results)
        ctx.log(f"Chain task success {lifecycle_manager}")
    except Exception as e:
        ctx.log(f"MAJOR - infrastructure error in chain end task: {e}")
        raise


# This task needs to be added as a workflow
async def chain_error_task(msg: ChainErrorMessage, ctx: Context):
    try:
        lifecycle_manager = (
            await ChainTaskSignature.ClientAdapter.lifecycle_from_signature(
                msg, ctx, msg.chain_task_id
            )
        )

        if lifecycle_manager is None:
            ctx.log(f"Chain task {msg.chain_task_id} already removed, skipping")
            return

        ctx.log(f"Chain task failed {lifecycle_manager}")

        # Calling error callback from chain task
        await invoker.task_failed(EmptyModel(**msg.original_msg), Exception(msg.error))
        ctx.log(f"Clean redis from chain tasks {chain_signature.task_name}")
        await lifecycle_manager.task_failed(
            EmptyModel(**msg.original_msg), Exception(msg.error)
        )
        ctx.log(f"Clean redis from chain tasks {lifecycle_manager}")
    except Exception as e:
        ctx.log(f"MAJOR - infrastructure error in chain error task: {e}")
        raise
