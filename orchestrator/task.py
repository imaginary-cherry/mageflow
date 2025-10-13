from orchestrator.hatchet.config import orchestrator_config
from orchestrator.hatchet.register import load_name


async def find_outer_task(task_name: str):
    hatchet = orchestrator_config.hatchet_client
    redis = orchestrator_config.redis_client
    task = await load_name(redis, task_name)
    workflow = hatchet.workflow(name=task)
    return workflow
