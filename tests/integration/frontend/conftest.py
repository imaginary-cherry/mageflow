from dataclasses import dataclass

import httpx
import pytest_asyncio
import rapyer
from fastapi import FastAPI

from mageflow.visualizer.server import register_api_routes
from tests.integration.frontend.seed_test_data import (
    cleanup_test_data,
    seed_basic_task,
    seed_chain_task,
    seed_swarm_task,
    seed_task_with_callbacks,
)


@dataclass
class ChainTestData:
    chain_id: str
    task1_id: str
    task2_id: str


@dataclass
class SwarmTestData:
    swarm_id: str
    batch_item_ids: list[str]
    original_task_ids: list[str]
    swarm_item_callback_ids: list[str]


@dataclass
class CallbackTestData:
    task_id: str
    success_callback_ids: list[str]
    error_callback_ids: list[str]


@dataclass
class SeededTestData:
    basic_task_id: str
    chain: ChainTestData
    swarm: SwarmTestData
    callbacks: CallbackTestData

    def all_task_ids(self) -> set[str]:
        return {
            self.basic_task_id,
            self.chain.chain_id,
            self.chain.task1_id,
            self.chain.task2_id,
            self.swarm.swarm_id,
            *self.swarm.batch_item_ids,
            *self.swarm.original_task_ids,
            *self.swarm.swarm_item_callback_ids,
            self.callbacks.task_id,
            *self.callbacks.success_callback_ids,
            *self.callbacks.error_callback_ids,
        }

    def root_task_ids(self) -> set[str]:
        return {
            self.basic_task_id,
            self.chain.chain_id,
            self.swarm.swarm_id,
            self.callbacks.task_id,
        }


@pytest_asyncio.fixture(scope="function", loop_scope="session")
async def seeded_test_data(redis_client):
    await rapyer.init_rapyer(redis_client, prefer_normal_json_dump=True)
    await cleanup_test_data(redis_client, clean_all=True)

    basic_task_id = await seed_basic_task()
    chain_data = await seed_chain_task()
    swarm_data = await seed_swarm_task()
    callback_data = await seed_task_with_callbacks()

    yield SeededTestData(
        basic_task_id=basic_task_id,
        chain=ChainTestData(**chain_data),
        swarm=SwarmTestData(**swarm_data),
        callbacks=CallbackTestData(**callback_data),
    )

    await cleanup_test_data(redis_client, clean_all=True)
    await rapyer.teardown_rapyer()


@pytest_asyncio.fixture(scope="function", loop_scope="session")
async def test_client(redis_client, seeded_test_data):
    app = FastAPI(title="Mageflow Test Server")
    register_api_routes(app)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, seeded_test_data
