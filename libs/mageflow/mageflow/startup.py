import rapyer
from hatchet_sdk.runnables.workflow import Standalone
from redis.asyncio import Redis
from thirdmagic.signature.model import TaskSignature
from thirdmagic.task import MageflowTaskDefinition

REGISTERED_TASKS: list[tuple[Standalone, str]] = []


async def init_mageflow(redis: Redis):
    # Init redis in local async loop
    redis = Redis(**redis.connection_pool.connection_kwargs)
    await rapyer.init_rapyer(redis, prefer_normal_json_dump=True)
    await register_workflows()


async def teardown_mageflow():
    await rapyer.teardown_rapyer()


async def register_workflows():
    for reg_task in REGISTERED_TASKS:
        workflow, mageflow_task_name = reg_task
        validator = TaskSignature.ClientAdapter.extract_validator(workflow)
        hatchet_task = MageflowTaskDefinition(
            mageflow_task_name=mageflow_task_name,
            task_name=workflow.name,
            input_validator=validator,
            retries=workflow.tasks[0].retries,
        )
        await hatchet_task.asave()


async def lifespan_initialize(redis: Redis):
    # Init redis in local async loop
    redis = Redis(**redis.connection_pool.connection_kwargs)
    await init_mageflow(redis)
    # yield makes the function usable as a Hatchet lifespan context manager (can also be used for FastAPI):
    # - code before yield runs at startup (init config, register workers, etc.)
    # - code after yield would run at shutdown
    yield
    await teardown_mageflow()
