import abc
from abc import ABC
from typing import Self

from mageflow.signature.model import TaskSignature


class ContainerTaskSignature(TaskSignature, ABC):
    @abc.abstractmethod
    async def sub_tasks(self) -> list[Self]:
        pass
