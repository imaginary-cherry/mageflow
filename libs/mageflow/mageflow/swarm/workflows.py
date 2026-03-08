from logging import Logger
from typing import Any, Optional, cast

import rapyer
from rapyer.fields import RapyerKey

from thirdmagic.clients.lifecycle import BaseLifecycle
from thirdmagic.signature import Signature
from thirdmagic.swarm import PublishState
from thirdmagic.swarm.consts import SWARM_MESSAGE_PARAM_NAME
from thirdmagic.swarm.model import SwarmTaskSignature


async def swarm_item_done(
    swarm_task_id: RapyerKey,
    swarm_item_id: RapyerKey,
    mageflow_results: Any,
    logger: Logger,
):
    try:
        logger.info(f"Swarm item done {swarm_item_id}")

        # Update swarm tasks
        swarm_task = await SwarmTaskSignature.aget(swarm_task_id)

        logger.info(f"Swarm item done {swarm_item_id} - saving results")
        await swarm_task.finish_task(swarm_item_id, mageflow_results)

        # Publish next tasks
        await SwarmTaskSignature.ClientAdapter.afill_swarm(swarm_task)
    except Exception as e:
        logger.exception(f"MAJOR - Error in swarm start item done")
        raise


async def swarm_item_failed(
    swarm_task_id: RapyerKey, swarm_item_id: RapyerKey, error: str, logger: Logger
):
    try:
        logger.info(f"Swarm item failed {swarm_item_id} - {error}")
        # Check if the swarm should end
        swarm_task = await SwarmTaskSignature.aget(swarm_task_id)
        await swarm_task.task_failed(swarm_item_id)
        await SwarmTaskSignature.ClientAdapter.afill_swarm(swarm_task)
    except Exception as e:
        logger.exception(f"MAJOR - Error in swarm item failed")
        raise


async def fill_swarm_running_tasks(
    swarm_task_id: RapyerKey,
    max_tasks: Optional[int],
    lifecycle: BaseLifecycle,
    logger: Logger,
):
    logger.info(f"Filling swarm {swarm_task_id} with {max_tasks}")
    swarm_task = await SwarmTaskSignature.afind_one(swarm_task_id)
    if swarm_task is None:
        logger.info(
            f"Swarm {swarm_task_id} not found, it was probably already finished and deleted."
        )
        return

    if swarm_task.has_swarm_failed():
        logger.info(f"Swarm failed too much {swarm_task_id}")

        if swarm_task is None or swarm_task.has_published_errors():
            logger.info(f"Swarm {swarm_task_id} was deleted already deleted or failed")
            return
        await swarm_task.interrupt()
        await lifecycle.task_failed({}, RuntimeError("Swarm failed too much"))
        return

    tasks_started = await fill_running_tasks(swarm_task, max_tasks=max_tasks)
    num_task_started = len(tasks_started)
    if num_task_started:
        logger.info(f"Swarm item started new task {num_task_started}/{swarm_task.key}")
    else:
        logger.info(f"Swarm item no new task to run in {swarm_task.key}")

    # Check if the swarm should end
    not_yet_published = not swarm_task.has_published_callback()
    is_swarm_finished_running = await swarm_task.is_swarm_done()
    if is_swarm_finished_running and not_yet_published:
        logger.info(f"Swarm item done - closing swarm {swarm_task.key}")
        await lifecycle.task_success(None)
        logger.info(f"Swarm item done - closed swarm {swarm_task.key}")
    logger.info(f"Swarm item done - done filling swarm {swarm_task.key}")


async def fill_running_tasks(
    swarm, max_tasks: Optional[int] = None, **pub_kwargs
) -> list[Signature]:
    publish_state = await PublishState.aget(swarm.publishing_state_id)
    task_ids_to_run = list(publish_state.task_ids)
    num_of_task_to_run = len(task_ids_to_run)
    if not task_ids_to_run:
        resource_to_run = swarm.config.max_concurrency - swarm.current_running_tasks
        if max_tasks is not None:
            resource_to_run = min(max_tasks, resource_to_run)
        if resource_to_run <= 0:
            return []
        num_of_task_to_run = min(resource_to_run, len(swarm.tasks_left_to_run))
        async with swarm.apipeline():
            task_ids_to_run = swarm.tasks_left_to_run[:num_of_task_to_run]
            publish_state.task_ids.extend(task_ids_to_run)
            swarm.tasks_left_to_run.remove_range(0, num_of_task_to_run)

    if task_ids_to_run:
        tasks = await rapyer.afind(*task_ids_to_run)
        tasks = cast(list[Signature], tasks)

        # Update the kwargs locally, so swarm kwargs wont be duplicated on redis but still sent to task
        swarm_kwargs = swarm.kwargs.copy()
        swarm_msg = swarm_kwargs.pop(SWARM_MESSAGE_PARAM_NAME, None)
        for task in tasks:
            task.kwargs.update(**swarm_kwargs)

        await swarm.ClientAdapter.acall_signatures(
            tasks,
            swarm_msg,
            set_return_field=swarm.config.send_swarm_message_to_return_field,
            **pub_kwargs,
        )

        async with publish_state.apipeline():
            publish_state.task_ids.clear()
            swarm.current_running_tasks += num_of_task_to_run
        return tasks
    return []
