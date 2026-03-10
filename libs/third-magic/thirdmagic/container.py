import abc
import asyncio
from abc import ABC
from typing import Any

from rapyer.fields import RapyerKey

from thirdmagic.signature import Signature


class ContainerTaskSignature(Signature, ABC):
    @property
    @abc.abstractmethod
    def task_ids(self) -> list[RapyerKey]:
        pass

    @abc.abstractmethod
    async def sub_tasks(self) -> list[Signature]:
        pass

    async def remove_references(self):
        sub_tasks = await self.sub_tasks()
        await asyncio.gather(
            *[task.remove() for task in sub_tasks], return_exceptions=True
        )

    @abc.abstractmethod
    async def on_sub_task_error(
        self, sub_task: Signature, error: BaseException, original_msg: dict
    ):
        pass

    @abc.abstractmethod
    async def on_sub_task_done(self, sub_task: Signature, results: Any):
        pass
