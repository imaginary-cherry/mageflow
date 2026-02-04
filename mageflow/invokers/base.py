import abc
from abc import ABC
from typing import Any

from pydantic import BaseModel


class BaseInvoker(ABC):
    @property
    @abc.abstractmethod
    def task_ctx(self) -> dict:
        pass

    @abc.abstractmethod
    async def start_task(self):
        pass

    @abc.abstractmethod
    async def task_success(self, result: Any):
        pass

    @abc.abstractmethod
    async def task_failed(self):
        pass

    @abc.abstractmethod
    async def should_run_task(self) -> bool:
        pass

    @classmethod
    @abc.abstractmethod
    async def wait_task(
        cls, task_name: str, msg: BaseModel, validator: type[BaseModel] = None
    ):
        pass

    @classmethod
    @abc.abstractmethod
    async def run_task(
        cls, task_name: str, msg: BaseModel, validator: type[BaseModel] = None
    ):
        pass
