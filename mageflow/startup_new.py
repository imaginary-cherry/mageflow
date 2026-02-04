"""
Mageflow startup and initialization - task manager agnostic version.

This module handles the initialization of Mageflow, including:
- Redis/rapyer setup
- Task registration
- Signature model registration

It's designed to work with any task manager adapter.
"""
import rapyer
from pydantic import BaseModel
from redis.asyncio.client import Redis
from typing import Any, TYPE_CHECKING

from mageflow.task.model_new import TaskModel

if TYPE_CHECKING:
    from mageflow.adapters.protocols import TaskManagerAdapter


# Registry for tasks that have been decorated
REGISTERED_TASKS: list[tuple[Any, str]] = []


class ConfigModel(BaseModel):
    """Base configuration model allowing arbitrary types."""

    class Config:
        arbitrary_types_allowed = True


class MageFlowConfigModel(ConfigModel):
    """
    Global Mageflow configuration.

    This stores shared configuration that needs to be accessed across
    the package. It's task-manager-agnostic.
    """

    task_adapter: Any = None
    """The task manager adapter (TaskManagerAdapter)"""

    redis_client: Redis | None = None
    """Redis client for state management"""

    # Backwards compatibility for Hatchet
    hatchet_client: Any = None
    """Hatchet client (for backwards compatibility)"""


mageflow_config = MageFlowConfigModel()


async def init_mageflow():
    """
    Initialize Mageflow.

    This should be called during worker startup (via lifespan).
    It sets up rapyer/Redis and registers tasks.
    """
    await rapyer.init_rapyer(mageflow_config.redis_client, prefer_normal_json_dump=True)
    await register_workflows()
    await update_register_signature_models()


async def teardown_mageflow():
    """
    Teardown Mageflow.

    This should be called during worker shutdown (via lifespan).
    """
    await rapyer.teardown_rapyer()


async def update_register_signature_models():
    """
    Update the signature model registry.

    This scans for TaskSignature subclasses and registers them
    for polymorphic deserialization.
    """
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
    """
    Register decorated tasks in Redis.

    This creates TaskModel entries for all registered tasks so they
    can be looked up at runtime for retry logic, etc.
    """
    for reg_task in REGISTERED_TASKS:
        workflow, mageflow_task_name = reg_task

        # Get task metadata from the workflow/task object
        # This works for both Hatchet and TaskIQ
        task_name = getattr(workflow, "name", mageflow_task_name)
        input_validator = getattr(workflow, "input_validator", None)

        # Get retries - location varies by task manager
        retries = None
        if hasattr(workflow, "tasks") and workflow.tasks:
            # Hatchet pattern
            retries = getattr(workflow.tasks[0], "retries", None)
        elif hasattr(workflow, "retries"):
            retries = workflow.retries

        task_model = TaskModel(
            mageflow_task_name=mageflow_task_name,
            task_name=task_name,
            input_validator=input_validator,
            retries=retries,
        )
        await task_model.asave()


async def lifespan_initialize():
    """
    Lifespan context manager for worker initialization.

    This can be used with both Hatchet and FastAPI-style lifespans.

    Usage:
        worker = mage.worker("my-worker", lifespan=lifespan_initialize)
    """
    await init_mageflow()
    yield
    await teardown_mageflow()
