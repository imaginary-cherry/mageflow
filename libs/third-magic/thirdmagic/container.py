import abc
import asyncio
from abc import ABC
from typing import Any

from rapyer.actions import ActionGroup
from rapyer.config import RedisConfig
from rapyer.fields import RapyerKey

from thirdmagic.signature import Signature
from thirdmagic.signature.status import ContainerStatus

# Write actions that refresh (and cascade) a container's TTL; not READ/FETCH/DELETE.
CONTAINER_WRITE_ACTIONS = (
    ActionGroup.CREATE
    | ActionGroup.UPDATE
    | ActionGroup.APPEND
    | ActionGroup.ERASE
    | ActionGroup.ARITHMETIC
)


def container_ttl_cascade_meta() -> RedisConfig:
    # cascade is declared per-field via CascadeTTL(); init resets Meta.cascade_ttl.
    return RedisConfig(ttl=24 * 60 * 60, refresh_ttl=CONTAINER_WRITE_ACTIONS)


class ContainerTaskSignature(Signature, ABC):
    @property
    @abc.abstractmethod
    def task_ids(self) -> list[RapyerKey]:
        pass

    @abc.abstractmethod
    async def sub_tasks(self) -> list[Signature]:
        pass

    @abc.abstractmethod
    async def astatus(self) -> ContainerStatus:
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
