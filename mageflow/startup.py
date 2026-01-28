"""
MageFlow startup and configuration module.

This module handles initialization and teardown of MageFlow,
including Redis connections and task registration for all backends.
"""

import rapyer
from pydantic import BaseModel
from redis.asyncio.client import Redis
from typing import Any, TYPE_CHECKING

from mageflow.task.model import HatchetTaskModel

if TYPE_CHECKING:
    from hatchet_sdk import Hatchet

REGISTERED_TASKS: list[tuple[Any, str]] = []


class ConfigModel(BaseModel):
    class Config:
        arbitrary_types_allowed = True


class MageFlowConfigModel(ConfigModel):
    """
    Global configuration model for MageFlow.

    Supports multiple backend clients through optional fields.
    """

    # Hatchet backend
    hatchet_client: Any | None = None  # Hatchet instance

    # TaskIQ backend
    taskiq_broker: Any | None = None  # TaskIQ broker instance

    # Shared resources
    redis_client: Redis | None = None


mageflow_config = MageFlowConfigModel()


async def init_mageflow():
    """Initialize MageFlow with Redis and register all workflows."""
    await rapyer.init_rapyer(mageflow_config.redis_client)
    await register_workflows()
    await update_register_signature_models()


async def teardown_mageflow():
    """Clean up MageFlow resources."""
    await rapyer.teardown_rapyer()


async def update_register_signature_models():
    """Update the signature model registry with all discovered models."""
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
    Register all workflows from REGISTERED_TASKS.

    This function handles both Hatchet and TaskIQ tasks,
    extracting metadata appropriately for each backend.
    """
    for reg_task in REGISTERED_TASKS:
        workflow, mageflow_task_name = reg_task

        # Extract task metadata based on backend type
        task_name = _get_task_name(workflow)
        input_validator = _get_input_validator(workflow)
        retries = _get_retries(workflow)

        task_model = HatchetTaskModel(
            mageflow_task_name=mageflow_task_name,
            task_name=task_name,
            input_validator=input_validator,
            retries=retries,
        )
        await task_model.save()


def _get_task_name(workflow: Any) -> str:
    """Extract task name from workflow object."""
    # Hatchet workflow
    if hasattr(workflow, "name"):
        return workflow.name
    # TaskIQ task
    if hasattr(workflow, "__mageflow_task_name__"):
        return workflow.__mageflow_task_name__
    if hasattr(workflow, "task_name"):
        return workflow.task_name
    # Fallback to function name
    if hasattr(workflow, "__name__"):
        return workflow.__name__
    return str(workflow)


def _get_input_validator(workflow: Any) -> Any:
    """Extract input validator from workflow object."""
    # Hatchet workflow
    if hasattr(workflow, "input_validator"):
        return workflow.input_validator
    # TaskIQ task
    if hasattr(workflow, "__mageflow_input_validator__"):
        return workflow.__mageflow_input_validator__
    return None


def _get_retries(workflow: Any) -> int:
    """Extract retry count from workflow object."""
    # Hatchet workflow
    if hasattr(workflow, "tasks") and workflow.tasks:
        return workflow.tasks[0].retries
    # TaskIQ task
    if hasattr(workflow, "__mageflow_retries__"):
        return workflow.__mageflow_retries__
    if hasattr(workflow, "max_retries"):
        return workflow.max_retries
    return 0


async def lifespan_initialize():
    """
    Lifespan context manager for MageFlow initialization.

    This can be used as a Hatchet lifespan context manager
    or integrated with FastAPI/other frameworks.

    Yields after initialization, then tears down on exit.
    """
    await init_mageflow()
    # yield makes the function usable as a lifespan context manager:
    # - code before yield runs at startup (init config, register workers, etc.)
    # - code after yield would run at shutdown
    yield
    await teardown_mageflow()
