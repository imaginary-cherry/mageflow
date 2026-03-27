import os
from dataclasses import dataclass

import httpx
import pytest_asyncio
import rapyer
from fastapi import FastAPI
from integration.frontend.seed_test_data import (
    CallbackTestData,
    ChainTestData,
    SwarmTestData,
    cleanup_test_data,
    seed_basic_task,
    seed_chain_task,
    seed_swarm_task,
    seed_task_with_callbacks,
)
from redis.asyncio import Redis
from testcontainers.redis import RedisContainer
from visualizer.server import register_api_routes


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def redis_client():
    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        client = Redis.from_url(redis_url, decode_responses=True)
        yield client
        await client.aclose()
        return

    with RedisContainer("redis/redis-stack-server:7.2.0-v10") as container:
        host = container.get_container_host_ip()
        port = container.get_exposed_port(6379)
        redis_url = f"redis://{host}:{port}"
        os.environ["REDIS_URL"] = redis_url
        client = Redis.from_url(redis_url, decode_responses=True)
        yield client
        await client.aclose()


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
        chain=chain_data,
        swarm=swarm_data,
        callbacks=callback_data,
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
