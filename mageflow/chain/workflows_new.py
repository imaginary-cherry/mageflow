"""
Chain workflow handlers - task manager agnostic version.

This module provides the chain task handlers that work with any task manager.
They use TaskContext instead of Hatchet's Context directly.
"""
from typing import TYPE_CHECKING

from pydantic import BaseModel

from mageflow.adapters.protocols import TaskContext
from mageflow.chain.consts import CHAIN_TASK_ID_NAME
from mageflow.chain.messages import ChainCallbackMessage
from mageflow.chain.model import ChainTaskSignature
from mageflow.invokers.base import BaseInvoker
from mageflow.signature.consts import TASK_ID_PARAM_NAME
from mageflow.signature.model import TaskSignature

if TYPE_CHECKING:
    from mageflow.adapters.protocols import TaskManagerAdapter


async def chain_end_task_handler(
    msg: ChainCallbackMessage,
    task_context: TaskContext,
    invoker: BaseInvoker,
):
    """
    Handle chain completion - task manager agnostic.

    Args:
        msg: The chain callback message
        task_context: Normalized task context
        invoker: Task invoker for lifecycle management
    """
    try:
        task_data = invoker.task_ctx
        current_task_id = task_data[TASK_ID_PARAM_NAME]

        chain_task_signature = await ChainTaskSignature.get_safe(msg.chain_task_id)

        if chain_task_signature is None:
            task_context.log(f"Chain task {msg.chain_task_id} already removed, skipping")
            return

        task_context.log(f"Chain task done {chain_task_signature.task_name}")

        # Calling error callback from a chain task
        # This is done before deletion because a deletion error should not disturb the workflow
        await chain_task_signature.activate_success(msg.chain_results)
        task_context.log(f"Chain task success {chain_task_signature.task_name}")

        # Remove tasks
        await chain_task_signature.remove(with_success=False)
        await TaskSignature.remove_from_key(current_task_id)
    except Exception as e:
        task_context.log(f"MAJOR - infrastructure error in chain end task: {e}")
        raise


async def chain_error_task_handler(
    msg: BaseModel,
    task_context: TaskContext,
    invoker: BaseInvoker,
):
    """
    Handle chain error - task manager agnostic.

    Args:
        msg: The error message
        task_context: Normalized task context
        invoker: Task invoker for lifecycle management
    """
    try:
        msg_data = msg.model_dump() if hasattr(msg, "model_dump") else msg
        chain_task_id = msg_data[CHAIN_TASK_ID_NAME]
        task_data = invoker.task_ctx
        current_task_id = task_data[TASK_ID_PARAM_NAME]
        chain_signature = await ChainTaskSignature.get_safe(chain_task_id)

        if chain_signature is None:
            task_context.log(f"Chain task {chain_task_id} already removed, skipping")
            return

        task_context.log(
            f"Chain task failed {chain_signature.task_name} on task id - {current_task_id}"
        )

        # Calling error callback from chain task
        await chain_signature.activate_error(msg)
        task_context.log(f"Chain task error {chain_signature.task_name}")

        # Remove tasks
        await chain_signature.remove(with_error=False)
        await TaskSignature.remove_from_key(current_task_id)
        task_context.log(f"Clean redis from chain tasks {chain_signature.task_name}")
    except Exception as e:
        task_context.log(f"MAJOR - infrastructure error in chain error task: {e}")
        raise
