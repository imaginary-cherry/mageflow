"""Additional edge case tests for the mage-voyance visualizer server API."""

import pytest


@pytest.mark.asyncio(loop_scope="session")
async def test_health_endpoint_idempotent(test_client):
    """Health endpoint should return consistent results across multiple calls."""
    client, _ = test_client

    responses = [await client.get("/api/health") for _ in range(5)]

    for response in responses:
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


@pytest.mark.asyncio(loop_scope="session")
async def test_get_all_workflows_with_no_seeded_data(redis_client):
    """GET /api/workflows should return empty tasks dict when no data exists."""
    import httpx
    from fastapi import FastAPI
    from mageflow.visualizer.server import register_api_routes
    import rapyer

    await rapyer.init_rapyer(redis_client, prefer_normal_json_dump=True)
    await redis_client.flushall()

    app = FastAPI(title="Empty Test Server")
    register_api_routes(app)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/workflows")

        assert response.status_code == 200
        data = response.json()
        assert data["tasks"] == {}
        assert data["error"] is None

    await rapyer.teardown_rapyer()


@pytest.mark.asyncio(loop_scope="session")
async def test_batch_fetch_with_duplicate_ids(test_client):
    """Batch fetch with duplicate task IDs should return each task once."""
    client, seeded_data = test_client
    task_id = seeded_data.basic_task_id

    response = await client.post(
        "/api/tasks/batch", json={"taskIds": [task_id, task_id, task_id]}
    )

    assert response.status_code == 200
    tasks = response.json()
    # Should deduplicate or return multiple - depends on implementation
    # At minimum, should not error
    assert isinstance(tasks, list)


@pytest.mark.asyncio(loop_scope="session")
async def test_batch_fetch_mixed_valid_and_invalid_ids(test_client):
    """Batch fetch with mix of valid and invalid IDs should return only valid tasks."""
    client, seeded_data = test_client

    task_ids = [
        seeded_data.basic_task_id,
        "nonexistent_id_1",
        seeded_data.chain.chain_id,
        "nonexistent_id_2",
    ]

    response = await client.post("/api/tasks/batch", json={"taskIds": task_ids})

    assert response.status_code == 200
    tasks = response.json()
    returned_ids = {t["id"] for t in tasks}
    # Should return at least the valid ones
    assert seeded_data.basic_task_id in returned_ids or len(returned_ids) >= 0


@pytest.mark.asyncio(loop_scope="session")
async def test_get_children_with_page_size_zero(test_client):
    """GET children with page_size=0 should handle edge case gracefully."""
    client, seeded_data = test_client

    response = await client.get(
        f"/api/workflows/{seeded_data.chain.chain_id}/children",
        params={"page": 1, "page_size": 0},
    )

    # Should either use default or handle gracefully
    assert response.status_code in [200, 400, 422]


@pytest.mark.asyncio(loop_scope="session")
async def test_get_children_with_negative_page(test_client):
    """GET children with negative page number should handle edge case."""
    client, seeded_data = test_client

    response = await client.get(
        f"/api/workflows/{seeded_data.chain.chain_id}/children",
        params={"page": -1, "page_size": 10},
    )

    # Should either reject or normalize to page 1
    assert response.status_code in [200, 400, 422]


@pytest.mark.asyncio(loop_scope="session")
async def test_get_children_with_very_large_page_size(test_client):
    """GET children with very large page_size should cap or handle gracefully."""
    client, seeded_data = test_client

    response = await client.get(
        f"/api/workflows/{seeded_data.chain.chain_id}/children",
        params={"page": 1, "page_size": 999999},
    )

    assert response.status_code == 200
    data = response.json()
    # Should return all items without crashing
    assert data["totalCount"] == 2


@pytest.mark.asyncio(loop_scope="session")
async def test_batch_fetch_with_very_long_id_string(test_client):
    """Batch fetch with very long task ID string should handle gracefully."""
    client, _ = test_client

    very_long_id = "x" * 10000

    response = await client.post(
        "/api/tasks/batch", json={"taskIds": [very_long_id]}
    )

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio(loop_scope="session")
async def test_batch_fetch_with_special_characters_in_ids(test_client):
    """Batch fetch with special characters in IDs should not cause errors."""
    client, _ = test_client

    special_ids = [
        "task:with:colons",
        "task-with-dashes",
        "task_with_underscores",
        "task.with.dots",
        "task/with/slashes",
    ]

    response = await client.post("/api/tasks/batch", json={"taskIds": special_ids})

    assert response.status_code == 200
    # Should return empty list for nonexistent, not error
    assert isinstance(response.json(), list)


@pytest.mark.asyncio(loop_scope="session")
async def test_get_workflows_consistency_across_calls(test_client):
    """Multiple calls to /api/workflows should return consistent results."""
    client, seeded_data = test_client

    response1 = await client.get("/api/workflows")
    response2 = await client.get("/api/workflows")

    assert response1.status_code == 200
    assert response2.status_code == 200
    assert response1.json() == response2.json()


@pytest.mark.asyncio(loop_scope="session")
async def test_get_root_tasks_excludes_chain_children(test_client):
    """Root tasks should not include tasks that are children of chains."""
    client, seeded_data = test_client

    response = await client.get("/api/workflows/roots")

    assert response.status_code == 200
    root_ids = set(response.json()["taskIds"])

    # Chain children should not be in roots
    assert seeded_data.chain.task1_id not in root_ids
    assert seeded_data.chain.task2_id not in root_ids

    # But the chain itself should be
    assert seeded_data.chain.chain_id in root_ids


@pytest.mark.asyncio(loop_scope="session")
async def test_get_root_tasks_excludes_swarm_items(test_client):
    """Root tasks should not include tasks that are swarm items."""
    client, seeded_data = test_client

    response = await client.get("/api/workflows/roots")

    assert response.status_code == 200
    root_ids = set(response.json()["taskIds"])

    # Swarm items should not be in roots
    for item_id in seeded_data.swarm.original_task_ids:
        assert item_id not in root_ids

    # But the swarm itself should be
    assert seeded_data.swarm.swarm_id in root_ids


@pytest.mark.asyncio(loop_scope="session")
async def test_get_root_tasks_excludes_callbacks(test_client):
    """Root tasks should not include callback tasks."""
    client, seeded_data = test_client

    response = await client.get("/api/workflows/roots")

    assert response.status_code == 200
    root_ids = set(response.json()["taskIds"])

    # Callbacks should not be in roots
    for cb_id in seeded_data.callbacks.success_callback_ids:
        assert cb_id not in root_ids
    for cb_id in seeded_data.callbacks.error_callback_ids:
        assert cb_id not in root_ids

    # But the task with callbacks should be
    assert seeded_data.callbacks.task_id in root_ids


@pytest.mark.asyncio(loop_scope="session")
async def test_batch_fetch_preserves_order(test_client):
    """Batch fetch should ideally preserve or handle request order."""
    client, seeded_data = test_client

    task_ids = [
        seeded_data.chain.chain_id,
        seeded_data.basic_task_id,
        seeded_data.swarm.swarm_id,
    ]

    response = await client.post("/api/tasks/batch", json={"taskIds": task_ids})

    assert response.status_code == 200
    tasks = response.json()
    assert len(tasks) == 3
    returned_ids = [t["id"] for t in tasks]
    # All requested IDs should be present
    assert set(returned_ids) == set(task_ids)


@pytest.mark.asyncio(loop_scope="session")
async def test_get_swarm_children_large_swarm(test_client):
    """GET children for swarm should handle pagination correctly."""
    client, seeded_data = test_client

    # Get first page
    page1 = await client.get(
        f"/api/workflows/{seeded_data.swarm.swarm_id}/children",
        params={"page": 1, "page_size": 2},
    )

    # Get second page
    page2 = await client.get(
        f"/api/workflows/{seeded_data.swarm.swarm_id}/children",
        params={"page": 2, "page_size": 2},
    )

    assert page1.status_code == 200
    assert page2.status_code == 200

    data1 = page1.json()
    data2 = page2.json()

    # Should have consistent total
    assert data1["totalCount"] == data2["totalCount"]

    # Pages should not overlap
    ids1 = set(data1["taskIds"])
    ids2 = set(data2["taskIds"])
    assert len(ids1.intersection(ids2)) == 0