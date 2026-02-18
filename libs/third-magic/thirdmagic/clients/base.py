import abc
import asyncio
from abc import ABC
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from thirdmagic.task_def import MageflowTaskDefinition

if TYPE_CHECKING:
    from thirdmagic.task.model import TaskSignature
    from thirdmagic.chain.model import ChainTaskSignature
    from thirdmagic.swarm.model import SwarmTaskSignature
    from thirdmagic.utils import HatchetTaskType


class BaseClientAdapter(ABC):
    @abc.abstractmethod
    def extract_validator(self, client_task) -> type[BaseModel]:
        pass

    @abc.abstractmethod
    async def acall_chain_done(self, results: Any, chain: "ChainTaskSignature"):
        pass

    @abc.abstractmethod
    async def acall_chain_error(
        self,
        original_msg: Any,
        error: Exception,
        chain: "ChainTaskSignature",
        failed_task: "TaskSignature",
    ):
        pass

    @abc.abstractmethod
    async def astart_swarm(self, swarm: "SwarmTaskSignature", **kwargs):
        pass

    @abc.abstractmethod
    async def acall_swarm_item_error(
        self, error: Exception, swarm: "SwarmTaskSignature", swarm_item: "TaskSignature"
    ):
        pass

    @abc.abstractmethod
    async def acall_swarm_item_done(
        self, results: Any, swarm: "SwarmTaskSignature", swarm_item: "TaskSignature"
    ):
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
                signature.acall(msg, set_return_field, **kwargs)
                for signature, msg in zip(signatures, msgs)
            ]
        )

    @abc.abstractmethod
    def should_task_retry(
        self, task_definition: MageflowTaskDefinition, attempt_num: int, e: Exception
    ) -> bool:
        pass

    @abc.abstractmethod
    def task_name(self, task: "HatchetTaskType") -> str:
        pass


class DefaultClientAdapter(BaseClientAdapter):
    async def acall_chain_done(self, results: Any, chain: "ChainTaskSignature"):
        raise NotImplementedError("Set a client before we start")

    async def acall_chain_error(
        self,
        original_msg: Any,
        error: Exception,
        chain: "ChainTaskSignature",
        failed_task: "TaskSignature",
    ):
        raise NotImplementedError("Set a client before we start")

    async def astart_swarm(self, swarm: "SwarmTaskSignature", **kwargs):
        raise NotImplementedError("Set a client before we start")

    async def acall_swarm_item_error(
        self, error: Exception, swarm: "SwarmTaskSignature", swarm_item: "TaskSignature"
    ):
        raise NotImplementedError("Set a client before we start")

    async def acall_swarm_item_done(
        self, results: Any, swarm: "SwarmTaskSignature", swarm_item: "TaskSignature"
    ):
        raise NotImplementedError("Set a client before we start")

    def extract_validator(self, client_task) -> type[BaseModel]:
        raise NotImplementedError("Set a client before we start")

    async def acall_signature(
        self, signature: "TaskSignature", set_return_field: bool, **kwargs
    ):
        raise NotImplementedError("Set a client before we start")

    def should_task_retry(
        self, task_definition: MageflowTaskDefinition, attempt_num: int, e: Exception
    ) -> bool:
        raise NotImplementedError("Set a client before we start")

    def task_name(self, task: "HatchetTaskType") -> str:
        raise NotImplementedError("Set a client before we start")
