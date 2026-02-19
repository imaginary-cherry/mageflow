import asyncio

import pytest
from thirdmagic.task_def import MageflowTaskDefinition

from tests.integration.hatchet.conftest import HatchetInitData
from tests.integration.hatchet.worker import workflows


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
async def test_all_worker_tasks_have_task_definitions(
    hatchet_client_init: HatchetInitData,
):
    # Arrange
    expected_tasks = {wf.name: wf for wf in workflows}

    # Act
    task_definitions = await MageflowTaskDefinition.afind()
    task_defs_by_name = {td.mageflow_task_name: td for td in task_definitions}

    # Assert
    missing_tasks = expected_tasks.keys() - task_defs_by_name.keys()
    assert not missing_tasks, (
        f"Worker tasks missing MageflowTaskDefinition in Redis: {missing_tasks}"
    )

    for task_name, wf in expected_tasks.items():
        task_def = task_defs_by_name[task_name]
        expected_retries = wf.tasks[0].retries
        assert task_def.retries == expected_retries, (
            f"Task '{task_name}' retries mismatch: "
            f"expected {expected_retries}, got {task_def.retries}"
        )
