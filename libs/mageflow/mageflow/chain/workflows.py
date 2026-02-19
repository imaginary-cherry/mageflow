from logging import Logger
from typing import Any

from rapyer.fields import RapyerKey
from thirdmagic.clients.lifecycle import BaseLifecycle


async def chain_end_task(
    chain_results: Any, lifecycle_manager: BaseLifecycle, logger: Logger
):
    try:
        if lifecycle_manager is None:
            logger.warning(f"Chain task {lifecycle_manager} already removed, skipping")
            return

        logger.info(f"Chain task done {lifecycle_manager}")

        # Calling error callback from a chain task - This is done before deletion because a deletion error should not disturb the workflow
        await lifecycle_manager.task_success(chain_results)
        logger.info(f"Chain task success {lifecycle_manager}")
    except Exception as e:
        logger.exception(f"MAJOR - infrastructure error in chain end task: {e}")
        raise


# This task needs to be added as a workflow
async def chain_error_task(
    chain_task_id: RapyerKey,
    original_msg: dict,
    error: str,
    lifecycle_manager: BaseLifecycle,
    logger: Logger,
):
    try:
        if lifecycle_manager is None:
            logger.warning(f"Chain task {chain_task_id} already removed, skipping")
            return

        logger.info(f"Chain task failed {lifecycle_manager}")

        # Calling error callback from chain task
        await lifecycle_manager.task_failed(original_msg, Exception(error))
        logger.info(f"Clean redis from chain tasks {lifecycle_manager}")
    except Exception as e:
        logger.exception(f"MAJOR - infrastructure error in chain error task: {e}")
        raise
