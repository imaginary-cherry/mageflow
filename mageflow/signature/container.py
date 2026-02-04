import abc
import asyncio
from abc import ABC
from typing import Self, Any

from pydantic import BaseModel

from mageflow.signature.model import TaskSignature


class ContainerTaskSignature(TaskSignature, ABC):
    @abc.abstractmethod
    async def sub_tasks(self) -> list[Self]:
        pass

    async def remove_references(self):
        sub_tasks = await self.sub_tasks()
        await asyncio.gather(
            *[task.remove() for task in sub_tasks], return_exceptions=True
        )

    @abc.abstractmethod
    async def on_sub_task_error(
        self, sub_task: TaskSignature, error: Exception, original_msg: BaseModel
    ):
        pass

    @abc.abstractmethod
    async def on_sub_task_done(self, sub_task: TaskSignature, results: Any):
        pass
