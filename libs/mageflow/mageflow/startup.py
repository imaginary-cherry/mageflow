import rapyer
from redis.asyncio import Redis
from thirdmagic.task_def import MageflowTaskDefinition


async def init_mageflow(redis: Redis, tasks: list[MageflowTaskDefinition]):
    # Init redis in local async loop
    redis = Redis(**redis.connection_pool.connection_kwargs)
    await rapyer.init_rapyer(redis, prefer_normal_json_dump=True)
    await register_workflows(tasks)


async def teardown_mageflow():
    await rapyer.teardown_rapyer()


async def register_workflows(tasks: list[MageflowTaskDefinition]):
    await MageflowTaskDefinition.ainsert(*tasks)


async def lifespan_initialize(redis: Redis, tasks: list[MageflowTaskDefinition]):
    # Init redis in local async loop
    redis = Redis(**redis.connection_pool.connection_kwargs)
    await init_mageflow(redis, tasks)
    # yield makes the function usable as a Hatchet lifespan context manager (can also be used for FastAPI):
    # - code before yield runs at startup (init config, register workers, etc.)
    # - code after yield would run at shutdown
    yield
    await teardown_mageflow()
