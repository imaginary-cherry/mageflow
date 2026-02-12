import pytest

import mageflow
from mageflow.chain.model import ChainTaskSignature
from mageflow.signature.model import TaskSignature
from mageflow.swarm.model import SwarmTaskSignature
from tests.integration.hatchet.models import ContextMessage
from tests.unit.assertions import assert_task_reloaded_as_type, assert_callback_contains


@pytest.mark.asyncio
async def test_chain_with_swarm_task_creates_container_correctly_edge_case(
    hatchet_mock,
):
    # Arrange
    # Create a swarm task
    swarm_task = await mageflow.swarm(
        task_name="test_swarm_task",
        model_validators=ContextMessage,
        swarm_arg="swarm_value",
    )

    simple_task = await mageflow.sign(
        "simple_task",
        model_validators=ContextMessage,
        param="value",
    )

    # Act
    chain_signature = await mageflow.chain([swarm_task.key, simple_task.key])

    # Assert
    reloaded_swarm = await assert_task_reloaded_as_type(
        swarm_task.key, SwarmTaskSignature
    )
    assert reloaded_swarm.signature_container_id == chain_signature.key

    reloaded_simple = await assert_task_reloaded_as_type(simple_task.key, TaskSignature)
    assert reloaded_simple.signature_container_id == chain_signature.key


@pytest.mark.asyncio
async def test_chain_with_swarm_added_task_creates_container_correctly_edge_case(
    hatchet_mock,
):
    # Arrange
    parent_swarm = await mageflow.swarm(
        task_name="parent_swarm",
        model_validators=ContextMessage,
    )

    original_task = await mageflow.sign(
        "original_task",
        model_validators=ContextMessage,
    )

    task = await parent_swarm.add_task(original_task)

    simple_task = await mageflow.sign(
        "simple_task_after_batch",
        model_validators=ContextMessage,
    )

    # Act
    chain_signature = await mageflow.chain([parent_swarm.key, simple_task.key])

    # Assert
    reloaded_task = await assert_task_reloaded_as_type(task.key, TaskSignature)
    assert reloaded_task.signature_container_id == parent_swarm.key
    reloaded_swarm = await assert_task_reloaded_as_type(
        parent_swarm.key, SwarmTaskSignature
    )
    assert reloaded_swarm.signature_container_id == chain_signature.key


@pytest.mark.asyncio
async def test_chain_with_mixed_task_types_loads_and_chains_correctly_sanity(
    hatchet_mock,
):
    # Arrange
    # Create various task types
    simple_task = await mageflow.sign(
        "simple_task",
        model_validators=ContextMessage,
        simple_arg="simple_value",
    )

    swarm_task = await mageflow.swarm(
        task_name="swarm_task",
        model_validators=ContextMessage,
        swarm_arg="swarm_value",
    )

    # Create another simple task
    final_task = await mageflow.sign(
        "final_task",
        model_validators=ContextMessage,
        final_arg="final_value",
    )

    # Act
    chain_signature = await mageflow.chain(
        [simple_task.key, swarm_task.key, final_task.key]
    )

    # Assert
    loaded_simple = await assert_task_reloaded_as_type(simple_task.key, TaskSignature)
    loaded_swarm = await assert_task_reloaded_as_type(
        swarm_task.key, SwarmTaskSignature
    )
    loaded_final = await assert_task_reloaded_as_type(final_task.key, TaskSignature)

    assert loaded_simple.signature_container_id == chain_signature.key
    assert loaded_swarm.signature_container_id == chain_signature.key
    assert loaded_final.signature_container_id == chain_signature.key

    loaded_chain = await assert_task_reloaded_as_type(
        chain_signature.key, ChainTaskSignature
    )
    assert loaded_chain.tasks == [simple_task.key, swarm_task.key, final_task.key]


@pytest.mark.asyncio
async def test_chain_creation_with_custom_name_and_callbacks_sanity(hatchet_mock):
    # Arrange
    # Create custom success and error callbacks
    custom_success = await mageflow.sign(
        "custom_success_callback",
        model_validators=ContextMessage,
    )

    custom_error = await mageflow.sign(
        "custom_error_callback",
        model_validators=ContextMessage,
    )

    # Create tasks for a chain
    task1 = await mageflow.sign(
        "task1",
        model_validators=ContextMessage,
    )

    task2 = await mageflow.sign(
        "task2",
        model_validators=ContextMessage,
    )

    # Act
    chain_signature = await mageflow.chain(
        [task1.key, task2.key],
        name="custom_chain_name",
        success=custom_success.key,
        error=custom_error.key,
    )

    # Assert
    loaded_chain = await assert_task_reloaded_as_type(
        chain_signature.key, TaskSignature
    )
    assert loaded_chain.task_name == "chain-task:custom_chain_name"
    assert_callback_contains(loaded_chain, [custom_success.key], [custom_error.key])
