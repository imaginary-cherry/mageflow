import pytest

from tests.integration.frontend.seed_test_data import TEST_PREFIX


@pytest.mark.asyncio(loop_scope="session")
async def test_health_endpoint_returns_ok(test_client):
    # Arrange
    client, _ = test_client

    # Act
    response = await client.get("/api/health")

    # Assert
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


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
    assert set(data["taskIds"]) == set(seeded_data.swarm.batch_item_ids)


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
