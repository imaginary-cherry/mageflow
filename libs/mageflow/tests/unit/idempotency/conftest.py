from dataclasses import dataclass
from unittest.mock import MagicMock

import pytest_asyncio
from thirdmagic.clients.lifecycle import BaseLifecycle
from thirdmagic.signature import Signature
from thirdmagic.swarm.model import SwarmConfig, SwarmTaskSignature
from thirdmagic.swarm.state import PublishState

import mageflow
from mageflow.swarm.messages import (
    FillSwarmMessage,
    SwarmErrorMessage,
    SwarmResultsMessage,
)
from tests.integration.hatchet.models import ContextMessage
from tests.unit.conftest import SwarmItemDoneSetup


@dataclass
class FailedSwarmSetup:
    swarm_task: SwarmTaskSignature
    task: Signature
    swarm_task_id: str
    max_tasks: int | None
    lifecycle: BaseLifecycle
    logger: MagicMock


@dataclass
class CompletedSwarmSetup:
    swarm_task: SwarmTaskSignature
    task: Signature
    swarm_task_id: str
    max_tasks: int | None
    lifecycle: BaseLifecycle
    logger: MagicMock


@dataclass
class SwarmItemFailedSetup:
    swarm_task: SwarmTaskSignature
    task: Signature
    swarm_task_id: str
    swarm_item_id: str
    error: str
    logger: MagicMock


@pytest_asyncio.fixture
async def publish_state():
    state = PublishState()
    await state.asave()
    return state


@pytest_asyncio.fixture
async def failed_swarm_setup(mock_task_def, adapter_with_lifecycle, mock_logger):
    # Arrange
    swarm_task = await mageflow.aswarm(
        task_name="test_swarm_failed",
        model_validators=ContextMessage,
        config=SwarmConfig(max_concurrency=1, stop_after_n_failures=1),
    )
    original_task = await mageflow.asign("item_task")
    task = await swarm_task.add_task(original_task)
    async with swarm_task.apipeline():
        swarm_task.tasks_left_to_run.remove_range(0, len(swarm_task.tasks_left_to_run))
        swarm_task.failed_tasks.append(task.key)
        swarm_task.current_running_tasks += 1

    msg = FillSwarmMessage(swarm_task_id=swarm_task.key)
    lifecycle = await adapter_with_lifecycle.lifecycle_from_signature(
        msg, MagicMock(), swarm_task.key
    )

    return FailedSwarmSetup(
        swarm_task=swarm_task,
        task=task,
        swarm_task_id=swarm_task.key,
        max_tasks=msg.max_tasks,
        lifecycle=lifecycle,
        logger=mock_logger,
    )


@pytest_asyncio.fixture
async def completed_swarm_setup(mock_task_def, adapter_with_lifecycle, mock_logger):
    # Arrange
    swarm_task = await mageflow.aswarm(
        task_name="test_swarm_completed",
        model_validators=ContextMessage,
        config=SwarmConfig(max_concurrency=1),
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

    return CompletedSwarmSetup(
        swarm_task=swarm_task,
        task=task,
        swarm_task_id=swarm_task.key,
        max_tasks=msg.max_tasks,
        lifecycle=lifecycle,
        logger=mock_logger,
    )


@pytest_asyncio.fixture
async def swarm_item_failed_setup(swarm_setup):
    swarm_task, task, logger = swarm_setup
    msg = SwarmErrorMessage(
        swarm_task_id=swarm_task.key, swarm_item_id=task.key, error="test error"
    )

    return SwarmItemFailedSetup(
        swarm_task=swarm_task,
        task=task,
        swarm_task_id=msg.swarm_task_id,
        swarm_item_id=msg.swarm_item_id,
        error=msg.error,
        logger=logger,
    )


@pytest_asyncio.fixture
async def swarm_item_done_setup(swarm_setup):
    swarm_task, task, logger = swarm_setup
    msg = SwarmResultsMessage(
        mageflow_results=42,
        swarm_task_id=swarm_task.key,
        swarm_item_id=task.key,
    )

    return SwarmItemDoneSetup(swarm_task=swarm_task, task=task, logger=logger, msg=msg)
