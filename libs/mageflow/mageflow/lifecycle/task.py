from typing import Any

from pydantic import BaseModel
from thirdmagic.clients.lifecycle import BaseLifecycle


class TaskLifecycle(BaseLifecycle):
    async def start_task(self):
        pass

    async def task_success(self, result: Any):
        pass

    async def task_failed(self, message: BaseModel, error: Exception):
        raise

    async def should_run_task(self, message: BaseModel) -> bool:
        pass
