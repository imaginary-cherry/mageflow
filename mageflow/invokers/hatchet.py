import asyncio
from typing import Any, cast

import rapyer
from hatchet_sdk import Context, Hatchet
from hatchet_sdk.runnables.contextvars import ctx_additional_metadata
from pydantic import BaseModel

from mageflow.invokers.base import BaseInvoker
from mageflow.signature.consts import TASK_ID_PARAM_NAME
from mageflow.signature.container import ContainerTaskSignature
from mageflow.signature.model import TaskSignature
from mageflow.signature.status import SignatureStatus
from mageflow.workflows import TASK_DATA_PARAM_NAME


class HatchetInvoker(BaseInvoker):
    # TODO - This should be in init, and the entire class created via factory in mageflow_config
    client: Hatchet = None

    def __init__(self, message: BaseModel, ctx: Context):
        self.message = message
        self.task_data = ctx.additional_metadata.get(TASK_DATA_PARAM_NAME, {})
        self.workflow_id = ctx.workflow_id
        hatchet_ctx_metadata = ctx_additional_metadata.get() or {}
        hatchet_ctx_metadata.pop(TASK_DATA_PARAM_NAME, None)
        ctx_additional_metadata.set(hatchet_ctx_metadata)

    @property
    def task_ctx(self) -> dict:
        return self.task_data

    @property
    def task_id(self) -> str | None:
        return self.task_data.get(TASK_ID_PARAM_NAME, None)

    def is_vanilla_run(self):
        return self.task_id is None

    async def start_task(self) -> TaskSignature | None:
        task_id = self.task_id
        if task_id:
            async with TaskSignature.alock_from_key(task_id) as signature:
                await signature.change_status(SignatureStatus.ACTIVE)
                await signature.task_status.aupdate(worker_task_id=self.workflow_id)
                return signature
        return None

    async def task_success(self, result: Any):
        success_publish_tasks = []
        task_id = self.task_id
        if task_id:
            current_task = await TaskSignature.get_safe(task_id)
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

    async def task_failed(self, error: Exception):
        task_id = self.task_id
        if task_id:
            error_publish_tasks = []

            current_task = await TaskSignature.get_safe(task_id)
            container_id = current_task.signature_container_id
            if container_id:
                container_signature = await rapyer.aget(container_id)
                container_signature = cast(ContainerTaskSignature, container_signature)
                error_publish_tasks.append(
                    container_signature.on_sub_task_error(
                        current_task, error, self.message
                    )
                )

            task_error_workflows = current_task.activate_error(self.message)
            error_publish_tasks.append(asyncio.create_task(task_error_workflows))

            if error_publish_tasks:
                await asyncio.gather(*error_publish_tasks)

            await current_task.failed()
            await current_task.remove(with_error=False)

    async def should_run_task(self) -> bool:
        task_id = self.task_id
        if task_id:
            signature = await TaskSignature.get_safe(task_id)
            if signature is None:
                return False
            should_task_run = await signature.should_run()
            if should_task_run:
                return True
            await signature.task_status.aupdate(last_status=SignatureStatus.ACTIVE)
            await signature.handle_inactive_task(self.message)
            return False
        return True

    @classmethod
    async def wait_task(
        cls, task_name: str, msg: BaseModel, validator: type[BaseModel] = None
    ):
        validator = validator or type(msg)
        wf = cls.client.workflow(name=task_name, input_validator=validator)
        return await wf.aio_run(msg)

    @classmethod
    async def run_task(
        cls, task_name: str, msg: BaseModel, validator: type[BaseModel] = None
    ):
        validator = validator or type(msg)
        wf = cls.client.workflow(name=task_name, input_validator=validator)
        return await wf.aio_run_no_wait(msg)
