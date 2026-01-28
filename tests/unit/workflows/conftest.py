from dataclasses import dataclass
from unittest.mock import MagicMock

import pytest_asyncio

import mageflow
from mageflow.chain.messages import ChainCallbackMessage
from mageflow.chain.model import ChainTaskSignature
from mageflow.signature.model import TaskSignature
from mageflow.swarm.messages import SwarmMessage
from mageflow.swarm.model import SwarmTaskSignature, SwarmConfig, BatchItemTaskSignature
from tests.integration.hatchet.models import ContextMessage, MessageWithResult
from tests.unit.conftest import create_mock_context_with_metadata


@dataclass
class CompletedSwarmWithSuccessCallback:
    swarm_task: SwarmTaskSignature
    ctx: MagicMock
    msg: SwarmMessage


@dataclass
class SwarmTestSetup:
    swarm_task: SwarmTaskSignature
    original_tasks: list[TaskSignature]
    batch_tasks: list[BatchItemTaskSignature]
    item_task: TaskSignature | None = None
    ctx: MagicMock | None = None


@pytest_asyncio.fixture
async def completed_swarm_with_success_callback():
    # Arrange
    success_callback = await mageflow.sign(
        "unittest_success_callback_task", model_validators=MessageWithResult
    )
    error_callback = await mageflow.sign(
        "unittest_error_callback_task", model_validators=MessageWithResult
    )
    error_callback2 = await mageflow.sign(
        "unittest_error_callback_task", model_validators=MessageWithResult
    )

    swarm_task = await mageflow.swarm(
        task_name="test_swarm_completed_with_callback",
        model_validators=ContextMessage,
        config=SwarmConfig(max_concurrency=1),
        success_callbacks=[success_callback],
        error_callbacks=[error_callback, error_callback2],
    )
    original_task = await mageflow.sign("item_task")
    batch_task = await swarm_task.add_task(original_task)

    async with swarm_task.apipeline():
        swarm_task.finished_tasks.append(batch_task.key)

    async with swarm_task.alock() as locked_swarm:
        await locked_swarm.aupdate(is_swarm_closed=True)

    ctx = create_mock_context_with_metadata()
    msg = SwarmMessage(swarm_task_id=swarm_task.key)

    return CompletedSwarmWithSuccessCallback(swarm_task=swarm_task, ctx=ctx, msg=msg)


async def create_swarm_item_test_setup(
    num_tasks: int = 3,
    max_concurrency: int = 1,
    stop_after_n_failures: int | None = 2,
    current_running: int = 1,
    tasks_left_indices: list[int] | None = None,
    failed_indices: list[int] | None = None,
    finished_indices: list[int] | None = None,
) -> SwarmTestSetup:
    swarm_task = await mageflow.swarm(
        task_name="test_swarm",
        model_validators=ContextMessage,
        config=SwarmConfig(
            max_concurrency=max_concurrency,
            stop_after_n_failures=stop_after_n_failures,
        ),
    )
    original_tasks = [
        await mageflow.sign(f"test_task_{i}", model_validators=ContextMessage)
        for i in range(num_tasks)
    ]
    batch_tasks = [await swarm_task.add_task(task) for task in original_tasks]

    async with swarm_task.apipeline():
        swarm_task.current_running_tasks = current_running
        swarm_task.tasks.extend([t.key for t in batch_tasks])
        if failed_indices:
            swarm_task.failed_tasks.extend([batch_tasks[i].key for i in failed_indices])
        if finished_indices:
            swarm_task.finished_tasks.extend(
                [batch_tasks[i].key for i in finished_indices]
            )

    if tasks_left_indices:
        await swarm_task.tasks_left_to_run.aextend(
            [batch_tasks[i].key for i in tasks_left_indices]
        )

    item_task = await mageflow.sign("item_task", model_validators=ContextMessage)
    ctx = create_mock_context_with_metadata(task_id=item_task.key)

    return SwarmTestSetup(
        swarm_task=swarm_task,
        original_tasks=original_tasks,
        batch_tasks=batch_tasks,
        item_task=item_task,
        ctx=ctx,
    )


@dataclass
class ChainTestSetup:
    chain_signature: ChainTaskSignature
    chain_tasks: list[TaskSignature]
    current_task: TaskSignature
    success_callback: TaskSignature
    error_callback: TaskSignature
    ctx: MagicMock
    msg: ChainCallbackMessage


async def create_chain_test_setup(
    num_chain_tasks: int = 3,
    results: dict | None = None,
) -> ChainTestSetup:
    # Arrange
    chain_tasks = [
        await mageflow.sign(f"chain_task_{i}", model_validators=ContextMessage)
        for i in range(num_chain_tasks)
    ]

    # Arrange
    success_callback = await mageflow.sign(
        "chain_success_callback", model_validators=MessageWithResult
    )
    error_callback = await mageflow.sign(
        "chain_error_callback", model_validators=MessageWithResult
    )

    # Arrange
    chain_signature = await mageflow.chain(
        [task.key for task in chain_tasks],
        success=success_callback,
        error=error_callback,
    )

    # Arrange
    current_task = await mageflow.sign("current_task", model_validators=ContextMessage)

    # Arrange
    ctx = create_mock_context_with_metadata(task_id=current_task.key)

    # Arrange
    msg = ChainCallbackMessage(
        chain_results=results or {"status": "done"},
        chain_task_id=chain_signature.key,
    )

    return ChainTestSetup(
        chain_signature=chain_signature,
        chain_tasks=chain_tasks,
        current_task=current_task,
        success_callback=success_callback,
        error_callback=error_callback,
        ctx=ctx,
        msg=msg,
    )
