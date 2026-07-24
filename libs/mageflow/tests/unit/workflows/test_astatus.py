import pytest
from thirdmagic import ContainersStatus, ContainerStatus
from thirdmagic.errors import MissingSignatureError, NotAContainerError
from thirdmagic.signature.status import SignatureStatus

import mageflow
from tests.integration.hatchet.models import ContextMessage
from tests.unit.workflows.conftest import create_swarm_item_test_setup


@pytest.mark.asyncio
async def test_astatus_returns_status_for_single_container(mock_adapter):
    # Arrange
    setup = await create_swarm_item_test_setup(
        num_tasks=4,
        stop_after_n_failures=None,
        current_running=1,
        tasks_left_indices=[3],
        finished_indices=[0],
        failed_indices=[1],
    )
    expected = ContainersStatus(
        containers=[
            ContainerStatus(
                signature_id=setup.swarm_task.key,
                task_name="test_swarm",
                status=SignatureStatus.PENDING,
                total=4,
                finished=1,
                failed=1,
                running=1,
                pending=1,
                percentage=50.0,
                is_done=False,
            )
        ]
    )

    # Act
    result = await mageflow.astatus(setup.swarm_task.key)

    # Assert
    assert result == expected


@pytest.mark.asyncio
async def test_astatus_aggregates_multiple_containers(mock_adapter):
    # Arrange
    first = await create_swarm_item_test_setup(
        num_tasks=2, stop_after_n_failures=None, finished_indices=[0, 1]
    )
    second = await create_swarm_item_test_setup(num_tasks=2, stop_after_n_failures=None)
    expected = ContainersStatus(
        containers=[
            ContainerStatus(
                signature_id=first.swarm_task.key,
                task_name="test_swarm",
                status=SignatureStatus.PENDING,
                total=2,
                finished=2,
                failed=0,
                running=1,
                pending=0,
                percentage=100.0,
                is_done=False,
            ),
            ContainerStatus(
                signature_id=second.swarm_task.key,
                task_name="test_swarm",
                status=SignatureStatus.PENDING,
                total=2,
                finished=0,
                failed=0,
                running=1,
                pending=0,
                percentage=0.0,
                is_done=False,
            ),
        ]
    )

    # Act
    result = await mageflow.astatus(first.swarm_task.key, second.swarm_task.key)

    # Assert
    assert result == expected
    # 2 terminal tasks out of 4 total across both swarms
    assert result.overall_percentage == 50.0


@pytest.mark.asyncio
async def test_astatus_empty_ids_returns_empty_without_db_scan(mock_adapter):
    # Act
    result = await mageflow.astatus()

    # Assert
    assert isinstance(result, ContainersStatus)
    assert result.containers == []


@pytest.mark.asyncio
async def test_astatus_raises_for_non_container(mock_adapter):
    # Arrange
    task = await mageflow.asign("plain_task", model_validators=ContextMessage)

    # Act / Assert
    with pytest.raises(NotAContainerError):
        await mageflow.astatus(task.key)


@pytest.mark.asyncio
async def test_astatus_raises_for_missing_signature(mock_adapter):
    # Arrange
    missing_key = "SwarmTaskSignature:00000000-0000-0000-0000-000000000000"

    # Act / Assert
    with pytest.raises(MissingSignatureError):
        await mageflow.astatus(missing_key)
