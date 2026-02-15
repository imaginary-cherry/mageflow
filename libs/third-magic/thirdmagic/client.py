import abc
import asyncio
from abc import ABC
from typing import TYPE_CHECKING

from pydantic import BaseModel

from thirdmagic.task import MageflowTaskDefinition

if TYPE_CHECKING:
    from thirdmagic.signatures.siganture import TaskSignature


class BaseClientAdapter(ABC):
    @abc.abstractmethod
    def extract_validator(self, client_task) -> type[BaseModel]:
        pass

    @abc.abstractmethod
    async def acall_task(self, client_task, **kwargs):
        pass

    @abc.abstractmethod
    async def acall_task_identifier(self, task_id: str, **kwargs):
        pass

    @abc.abstractmethod
    async def acall_signature(
        self, signature: "TaskSignature", set_return_field: bool, **kwargs
    ):
        pass

    async def acall_signatures(
        self,
        signatures: list["TaskSignature"],
        set_return_field: bool,
        msg_kwargs: list[dict],
    ):
        return asyncio.gather(
            *[
                self.acall_signature(signature, set_return_field, **kwargs)
                for signature, kwargs in zip(signatures, msg_kwargs)
            ]
        )

    @abc.abstractmethod
    def should_task_retry(
        self, task_definition: MageflowTaskDefinition, attempt_num: int, e: Exception
    ) -> bool:
        pass


class DefaultClientAdapter(BaseClientAdapter):
    def extract_validator(self, client_task) -> type[BaseModel]:
        raise NotImplementedError("Set a client before we start")

    async def acall_task(self, client_task, **kwargs):
        raise NotImplementedError("Set a client before we start")

    async def acall_task_identifier(self, task_id: str, **kwargs):
        raise NotImplementedError("Set a client before we start")

    async def acall_signature(
        self, signature: "TaskSignature", set_return_field: bool, **kwargs
    ):
        raise NotImplementedError("Set a client before we start")

    def should_task_retry(
        self, task_definition: MageflowTaskDefinition, attempt_num: int, e: Exception
    ) -> bool:
        raise NotImplementedError("Set a client before we start")
