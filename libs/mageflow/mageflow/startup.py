import rapyer
from redis.asyncio import Redis
from thirdmagic.task_def import MageflowTaskDefinition

from mageflow.config import MageflowConfig, apply_ttl_config


async def init_mageflow(
    redis: Redis,
    tasks: list[MageflowTaskDefinition],
    config: MageflowConfig = None,
):
    if config is None:
        config = MageflowConfig()
    # Apply TTL config before rapyer init so new Meta objects receive the Redis client
    apply_ttl_config(config.ttl)
    # Init redis in local async loop
    redis = Redis(**redis.connection_pool.connection_kwargs)
    await rapyer.init_rapyer(redis, prefer_normal_json_dump=True)
    await register_workflows(tasks)


async def teardown_mageflow():
    await rapyer.teardown_rapyer()


async def register_workflows(tasks: list[MageflowTaskDefinition]):
    await MageflowTaskDefinition.ainsert(*tasks)


async def lifespan_initialize(
    redis: Redis,
    tasks: list[MageflowTaskDefinition],
    config: MageflowConfig = None,
):
    # Init redis in local async loop
    redis = Redis(**redis.connection_pool.connection_kwargs)
    await init_mageflow(redis, tasks, config)
    # yield makes the function usable as a Hatchet lifespan context manager (can also be used for FastAPI):
    # - code before yield runs at startup (init config, register workers, etc.)
    # - code after yield would run at shutdown
    yield
    await teardown_mageflow()
