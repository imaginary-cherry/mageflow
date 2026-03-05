from dataclasses import dataclass
from logging import Logger
from unittest.mock import MagicMock

import pytest_asyncio

import mageflow
from mageflow.chain.messages import ChainCallbackMessage, ChainErrorMessage
from mageflow.swarm.messages import FillSwarmMessage
from tests.integration.hatchet.models import ContextMessage, MessageWithResult
from thirdmagic.chain.model import ChainTaskSignature
from thirdmagic.clients.lifecycle import BaseLifecycle
from thirdmagic.swarm.model import SwarmConfig, SwarmTaskSignature
from thirdmagic.task import TaskSignature


@dataclass
class CompletedSwarmWithSuccessCallback:
    swarm_task: SwarmTaskSignature
    swarm_task_id: str
    max_tasks: int | None
    lifecycle: BaseLifecycle
    logger: MagicMock
    sub_tasks: list[TaskSignature]
    success: list[TaskSignature]
    error: list[TaskSignature]


@dataclass
class SwarmTestSetup:
    swarm_task: SwarmTaskSignature
    tasks: list[TaskSignature]
    item_task: TaskSignature | None = None
    logger: MagicMock | None = None


@pytest_asyncio.fixture
async def completed_swarm_with_success_callback(
    mock_task_def, adapter_with_lifecycle, mock_logger
):
    # Arrange
    success_callback = await mageflow.asign(
        "unittest_success_callback_task", model_validators=MessageWithResult
    )
    error_callback = await mageflow.asign(
        "unittest_error_callback_task", model_validators=MessageWithResult
    )
    error_callback2 = await mageflow.asign(
        "unittest_error_callback_task", model_validators=MessageWithResult
    )

    error_callback = [error_callback, error_callback2]
    success = [success_callback]
    swarm_task = await mageflow.aswarm(
        task_name="test_swarm_completed_with_callback",
        model_validators=ContextMessage,
        config=SwarmConfig(max_concurrency=1),
        success_callbacks=success,
        error_callbacks=error_callback,
    )
    original_task = await mageflow.asign("item_task")
    task = await swarm_task.add_task(original_task)

    async with swarm_task.apipeline():
        swarm_task.tasks_left_to_run.remove_range(0, len(swarm_task.tasks_left_to_run))
        swarm_task.finished_tasks.append(task.key)
        swarm_task.is_swarm_closed = True

    msg = FillSwarmMessage(swarm_task_id=swarm_task.key)
    lifecycle = await adapter_with_lifecycle.lifecycle_from_signature(
        msg, MagicMock(), swarm_task.key
    )

    return CompletedSwarmWithSuccessCallback(
        swarm_task=swarm_task,
        swarm_task_id=swarm_task.key,
        max_tasks=msg.max_tasks,
        lifecycle=lifecycle,
        logger=mock_logger,
        success=success,
        error=error_callback,
        sub_tasks=[original_task],
    )


async def create_swarm_item_test_setup(
    num_tasks: int = 3,
    max_concurrency: int = 1,
    stop_after_n_failures: int | None = 2,
    current_running: int = 1,
    tasks_left_indices: list[int] | None = None,
    failed_indices: list[int] | None = None,
    finished_indices: list[int] | None = None,
    logger: MagicMock | None = None,
) -> SwarmTestSetup:
    swarm_task = await mageflow.aswarm(
        task_name="test_swarm",
        model_validators=ContextMessage,
        config=SwarmConfig(
            max_concurrency=max_concurrency,
            stop_after_n_failures=stop_after_n_failures,
        ),
    )
    original_tasks = [
        await mageflow.asign(f"test_task_{i}", model_validators=ContextMessage)
        for i in range(num_tasks)
    ]
    tasks = await swarm_task.add_tasks(original_tasks)

    async with swarm_task.apipeline():
        swarm_task.current_running_tasks = current_running
        swarm_task.tasks_left_to_run.remove_range(0, len(swarm_task.tasks_left_to_run))
        if failed_indices:
            swarm_task.failed_tasks.extend([tasks[i].key for i in failed_indices])
        if finished_indices:
            swarm_task.finished_tasks.extend([tasks[i].key for i in finished_indices])

    if tasks_left_indices:
        await swarm_task.tasks_left_to_run.aextend(
            [tasks[i].key for i in tasks_left_indices]
        )

    item_task = await mageflow.asign("item_task", model_validators=ContextMessage)

    return SwarmTestSetup(
        swarm_task=swarm_task,
        tasks=tasks,
        item_task=item_task,
        logger=logger or MagicMock(spec=Logger),
    )


@dataclass
class ChainTestSetup:
    chain_signature: ChainTaskSignature
    chain_tasks: list[TaskSignature]
    success_callback: TaskSignature
    error_callback: TaskSignature
    lifecycle_manager: BaseLifecycle
    logger: MagicMock
    msg: ChainCallbackMessage
    error_msg: ChainErrorMessage


async def create_chain_test_setup(
    num_chain_tasks: int = 3,
    results: dict | None = None,
    adapter=None,
    logger: MagicMock | None = None,
) -> ChainTestSetup:
    # Arrange
    chain_tasks = [
        await mageflow.asign(f"chain_task_{i}", model_validators=ContextMessage)
        for i in range(num_chain_tasks)
    ]

    # Arrange
    success_callback = await mageflow.asign(
        "chain_success_callback", model_validators=MessageWithResult
    )
    error_callback = await mageflow.asign(
        "chain_error_callback", model_validators=MessageWithResult
    )

    # Arrange
    chain_signature = await mageflow.achain(
        [task.key for task in chain_tasks],
        success=success_callback,
        error=error_callback,
    )

    # Arrange
    msg = ChainCallbackMessage(
        chain_results=results or {"status": "done"},
        chain_task_id=chain_signature.key,
    )

    # Arrange
    error_msg = ChainErrorMessage(
        chain_task_id=chain_signature.key,
        error="test error",
        original_msg={"status": "error"},
        error_task_key=chain_tasks[0].key,
    )

    # Arrange
    _logger = logger or MagicMock(spec=Logger)
    lifecycle_manager = (
        await adapter.lifecycle_from_signature(msg, MagicMock(), chain_signature.key)
        if adapter
        else MagicMock(spec=BaseLifecycle)
    )

    return ChainTestSetup(
        chain_signature=chain_signature,
        chain_tasks=chain_tasks,
        success_callback=success_callback,
        error_callback=error_callback,
        lifecycle_manager=lifecycle_manager,
        logger=_logger,
        msg=msg,
        error_msg=error_msg,
    )
