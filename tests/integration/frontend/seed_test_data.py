import asyncio
from datetime import datetime

import click
import rapyer
from redis.asyncio import Redis

from mageflow.chain.model import ChainTaskSignature
from mageflow.signature.model import TaskSignature
from mageflow.signature.status import SignatureStatus, TaskStatus
from mageflow.swarm.model import SwarmTaskSignature, SwarmConfig
from mageflow.swarm.state import PublishState

TEST_PREFIX = "test_frontend_"


async def seed_basic_task() -> str:
    task = TaskSignature(
        task_name="basic_test_task",
        kwargs={"param1": "value1", "param2": 42},
        creation_time=datetime.now(),
        task_status=TaskStatus(status=SignatureStatus.PENDING),
    )
    task.key = f"{TEST_PREFIX}basic_task_001"
    await task.asave()
    return task.key


async def seed_chain_task() -> dict[str, str]:
    task1 = TaskSignature(
        task_name="chain_step_1",
        kwargs={"step": 1},
        creation_time=datetime.now(),
        task_status=TaskStatus(status=SignatureStatus.PENDING),
    )
    task1.key = f"{TEST_PREFIX}chain_task_001"
    await task1.asave()

    task2 = TaskSignature(
        task_name="chain_step_2",
        kwargs={"step": 2},
        creation_time=datetime.now(),
        task_status=TaskStatus(status=SignatureStatus.PENDING),
    )
    task2.key = f"{TEST_PREFIX}chain_task_002"
    await task2.asave()

    chain = ChainTaskSignature(
        task_name="test_chain",
        tasks=[task1.key, task2.key],
        kwargs={"chain_param": "chain_value"},
        creation_time=datetime.now(),
        task_status=TaskStatus(status=SignatureStatus.ACTIVE),
    )
    chain.key = f"{TEST_PREFIX}chain_001"
    await chain.asave()

    return {"chain_id": chain.key, "task1_id": task1.key, "task2_id": task2.key}


async def seed_swarm_task() -> dict[str, str | list[str]]:
    publish_state = PublishState()
    publish_state.key = f"{TEST_PREFIX}publish_state_001"
    await publish_state.asave()

    swarm = SwarmTaskSignature(
        task_name="test_swarm",
        tasks=[],
        kwargs={"swarm_param": "swarm_value"},
        creation_time=datetime.now(),
        task_status=TaskStatus(status=SignatureStatus.ACTIVE),
        publishing_state_id=publish_state.key,
        config=SwarmConfig(max_concurrency=10),
    )
    swarm.key = f"{TEST_PREFIX}swarm_001"
    await swarm.asave()

    batch_item_ids = []
    original_task_ids = []
    swarm_item_callback_ids = []
    for i in range(3):
        original_task = TaskSignature(
            task_name="swarm_item_task",
            kwargs={"item_index": i},
            creation_time=datetime.now(),
            task_status=TaskStatus(status=SignatureStatus.PENDING),
        )
        original_task.key = f"{TEST_PREFIX}swarm_original_{i:03d}"
        await original_task.asave()
        original_task_ids.append(original_task.key)

        batch_item = await swarm.add_task(original_task)
        batch_item_ids.append(batch_item.key)
        swarm_item_callback_ids.extend(original_task.success_callbacks)
        swarm_item_callback_ids.extend(original_task.error_callbacks)

    return {
        "swarm_id": swarm.key,
        "batch_item_ids": batch_item_ids,
        "original_task_ids": original_task_ids,
        "swarm_item_callback_ids": swarm_item_callback_ids,
    }


async def seed_task_with_callbacks() -> dict[str, str | list[str]]:
    success_callback = TaskSignature(
        task_name="on_success_callback",
        kwargs={"callback_type": "success"},
        creation_time=datetime.now(),
        task_status=TaskStatus(status=SignatureStatus.PENDING),
    )
    success_callback.key = f"{TEST_PREFIX}success_callback_001"
    await success_callback.asave()

    error_callback = TaskSignature(
        task_name="on_error_callback",
        kwargs={"callback_type": "error"},
        creation_time=datetime.now(),
        task_status=TaskStatus(status=SignatureStatus.PENDING),
    )
    error_callback.key = f"{TEST_PREFIX}error_callback_001"
    await error_callback.asave()

    main_task = TaskSignature(
        task_name="task_with_callbacks",
        kwargs={"has_callbacks": True},
        creation_time=datetime.now(),
        task_status=TaskStatus(status=SignatureStatus.ACTIVE),
        success_callbacks=[success_callback.key],
        error_callbacks=[error_callback.key],
    )
    main_task.key = f"{TEST_PREFIX}task_with_callbacks_001"
    await main_task.asave()

    return {
        "task_id": main_task.key,
        "success_callback_ids": [success_callback.key],
        "error_callback_ids": [error_callback.key],
    }


async def cleanup_test_data(
    redis_client: Redis, prefix: str = TEST_PREFIX, clean_all: bool = False
) -> int:
    if clean_all:
        keys = await redis_client.keys("*")
    else:
        keys = await redis_client.keys(f"*{prefix}*")
    if keys:
        await redis_client.delete(*keys)
    return len(keys)


async def seed_all(redis_url: str) -> dict:
    redis_client = Redis.from_url(redis_url, decode_responses=True)

    try:
        await rapyer.init_rapyer(redis_client, prefer_normal_json_dump=True)
        basic_task_id = await seed_basic_task()
        chain_data = await seed_chain_task()
        swarm_data = await seed_swarm_task()
        callback_data = await seed_task_with_callbacks()

        return {
            "basic_task_id": basic_task_id,
            "chain": chain_data,
            "swarm": swarm_data,
            "callbacks": callback_data,
        }
    finally:
        await rapyer.teardown_rapyer()
        await redis_client.aclose()


async def cleanup_all(redis_url: str) -> int:
    redis_client = Redis.from_url(redis_url, decode_responses=True)

    try:
        await rapyer.init_rapyer(redis_client, prefer_normal_json_dump=True)
        return await cleanup_test_data(redis_client)
    finally:
        await rapyer.teardown_rapyer()
        await redis_client.aclose()


@click.command()
@click.option(
    "--action",
    type=click.Choice(["seed", "cleanup"]),
    required=True,
    help="Action to perform",
)
@click.option(
    "--redis-url",
    default="redis://localhost:6379/",
    help="Redis URL",
)
def main(action: str, redis_url: str):
    if action == "seed":
        result = asyncio.run(seed_all(redis_url))
        click.echo(f"Seeded test data: {result}")
    elif action == "cleanup":
        deleted_count = asyncio.run(cleanup_all(redis_url))
        click.echo(f"Cleaned up {deleted_count} keys")


if __name__ == "__main__":
    main()
