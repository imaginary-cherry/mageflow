import pytest

import thirdmagic
from tests.unit.messages import ContextMessage
from thirdmagic.swarm.model import SwarmConfig, SwarmTaskSignature
from thirdmagic.task import TaskSignature


@pytest.mark.asyncio
async def test_close_swarm_sets_is_swarm_closed_to_true_sanity(mock_task_def):
    # Arrange
    swarm_signature = await thirdmagic.swarm(task_name="test_swarm")
    task = await thirdmagic.sign("test_task")
    await swarm_signature.add_task(task, close_on_max_task=False)

    # Act
    result = await swarm_signature.close_swarm()

    # Assert
    reloaded = await SwarmTaskSignature.aget(swarm_signature.key)
    assert reloaded.is_swarm_closed is True
    mock_adapter.afill_swarm.assert_awaited_once_with(swarm_signature, max_tasks=0)


@pytest.mark.asyncio
async def test_close_swarm_calls_afill_swarm_when_all_tasks_finished(mock_adapter):
    # Arrange
    mock_adapter.afill_swarm.return_value = None
    task_1 = await thirdmagic.sign("task_1", model_validators=ContextMessage)
    task_2 = await thirdmagic.sign("task_2", model_validators=ContextMessage)
    swarm_signature = await thirdmagic.swarm(
        task_name="test_swarm",
        model_validators=ContextMessage,
        tasks=[task_1, task_2],
    )
    await swarm_signature.finish_task(task_1.key, "result_1")
    await swarm_signature.finish_task(task_2.key, "result_2")

    # Act
    await swarm_signature.close_swarm()

    # Assert
    mock_adapter.afill_swarm.assert_awaited_once_with(swarm_signature, max_tasks=0)


@pytest.mark.asyncio
async def test_close_swarm_calls_afill_swarm_when_all_tasks_failed(mock_adapter):
    # Arrange
    mock_adapter.afill_swarm.return_value = None
    task_1 = await thirdmagic.sign("task_1", model_validators=ContextMessage)
    task_2 = await thirdmagic.sign("task_2", model_validators=ContextMessage)
    swarm_signature = await thirdmagic.swarm(
        task_name="test_swarm",
        model_validators=ContextMessage,
        tasks=[task_1, task_2],
    )
    await swarm_signature.task_failed(task_1.key)
    await swarm_signature.task_failed(task_2.key)

    # Act
    await swarm_signature.close_swarm()

    # Assert
    mock_adapter.afill_swarm.assert_awaited_once_with(swarm_signature, max_tasks=0)


@pytest.mark.asyncio
async def test_close_swarm_calls_afill_swarm_when_mix_of_finished_and_failed(
    mock_adapter,
):
    # Arrange
    mock_adapter.afill_swarm.return_value = None
    task_1 = await thirdmagic.sign("task_1", model_validators=ContextMessage)
    task_2 = await thirdmagic.sign("task_2", model_validators=ContextMessage)
    swarm_signature = await thirdmagic.swarm(
        task_name="test_swarm",
        model_validators=ContextMessage,
        tasks=[task_1, task_2],
    )
    await swarm_signature.finish_task(task_1.key, "result_1")
    await swarm_signature.task_failed(task_2.key)

    # Act
    await swarm_signature.close_swarm()

    # Assert
    mock_adapter.afill_swarm.assert_awaited_once_with(swarm_signature, max_tasks=0)


@pytest.mark.asyncio
async def test_close_swarm_does_not_call_afill_swarm_when_tasks_still_pending(
    mock_adapter,
):
    # Arrange
    mock_adapter.afill_swarm.return_value = None
    task_1 = await thirdmagic.sign("task_1", model_validators=ContextMessage)
    task_2 = await thirdmagic.sign("task_2", model_validators=ContextMessage)
    swarm_signature = await thirdmagic.swarm(
        task_name="test_swarm",
        model_validators=ContextMessage,
        tasks=[task_1, task_2],
    )
    await swarm_signature.finish_task(task_1.key, "result_1")

    # Act
    await swarm_signature.close_swarm()

    # Assert
    mock_adapter.afill_swarm.assert_not_awaited()


@pytest.mark.asyncio
async def test_close_swarm_does_not_call_afill_swarm_when_no_tasks_done(mock_adapter):
    # Arrange
    mock_adapter.afill_swarm.return_value = None
    task = await thirdmagic.sign("task_1", model_validators=ContextMessage)
    swarm_signature = await thirdmagic.swarm(
        task_name="test_swarm",
        model_validators=ContextMessage,
        tasks=[task],
    )

    # Act
    await swarm_signature.close_swarm()

    # Assert
    mock_adapter.afill_swarm.assert_not_awaited()
