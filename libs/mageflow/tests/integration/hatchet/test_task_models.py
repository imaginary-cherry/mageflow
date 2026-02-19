import asyncio

import pytest
from thirdmagic.task_def import MageflowTaskDefinition

from tests.integration.hatchet.conftest import HatchetInitData
from tests.integration.hatchet.models import ContextMessage


@pytest.mark.asyncio(loop_scope="session")
async def test_hatchet_task_model_no_ttl_sanity(hatchet_client_init: HatchetInitData):
    # Arrange
    redis_client = hatchet_client_init.redis_client
    # Wait a bit to ensure worker has registered all tasks
    await asyncio.sleep(2)

    # Act
    task_model_keys = await MageflowTaskDefinition.afind_keys()

    # Assert
    assert (
        len(task_model_keys) > 0
    ), "No HatchetTaskModel keys found in Redis after worker deployment"

    for key in task_model_keys:
        ttl_result = await redis_client.ttl(key)
        assert (
            ttl_result == -1
        ), f"HatchetTaskModel key {key} has TTL {ttl_result}, expected -1 (no TTL)"


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize(
    ["task_name", "task_def"],
    [
        [
            "timeout_task",
            MageflowTaskDefinition(
                mageflow_task_name="timeout_task",
                task_name="mageflow_test_timeout_task",
                retries=1,
                input_validator=ContextMessage,
            ),
        ],
    ],
)
async def test_all_worker_tasks_have_task_definitions(
    hatchet_client_init: HatchetInitData,
    task_name: str,
    task_def: MageflowTaskDefinition,
):
    # Act
    task_definitions = await MageflowTaskDefinition.aget(task_name)

    # Assert
    assert task_definitions == task_def
