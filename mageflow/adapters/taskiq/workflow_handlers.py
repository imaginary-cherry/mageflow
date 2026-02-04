"""
TaskIQ-specific workflow handlers for chain and swarm.

These functions adapt the existing chain/swarm workflow logic to work
with TaskIQ's model (no ctx parameter, different logging, etc.).

The handlers use the adapter's logging and task triggering capabilities
instead of Hatchet's ctx methods.
"""
from typing import TYPE_CHECKING, cast
import logging

import rapyer

from mageflow.chain.consts import CHAIN_TASK_ID_NAME
from mageflow.chain.messages import ChainCallbackMessage
from mageflow.chain.model import ChainTaskSignature
from mageflow.signature.consts import TASK_ID_PARAM_NAME
from mageflow.signature.model import TaskSignature
from mageflow.swarm.consts import (
    SWARM_TASK_ID_PARAM_NAME,
    SWARM_ITEM_TASK_ID_PARAM_NAME,
    SWARM_FILL_TASK,
    SWARM_ACTION_FILL,
)
from mageflow.swarm.messages import SwarmResultsMessage, SwarmMessage
from mageflow.swarm.model import SwarmTaskSignature, BatchItemTaskSignature

if TYPE_CHECKING:
    from mageflow.adapters.taskiq.adapter import TaskIQAdapter

logger = logging.getLogger(__name__)


def _log(adapter: "TaskIQAdapter", message: str):
    """Log using standard logging (TaskIQ doesn't have ctx.log)."""
    logger.info(message)


def _get_task_data(msg: dict) -> dict:
    """Extract Mageflow task data from message."""
    return msg.get("_mageflow_task_data", {})


async def handle_chain_end(msg: dict, adapter: "TaskIQAdapter"):
    """
    Chain completion handler adapted for TaskIQ.

    This replicates the logic from chain/workflows.py:chain_end_task
    but uses TaskIQ's model instead of Hatchet's ctx.
    """
    try:
        task_data = _get_task_data(msg)
        current_task_id = task_data.get(TASK_ID_PARAM_NAME)

        chain_task_id = msg.get("chain_task_id")
        chain_results = msg.get("chain_results")

        chain_task_signature = await ChainTaskSignature.get_safe(chain_task_id)

        if chain_task_signature is None:
            _log(adapter, f"Chain task {chain_task_id} already removed, skipping")
            return

        _log(adapter, f"Chain task done {chain_task_signature.task_name}")

        # Calling success callback from chain task
        await chain_task_signature.activate_success(chain_results)
        _log(adapter, f"Chain task success {chain_task_signature.task_name}")

        # Remove tasks
        await chain_task_signature.remove(with_success=False)
        if current_task_id:
            await TaskSignature.remove_from_key(current_task_id)
    except Exception as e:
        _log(adapter, f"MAJOR - infrastructure error in chain end task: {e}")
        raise


async def handle_chain_error(msg: dict, adapter: "TaskIQAdapter"):
    """
    Chain error handler adapted for TaskIQ.

    This replicates the logic from chain/workflows.py:chain_error_task
    but uses TaskIQ's model instead of Hatchet's ctx.
    """
    try:
        chain_task_id = msg.get(CHAIN_TASK_ID_NAME)
        task_data = _get_task_data(msg)
        current_task_id = task_data.get(TASK_ID_PARAM_NAME)

        chain_signature = await ChainTaskSignature.get_safe(chain_task_id)

        if chain_signature is None:
            _log(adapter, f"Chain task {chain_task_id} already removed, skipping")
            return

        _log(
            adapter,
            f"Chain task failed {chain_signature.task_name} on task id - {current_task_id}",
        )

        # Calling error callback from chain task
        await chain_signature.activate_error(msg)
        _log(adapter, f"Chain task error {chain_signature.task_name}")

        # Remove tasks
        await chain_signature.remove(with_error=False)
        if current_task_id:
            await TaskSignature.remove_from_key(current_task_id)
        _log(adapter, f"Clean redis from chain tasks {chain_signature.task_name}")
    except Exception as e:
        _log(adapter, f"MAJOR - infrastructure error in chain error task: {e}")
        raise


async def handle_swarm_start(msg: dict, adapter: "TaskIQAdapter"):
    """
    Swarm start handler adapted for TaskIQ.

    This replicates the logic from swarm/workflows.py:swarm_start_tasks
    but uses TaskIQ's model instead of Hatchet's ctx.
    """
    try:
        _log(adapter, f"Swarm task started {msg}")
        swarm_task_id = msg.get(SWARM_TASK_ID_PARAM_NAME)
        swarm_task = await SwarmTaskSignature.get_safe(swarm_task_id)

        if swarm_task.has_swarm_started:
            _log(adapter, f"Swarm task started but already running {msg}")
            return

        # Create workflow adapter for triggering fill task
        fill_swarm_msg = {"swarm_task_id": swarm_task_id}
        await swarm_task.tasks_left_to_run.aextend(swarm_task.tasks)

        tasks = await rapyer.afind(*swarm_task.tasks)
        tasks = cast(list[BatchItemTaskSignature], tasks)
        original_tasks = await rapyer.afind(*[task.original_task_id for task in tasks])
        original_tasks = cast(list[TaskSignature], original_tasks)

        async with swarm_task.apipeline():
            for task in original_tasks:
                await task.aupdate_real_task_kwargs(**swarm_task.kwargs)

        # Trigger fill task
        workflow = adapter.workflow(name=SWARM_FILL_TASK)
        await workflow.aio_run(fill_swarm_msg)

        _log(
            adapter,
            f"Swarm task started running {swarm_task.config.max_concurrency} tasks",
        )
    except Exception:
        _log(adapter, f"MAJOR - Error in swarm start tasks")
        raise


async def handle_swarm_item_done(msg: dict, adapter: "TaskIQAdapter"):
    """
    Swarm item completion handler adapted for TaskIQ.

    This replicates the logic from swarm/workflows.py:swarm_item_done
    but uses TaskIQ's model instead of Hatchet's ctx.
    """
    task_data = _get_task_data(msg)
    task_key = task_data.get(TASK_ID_PARAM_NAME)

    try:
        swarm_task_id = msg.get("swarm_task_id")
        swarm_item_id = msg.get("swarm_item_id")
        mageflow_results = msg.get("mageflow_results")

        _log(adapter, f"Swarm item done {swarm_item_id}")

        # Update swarm tasks
        swarm_task = await SwarmTaskSignature.aget(swarm_task_id)

        _log(adapter, f"Swarm item done {swarm_item_id} - saving results")
        await swarm_task.finish_task(swarm_item_id, mageflow_results)

        # Publish next tasks
        fill_swarm_msg = {"swarm_task_id": swarm_task_id}
        workflow = adapter.workflow(name=SWARM_FILL_TASK)
        await workflow.aio_run(fill_swarm_msg)
    except Exception as e:
        _log(adapter, f"MAJOR - Error in swarm item done")
        raise
    finally:
        if task_key:
            await TaskSignature.remove_from_key(task_key)


async def handle_swarm_item_failed(msg: dict, adapter: "TaskIQAdapter"):
    """
    Swarm item failure handler adapted for TaskIQ.

    This replicates the logic from swarm/workflows.py:swarm_item_failed
    but uses TaskIQ's model instead of Hatchet's ctx.
    """
    task_data = _get_task_data(msg)
    task_key = task_data.get(TASK_ID_PARAM_NAME)

    try:
        swarm_task_key = msg.get(SWARM_TASK_ID_PARAM_NAME)
        swarm_item_key = msg.get(SWARM_ITEM_TASK_ID_PARAM_NAME)

        _log(adapter, f"Swarm item failed {swarm_item_key}")

        # Check if the swarm should end
        swarm_task = await SwarmTaskSignature.get_safe(swarm_task_key)
        await swarm_task.task_failed(swarm_item_key)

        fill_swarm_msg = {"swarm_task_id": swarm_task_key}
        workflow = adapter.workflow(name=SWARM_FILL_TASK)
        await workflow.aio_run(fill_swarm_msg)
    except Exception as e:
        _log(adapter, f"MAJOR - Error in swarm item failed")
        raise
    finally:
        if task_key:
            await TaskSignature.remove_from_key(task_key)


async def handle_swarm_fill(msg: dict, adapter: "TaskIQAdapter"):
    """
    Swarm fill handler adapted for TaskIQ.

    This replicates the logic from swarm/workflows.py:fill_swarm_running_tasks
    but uses TaskIQ's model instead of Hatchet's ctx.
    """
    from hatchet_sdk.runnables.types import EmptyModel

    swarm_task_id = msg.get("swarm_task_id")

    async with SwarmTaskSignature.alock_from_key(
        swarm_task_id, action=SWARM_ACTION_FILL
    ) as swarm_task:
        if swarm_task.has_swarm_failed():
            _log(adapter, f"Swarm failed too much {swarm_task_id}")
            swarm_task = await SwarmTaskSignature.get_safe(swarm_task_id)
            if swarm_task is None or swarm_task.has_published_errors():
                _log(
                    adapter,
                    f"Swarm {swarm_task_id} was deleted already deleted or failed",
                )
                return
            await swarm_task.interrupt()
            await swarm_task.activate_error(EmptyModel())
            await swarm_task.remove(with_error=False)
            await swarm_task.failed()
            return

        num_task_started = await swarm_task.fill_running_tasks()
        if num_task_started:
            _log(
                adapter, f"Swarm item started new task {num_task_started}/{swarm_task.key}"
            )
        else:
            _log(adapter, f"Swarm item no new task to run in {swarm_task.key}")

        # Check if the swarm should end
        not_yet_published = not swarm_task.has_published_callback()
        is_swarm_finished_running = await swarm_task.is_swarm_done()
        if is_swarm_finished_running and not_yet_published:
            _log(adapter, f"Swarm item done - closing swarm {swarm_task.key}")
            await swarm_task.activate_success(msg)
            await swarm_task.done()
            _log(adapter, f"Swarm item done - closed swarm {swarm_task.key}")
