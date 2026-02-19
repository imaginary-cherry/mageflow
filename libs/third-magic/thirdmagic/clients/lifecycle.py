import abc
from abc import ABC
from typing import Any

from pydantic import BaseModel


class BaseLifecycle(ABC):
    @abc.abstractmethod
    async def start_task(self):
        pass

    @abc.abstractmethod
    async def task_success(self, result: Any):
        pass

    @abc.abstractmethod
    async def task_failed(self, message: BaseModel, error: Exception):
        pass

    @abc.abstractmethod
    async def should_run_task(self, message: BaseModel) -> bool:
        pass

    def is_vanilla_run(self):
        return False
