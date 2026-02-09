import logging

from mageflow.chain.consts import CHAIN_TASK_ID_NAME
from mageflow.chain.messages import ChainCallbackMessage
from mageflow.chain.model import ChainTaskSignature
from mageflow.signature.consts import TASK_ID_PARAM_NAME
from mageflow.signature.model import TaskSignature

logger = logging.getLogger(__name__)


def _create_invoker(msg, ctx):
    from mageflow.startup import mageflow_config

    return mageflow_config.adapter.create_invoker(msg, ctx)


async def chain_end_task(msg: ChainCallbackMessage, ctx):
    try:
        invoker = _create_invoker(msg, ctx)
        task_data = invoker.task_ctx
        current_task_id = task_data[TASK_ID_PARAM_NAME]

        chain_task_signature = await ChainTaskSignature.get_safe(msg.chain_task_id)

        if chain_task_signature is None:
            await invoker.log(f"Chain task {msg.chain_task_id} already removed, skipping")
            return

        await invoker.log(f"Chain task done {chain_task_signature.task_name}")

        # Calling error callback from a chain task - This is done before deletion because a deletion error should not disturb the workflow
        await chain_task_signature.activate_success(msg.chain_results)
        await invoker.log(f"Chain task success {chain_task_signature.task_name}")

        # Remove tasks
        await chain_task_signature.remove(with_success=False)
        await TaskSignature.remove_from_key(current_task_id)
    except Exception as e:
        await invoker.log(f"MAJOR - infrastructure error in chain end task: {e}")
        raise


# This task needs to be added as a workflow
async def chain_error_task(msg, ctx):
    try:
        chain_task_id = msg.model_dump()[CHAIN_TASK_ID_NAME]
        invoker = _create_invoker(msg, ctx)
        task_data = invoker.task_ctx
        current_task_id = task_data[TASK_ID_PARAM_NAME]
        chain_signature = await ChainTaskSignature.get_safe(chain_task_id)

        if chain_signature is None:
            await invoker.log(f"Chain task {chain_task_id} already removed, skipping")
            return

        await invoker.log(
            f"Chain task failed {chain_signature.task_name} on task id - {current_task_id}"
        )

        # Calling error callback from chain task
        await chain_signature.activate_error(msg)
        await invoker.log(f"Chain task error {chain_signature.task_name}")

        # Remove tasks
        await chain_signature.remove(with_error=False)
        await TaskSignature.remove_from_key(current_task_id)
        await invoker.log(f"Clean redis from chain tasks {chain_signature.task_name}")
    except Exception as e:
        await invoker.log(f"MAJOR - infrastructure error in chain error task: {e}")
        raise
