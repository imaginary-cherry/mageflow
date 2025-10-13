import asyncio

from orchestrator.hatchet.config import orchestrator_config
from orchestrator.hatchet.register import store_task_name, store_input_validator

WORKER_FLAG_TO_STORE_NAME = "__orchestrator_task_name__"


async def init_from_dynaconf(workers: list = None):
    orchestrator_config.set_from_dynaconf()
    if workers:
        await register_workflows(workers)

    update_register_signature_models()


def update_register_signature_models():
    from orchestrator.hatchet.signature import SIGNATURES_NAME_MAPPING, TaskSignature
    from orchestrator.hatchet.chain import ChainTaskSignature
    from orchestrator.hatchet.swarm import SwarmTaskSignature, BatchItemTaskSignature

    signature_classes = [
        TaskSignature,
        ChainTaskSignature,
        SwarmTaskSignature,
        BatchItemTaskSignature,
    ]
    SIGNATURES_NAME_MAPPING.update(
        {
            signature_class.__name__: signature_class
            for signature_class in signature_classes
        }
    )
    for signature_class in SIGNATURES_NAME_MAPPING.values():
        signature_class.Meta.redis = orchestrator_config.redis_client


async def register_workflows(workflows: list):
    for workflow in workflows:
        if not hasattr(workflow, WORKER_FLAG_TO_STORE_NAME):
            continue
        orchestrator_task_name = getattr(workflow, WORKER_FLAG_TO_STORE_NAME)
        await asyncio.gather(
            store_task_name(
                orchestrator_config.redis_client, orchestrator_task_name, workflow.name
            ),
            store_input_validator(
                orchestrator_config.redis_client,
                orchestrator_task_name,
                workflow.input_validator,
            ),
        )


async def lifespan_initialize():
    await init_from_dynaconf()
    # yield makes the function usable as a Hatchet lifespan context manager (can alos be used for FastAPI):
    # - code before yield runs at startup (init config, register workers, etc.)
    # - code after yield would run at shutdown
    yield
