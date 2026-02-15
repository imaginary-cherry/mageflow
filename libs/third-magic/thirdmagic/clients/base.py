import abc
import asyncio
from abc import ABC
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from thirdmagic.task import MageflowTaskDefinition
from thirdmagic.utils import HatchetTaskType

if TYPE_CHECKING:
    from thirdmagic.signatures.siganture import TaskSignature


class BaseClientAdapter(ABC):
    @abc.abstractmethod
    def extract_validator(self, client_task) -> type[BaseModel]:
        pass

    @abc.abstractmethod
    async def acall_task_identifier(self, task_id: str, **kwargs):
        pass

    @abc.abstractmethod
    async def acall_signature(
        self, signature: "TaskSignature", msg: Any, set_return_field: bool, **kwargs
    ):
        pass

    async def acall_signatures(
        self,
        signatures: list["TaskSignature"],
        msgs: list,
        set_return_field: bool,
        **kwargs,
    ):
        return asyncio.gather(
            *[
                self.acall_signature(signature, msg, set_return_field, **kwargs)
                for signature, msg in zip(signatures, msgs)
            ]
        )

    @abc.abstractmethod
    def should_task_retry(
        self, task_definition: MageflowTaskDefinition, attempt_num: int, e: Exception
    ) -> bool:
        pass

    @abc.abstractmethod
    def task_name(self, task: HatchetTaskType) -> str:
        pass


class DefaultClientAdapter(BaseClientAdapter):
    def extract_validator(self, client_task) -> type[BaseModel]:
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

    def task_name(self, task: HatchetTaskType) -> str:
        raise NotImplementedError("Set a client before we start")
