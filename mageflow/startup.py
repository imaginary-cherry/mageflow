from typing import Any

import rapyer
from pydantic import BaseModel
from redis.asyncio.client import Redis

from mageflow.invokers.base import TaskClientAdapter
from mageflow.task.model import MageflowTaskModel

REGISTERED_TASKS: list[tuple[Any, str]] = []


class ConfigModel(BaseModel):
    class Config:
        arbitrary_types_allowed = True


class MageFlowConfigModel(ConfigModel):
    adapter: TaskClientAdapter | None = None
    redis_client: Redis | None = None

    @property
    def hatchet_client(self):
        """Backward-compatible read accessor for the underlying client."""
        if self.adapter is None:
            return None
        return getattr(self.adapter, "caller", getattr(self.adapter, "client", None))

    @hatchet_client.setter
    def hatchet_client(self, value):
        """
        Backward-compatible write accessor.

        If a raw Hatchet client is assigned, wrap it in a HatchetClientAdapter.
        """
        if value is None:
            return
        if isinstance(value, TaskClientAdapter):
            self.adapter = value
            return
        # Assume it's a Hatchet client
        try:
            from mageflow.invokers.hatchet import HatchetClientAdapter

            if self.adapter is None or not isinstance(self.adapter, HatchetClientAdapter):
                self.adapter = HatchetClientAdapter(value, value)
            else:
                # Update the caller on existing adapter
                self.adapter.caller = value
        except ImportError:
            pass


mageflow_config = MageFlowConfigModel()


async def init_mageflow():
    await rapyer.init_rapyer(mageflow_config.redis_client, prefer_normal_json_dump=True)
    await register_workflows()


async def teardown_mageflow():
    await rapyer.teardown_rapyer()


async def register_workflows():
    adapter = mageflow_config.adapter
    for reg_task in REGISTERED_TASKS:
        workflow, mageflow_task_name = reg_task
        if adapter:
            task_name = adapter.get_task_name(workflow)
            input_validator = adapter.get_input_validator(workflow)
            retries = adapter.get_retries(workflow)
        else:
            # Fallback for direct attribute access (backward compat)
            task_name = getattr(workflow, "name", mageflow_task_name)
            input_validator = getattr(workflow, "input_validator", None)
            tasks_list = getattr(workflow, "tasks", [])
            retries = tasks_list[0].retries if tasks_list else None

        task_model = MageflowTaskModel(
            mageflow_task_name=mageflow_task_name,
            task_name=task_name,
            input_validator=input_validator,
            retries=retries,
        )
        await task_model.asave()


async def lifespan_initialize():
    await init_mageflow()
    # yield makes the function usable as a lifespan context manager (Hatchet or FastAPI):
    # - code before yield runs at startup (init config, register workers, etc.)
    # - code after yield would run at shutdown
    yield
    await teardown_mageflow()
