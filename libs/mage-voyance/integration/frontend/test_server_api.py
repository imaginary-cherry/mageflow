import pytest

from integration.frontend.seed_test_data import TEST_PREFIX
from visualizer.models import TaskCallbacksResponse, TaskFromServer

# serialization_alias is output-only; remap JSON keys to field names for parsing
_ALIAS_TO_FIELD = {"children_ids": "subtask_ids", "metadata": "kwargs"}


def parse_task(data: dict) -> TaskFromServer:
    remapped = {_ALIAS_TO_FIELD.get(k, k): v for k, v in data.items()}
    return TaskFromServer(**remapped)
from visualizer.models import ConnectionStatus, HealthResponse


@pytest.mark.asyncio(loop_scope="session")
async def test_health_endpoint_returns_connected(test_client):
    # Arrange
    client, _ = test_client

    # Act
    response = await client.get("/api/health")

    # Assert
    assert response.status_code == 200
    health = HealthResponse.model_validate(response.json())
    assert health.hatchet == ConnectionStatus.CONNECTED
    assert health.redis == ConnectionStatus.CONNECTED


@pytest.mark.asyncio(loop_scope="session")
async def test_get_all_workflows_returns_seeded_tasks(test_client):
    # Arrange
    client, seeded_data = test_client

    # Act
    response = await client.get("/api/workflows")

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert "tasks" in data
    assert data["error"] is None
    tasks = data["tasks"]
    assert set(tasks.keys()) == seeded_data.all_task_ids()


@pytest.mark.asyncio(loop_scope="session")
async def test_get_root_tasks_returns_exact_roots(test_client):
    # Arrange
    client, seeded_data = test_client

    # Act
    response = await client.get("/api/workflows/roots")

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert set(data["taskIds"]) == seeded_data.root_task_ids()


@pytest.mark.asyncio(loop_scope="session")
async def test_batch_fetch_tasks_returns_requested_tasks(test_client):
    # Arrange
    client, seeded_data = test_client
    task_ids = [seeded_data.basic_task_id, seeded_data.chain.chain_id]

    # Act
    response = await client.post("/api/tasks/batch", json={"taskIds": task_ids})

    # Assert
    assert response.status_code == 200
    tasks = response.json()
    returned_ids = {t["id"] for t in tasks}
    assert returned_ids == set(task_ids)
    assert len(returned_ids) == len(task_ids)

    # Verify field names match frontend expectations
    for task in tasks:
        assert "children_ids" in task
        assert "metadata" in task
        assert "status" in task
        valid_statuses = [
            "pending",
            "running",
            "completed",
            "failed",
            "cancelled",
            "paused",
        ]
        assert task["status"] in valid_statuses

    # Verify specific status values for seeded tasks
    basic_task = next(t for t in tasks if t["id"] == seeded_data.basic_task_id)
    assert basic_task["status"] == "pending"

    chain_task = next(t for t in tasks if t["id"] == seeded_data.chain.chain_id)
    assert chain_task["status"] == "running"


@pytest.mark.asyncio(loop_scope="session")
async def test_batch_fetch_returns_chain_with_children(test_client):
    """Regression: chains must be returned by batch fetch, not silently dropped."""
    # Arrange
    client, seeded_data = test_client

    # Act
    response = await client.post(
        "/api/tasks/batch",
        json={"taskIds": [seeded_data.chain.chain_id]},
    )

    # Assert
    assert response.status_code == 200
    tasks = [parse_task(t) for t in response.json()]
    assert len(tasks) == 1
    chain = tasks[0]
    assert chain.id == seeded_data.chain.chain_id
    assert chain.type == "ChainTaskSignature"
    assert chain.status == "running"
    assert set(chain.subtask_ids) == {
        seeded_data.chain.task1_id,
        seeded_data.chain.task2_id,
    }


@pytest.mark.asyncio(loop_scope="session")
async def test_batch_fetch_returns_swarm_with_children(test_client):
    """Regression: swarms must be returned by batch fetch, not silently dropped."""
    # Arrange
    client, seeded_data = test_client

    # Act
    response = await client.post(
        "/api/tasks/batch",
        json={"taskIds": [seeded_data.swarm.swarm_id]},
    )

    # Assert
    assert response.status_code == 200
    tasks = [parse_task(t) for t in response.json()]
    assert len(tasks) == 1
    swarm = tasks[0]
    assert swarm.id == seeded_data.swarm.swarm_id
    assert swarm.type == "SwarmTaskSignature"
    assert swarm.status == "running"
    assert set(swarm.subtask_ids) == set(seeded_data.swarm.original_task_ids)


@pytest.mark.asyncio(loop_scope="session")
async def test_batch_fetch_mixed_signature_types(test_client):
    """Regression: batch fetch must return all Signature subtypes in one call."""
    # Arrange
    client, seeded_data = test_client
    requested_ids = [
        seeded_data.basic_task_id,
        seeded_data.chain.chain_id,
        seeded_data.swarm.swarm_id,
    ]

    # Act
    response = await client.post("/api/tasks/batch", json={"taskIds": requested_ids})

    # Assert
    assert response.status_code == 200
    tasks = [parse_task(t) for t in response.json()]
    assert {t.type for t in tasks} == {"TaskSignature", "ChainTaskSignature", "SwarmTaskSignature"}
    assert {t.id for t in tasks} == set(requested_ids)


@pytest.mark.asyncio(loop_scope="session")
async def test_callbacks_endpoint_works_for_chain_and_swarm(test_client):
    """Regression: callbacks endpoint must not return None for non-TaskSignature types."""
    # Arrange
    client, seeded_data = test_client

    # Act — chain
    chain_resp = await client.get(
        f"/api/workflows/{seeded_data.chain.chain_id}/callbacks"
    )
    # Act — swarm
    swarm_resp = await client.get(
        f"/api/workflows/{seeded_data.swarm.swarm_id}/callbacks"
    )

    # Assert — both parse as valid models, not None
    assert chain_resp.status_code == 200
    assert chain_resp.json() is not None
    chain_data = TaskCallbacksResponse(**chain_resp.json())
    assert isinstance(chain_data.success_callback_ids, list)
    assert isinstance(chain_data.error_callback_ids, list)

    assert swarm_resp.status_code == 200
    assert swarm_resp.json() is not None
    swarm_data = TaskCallbacksResponse(**swarm_resp.json())
    assert isinstance(swarm_data.success_callback_ids, list)
    assert isinstance(swarm_data.error_callback_ids, list)


@pytest.mark.asyncio(loop_scope="session")
async def test_batch_fetch_with_empty_list_returns_empty(test_client):
    # Arrange
    client, _ = test_client

    # Act
    response = await client.post("/api/tasks/batch", json={"taskIds": []})

    # Assert
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio(loop_scope="session")
async def test_batch_fetch_with_nonexistent_ids_returns_empty(test_client):
    # Arrange
    client, _ = test_client

    # Act
    response = await client.post(
        "/api/tasks/batch", json={"taskIds": ["nonexistent_id_1", "nonexistent_id_2"]}
    )

    # Assert
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio(loop_scope="session")
async def test_get_chain_children_returns_task_ids(test_client):
    # Arrange
    client, seeded_data = test_client
    expected_tasks = {
        seeded_data.chain.task1_id,
        seeded_data.chain.task2_id,
    }

    # Act
    response = await client.get(f"/api/workflows/{seeded_data.chain.chain_id}/children")

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["totalCount"] == 2
    assert set(data["taskIds"]) == expected_tasks


@pytest.mark.asyncio(loop_scope="session")
async def test_get_swarm_children_returns_batch_item_ids(test_client):
    # Arrange
    client, seeded_data = test_client

    # Act
    response = await client.get(f"/api/workflows/{seeded_data.swarm.swarm_id}/children")

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["totalCount"] == 3
    assert set(data["taskIds"]) == set(seeded_data.swarm.original_task_ids)


@pytest.mark.asyncio(loop_scope="session")
async def test_get_children_for_regular_task_returns_none(test_client):
    # Arrange
    client, seeded_data = test_client

    # Act
    response = await client.get(f"/api/workflows/{seeded_data.basic_task_id}/children")

    # Assert
    assert response.status_code == 200
    assert response.json() is None


@pytest.mark.asyncio(loop_scope="session")
async def test_get_children_for_nonexistent_task_returns_none(test_client):
    # Arrange
    client, _ = test_client

    # Act
    response = await client.get(f"/api/workflows/{TEST_PREFIX}nonexistent/children")

    # Assert
    assert response.status_code == 200
    assert response.json() is None


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize(
    ["page", "page_size", "expected_count"],
    [
        (1, 1, 1),
        (2, 1, 1),
        (1, 10, 2),
        (3, 1, 0),
    ],
)
async def test_get_chain_children_pagination(
    test_client, page, page_size, expected_count
):
    # Arrange
    client, seeded_data = test_client

    # Act
    response = await client.get(
        f"/api/workflows/{seeded_data.chain.chain_id}/children",
        params={"page": page, "page_size": page_size},
    )

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["totalCount"] == 2
    assert data["page"] == page
    assert data["pageSize"] == page_size
    assert len(data["taskIds"]) == expected_count


@pytest.mark.asyncio(loop_scope="session")
async def test_get_task_callbacks_returns_callback_ids(test_client):
    # Arrange
    client, seeded_data = test_client

    # Act
    response = await client.get(
        f"/api/workflows/{seeded_data.callbacks.task_id}/callbacks"
    )

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert seeded_data.callbacks.success_callback_ids == data["success_callback_ids"]
    assert seeded_data.callbacks.error_callback_ids == data["error_callback_ids"]


@pytest.mark.asyncio(loop_scope="session")
async def test_get_callbacks_for_task_without_callbacks(test_client):
    # Arrange
    client, seeded_data = test_client

    # Act
    response = await client.get(f"/api/workflows/{seeded_data.basic_task_id}/callbacks")

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["success_callback_ids"] == []
    assert data["error_callback_ids"] == []


@pytest.mark.asyncio(loop_scope="session")
async def test_get_callbacks_for_nonexistent_task_returns_none(test_client):
    # Arrange
    client, _ = test_client

    # Act
    response = await client.get(f"/api/workflows/{TEST_PREFIX}nonexistent/callbacks")

    # Assert
    assert response.status_code == 200
    assert response.json() is None


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.skip(
    reason="Control endpoints require Hatchet infrastructure not available in lightweight tests"
)
async def test_cancel_task_returns_202_accepted(test_client):
    # Arrange
    client, seeded_data = test_client

    # Act
    response = await client.post(f"/api/tasks/{seeded_data.basic_task_id}/cancel")

    # Assert
    assert response.status_code == 202


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.skip(
    reason="Control endpoints require Hatchet infrastructure not available in lightweight tests"
)
async def test_pause_task_returns_202_accepted(test_client):
    # Arrange
    client, seeded_data = test_client

    # Act
    response = await client.post(f"/api/tasks/{seeded_data.chain.chain_id}/pause")

    # Assert
    assert response.status_code == 202


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.skip(
    reason="Control endpoints require Hatchet infrastructure not available in lightweight tests"
)
async def test_retry_task_returns_202_accepted(test_client):
    # Arrange
    client, seeded_data = test_client

    # Act
    response = await client.post(f"/api/tasks/{seeded_data.callbacks.task_id}/retry")

    # Assert
    assert response.status_code == 202


@pytest.mark.asyncio(loop_scope="session")
async def test_cancel_nonexistent_task_returns_404(test_client):
    # Arrange
    client, _ = test_client

    # Act
    response = await client.post(f"/api/tasks/{TEST_PREFIX}nonexistent/cancel")

    # Assert
    assert response.status_code == 404


@pytest.mark.asyncio(loop_scope="session")
async def test_pause_nonexistent_task_returns_404(test_client):
    # Arrange
    client, _ = test_client

    # Act
    response = await client.post(f"/api/tasks/{TEST_PREFIX}nonexistent/pause")

    # Assert
    assert response.status_code == 404


@pytest.mark.asyncio(loop_scope="session")
async def test_retry_nonexistent_task_returns_404(test_client):
    # Arrange
    client, _ = test_client

    # Act
    response = await client.post(f"/api/tasks/{TEST_PREFIX}nonexistent/retry")

    # Assert
    assert response.status_code == 404
