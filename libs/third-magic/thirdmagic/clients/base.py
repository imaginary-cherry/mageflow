import abc
import asyncio
from abc import ABC
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from thirdmagic.clients.lifecycle import BaseLifecycle
from thirdmagic.task_def import MageflowTaskDefinition

if TYPE_CHECKING:
    from thirdmagic.chain.model import ChainTaskSignature
    from thirdmagic.signature import Signature
    from thirdmagic.swarm.model import SwarmTaskSignature
    from thirdmagic.task import TaskSignature
    from thirdmagic.utils import HatchetTaskType


class BaseClientAdapter(ABC):
    @abc.abstractmethod
    def extract_validator(self, client_task) -> type[BaseModel]:
        pass

    @abc.abstractmethod
    def extract_retries(self, client_task) -> int:
        pass

    @abc.abstractmethod
    async def acall_chain_done(self, results: Any, chain: "ChainTaskSignature"):
        pass

    @abc.abstractmethod
    async def acall_chain_error(
        self,
        original_msg: dict,
        error: BaseException,
        chain: "ChainTaskSignature",
        failed_task: "Signature",
    ):
        pass

    @abc.abstractmethod
    async def afill_swarm(
        self, swarm: "SwarmTaskSignature", max_tasks: int = None, **kwargs
    ):
        pass

    @abc.abstractmethod
    async def acall_swarm_item_error(
        self, error: BaseException, swarm: "SwarmTaskSignature", swarm_item: "Signature"
    ):
        pass

    @abc.abstractmethod
    async def acall_swarm_item_done(
        self, results: Any, swarm: "SwarmTaskSignature", swarm_item: "Signature"
    ):
        pass

    @abc.abstractmethod
    async def acall_signature(
        self, signature: "TaskSignature", msg: Any, set_return_field: bool, **kwargs
    ):
        pass

    async def acall_signatures(
        self,
        signatures: list["Signature"],
        msg: Any,
        set_return_field: bool,
        **kwargs,
    ):
        return await asyncio.gather(
            *[
                signature.acall(msg, set_return_field, **kwargs)
                for signature in signatures
            ]
        )

    @abc.abstractmethod
    def should_task_retry(
        self,
        task_definition: MageflowTaskDefinition,
        attempt_num: int,
        e: BaseException,
    ) -> bool:
        pass

    @abc.abstractmethod
    def task_name(self, task: "HatchetTaskType") -> str:
        pass

    @abc.abstractmethod
    async def create_lifecycle(self, *args) -> BaseLifecycle:
        pass

    @abc.abstractmethod
    async def lifecycle_from_signature(self, *args) -> BaseLifecycle:
        pass


class DefaultClientAdapter(BaseClientAdapter):
    async def acall_chain_done(self, results: Any, chain: "ChainTaskSignature"):
        raise NotImplementedError("Set a client before we start")

    async def acall_chain_error(
        self,
        original_msg: dict,
        error: BaseException,
        chain: "ChainTaskSignature",
        failed_task: "Signature",
    ):
        raise NotImplementedError("Set a client before we start")

    async def afill_swarm(
        self, swarm: "SwarmTaskSignature", max_tasks: int = None, **kwargs
    ):
        raise NotImplementedError("Set a client before we start")

    async def acall_swarm_item_error(
        self, error: BaseException, swarm: "SwarmTaskSignature", swarm_item: "Signature"
    ):
        raise NotImplementedError("Set a client before we start")

    async def acall_swarm_item_done(
        self, results: Any, swarm: "SwarmTaskSignature", swarm_item: "Signature"
    ):
        raise NotImplementedError("Set a client before we start")

    def extract_validator(self, client_task) -> type[BaseModel]:
        raise NotImplementedError("Set a client before we start")

    def extract_retries(self, client_task) -> int:
        raise NotImplementedError("Set a client before we start")

    async def acall_signature(
        self, signature: "Signature", set_return_field: bool, **kwargs
    ):
        raise NotImplementedError("Set a client before we start")

    def should_task_retry(
        self,
        task_definition: MageflowTaskDefinition,
        attempt_num: int,
        e: BaseException,
    ) -> bool:
        raise NotImplementedError("Set a client before we start")

    def task_name(self, task: "HatchetTaskType") -> str:
        raise NotImplementedError("Set a client before we start")

    def create_lifecycle(self, *args) -> BaseLifecycle:
        raise NotImplementedError("Set a client before we start")

    async def lifecycle_from_signature(self, *args) -> BaseLifecycle:
        pass
