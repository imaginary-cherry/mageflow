import abc
import asyncio
from abc import ABC
from typing import Any, cast, Optional

import rapyer
from pydantic import BaseModel

from mageflow.signature.container import ContainerTaskSignature
from mageflow.signature.model import TaskSignature
from mageflow.signature.status import SignatureStatus


class BaseInvoker(ABC):
    @classmethod
    @abc.abstractmethod
    def from_task_data(cls, *args, **kwargs) -> "BaseInvoker":
        pass

    @abc.abstractmethod
    async def task_signature(self) -> Optional[TaskSignature]:
        pass

    @abc.abstractmethod
    async def start_task(self):
        pass

    async def task_success(self, result: Any):
        success_publish_tasks = []
        current_task = await self.task_signature()
        if current_task:
            container_id = current_task.signature_container_id
            if container_id:
                container_signature = await rapyer.aget(container_id)
                container_signature = cast(ContainerTaskSignature, container_signature)
                success_publish_tasks.append(
                    container_signature.on_sub_task_done(current_task, result)
                )

            task_success_workflows = current_task.activate_success(result)
            success_publish_tasks.append(asyncio.create_task(task_success_workflows))

            if success_publish_tasks:
                await asyncio.gather(*success_publish_tasks)

            await current_task.done()
            await current_task.remove(with_success=False)

    async def task_failed(self, message: BaseModel, error: Exception):
        current_task = await self.task_signature()
        if current_task:
            error_publish_tasks = []

            container_id = current_task.signature_container_id
            if container_id:
                container_signature = await rapyer.aget(container_id)
                container_signature = cast(ContainerTaskSignature, container_signature)
                error_publish_tasks.append(
                    container_signature.on_sub_task_error(current_task, error, message)
                )

            task_error_workflows = current_task.activate_error(message)
            error_publish_tasks.append(asyncio.create_task(task_error_workflows))

            if error_publish_tasks:
                await asyncio.gather(*error_publish_tasks)

            await current_task.failed()
            await current_task.remove(with_error=False)

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
