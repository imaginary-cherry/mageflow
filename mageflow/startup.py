from typing import Any

import rapyer
from pydantic import BaseModel
from redis.asyncio.client import Redis

from mageflow.backends.protocol import BackendType
from mageflow.task.model import HatchetTaskModel

# Registry for decorated tasks: (task_object, mageflow_task_name)
REGISTERED_TASKS: list[tuple[Any, str]] = []


class ConfigModel(BaseModel):
    class Config:
        arbitrary_types_allowed = True


class MageFlowConfigModel(ConfigModel):
    # Backend type (hatchet or taskiq)
    backend_type: str | None = None

    # Hatchet-specific
    hatchet_client: Any | None = None  # Hatchet client for workflow creation

    # TaskIQ-specific
    task_trigger: Any | None = None  # TaskIQTaskTrigger instance

    # Common
    redis_client: Redis | None = None


mageflow_config = MageFlowConfigModel()


async def init_mageflow():
    await rapyer.init_rapyer(mageflow_config.redis_client, prefer_normal_json_dump=True)
    await register_workflows()
    await update_register_signature_models()


async def teardown_mageflow():
    await rapyer.teardown_rapyer()


async def update_register_signature_models():
    from mageflow.signature.model import SIGNATURES_NAME_MAPPING, TaskSignature

    signature_classes = [
        cls for cls in rapyer.find_redis_models() if issubclass(cls, TaskSignature)
    ]
    SIGNATURES_NAME_MAPPING.update(
        {
            signature_class.__name__: signature_class
            for signature_class in signature_classes
        }
    )


async def register_workflows():
    """Register decorated tasks in Redis for runtime lookup."""
    for reg_task in REGISTERED_TASKS:
        task_obj, mageflow_task_name = reg_task

        # Get task metadata (works for both Hatchet and TaskIQ)
        task_name = getattr(task_obj, "name", mageflow_task_name)
        input_validator = getattr(task_obj, "input_validator", None)

        # Get retries - location varies by backend
        retries = None
        if hasattr(task_obj, "tasks") and task_obj.tasks:
            # Hatchet pattern: workflow.tasks[0].retries
            retries = getattr(task_obj.tasks[0], "retries", None)
        elif hasattr(task_obj, "retries"):
            # Direct attribute
            retries = task_obj.retries

        task_model = HatchetTaskModel(
            mageflow_task_name=mageflow_task_name,
            task_name=task_name,
            input_validator=input_validator,
            retries=retries,
        )
        await task_model.asave()


async def lifespan_initialize():
    await init_mageflow()
    # yield makes the function usable as a Hatchet lifespan context manager (can also be used for FastAPI):
    # - code before yield runs at startup (init config, register workers, etc.)
    # - code after yield would run at shutdown
    yield
    await teardown_mageflow()
