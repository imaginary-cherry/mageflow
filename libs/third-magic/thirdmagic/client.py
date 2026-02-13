import abc
from abc import ABC

from pydantic import BaseModel

from thirdmagic.task import MageflowTaskDefinition


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

    def should_task_retry(
        self, task_definition: MageflowTaskDefinition, attempt_num: int, e: Exception
    ) -> bool:
        pass
