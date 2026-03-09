import asyncio
from typing import Any, Optional, cast

import rapyer
from thirdmagic.clients.lifecycle import BaseLifecycle
from thirdmagic.container import ContainerTaskSignature
from thirdmagic.signature import Signature
from thirdmagic.task import SignatureStatus


class SignatureLifecycle(BaseLifecycle):
    def __init__(
        self,
        workflow_id: Optional[str],
        signature: Signature,
        container: Optional[ContainerTaskSignature],
    ):
        self.signature = signature
        self.container = container
        self.workflow_id = workflow_id

    def __str__(self):
        return f"SignatureLifecycle(workflow_id={self.workflow_id}, task_name={self.signature.task_name})"

    async def start_task(self) -> Signature | None:
        async with self.signature.apipeline() as signature:
            await signature.change_status(SignatureStatus.ACTIVE)
            signature.worker_task_id = self.workflow_id
            return signature

    async def task_success(self, result: Any):
        success_publish_tasks = []
        current_task = self.signature
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

    async def task_failed(self, message: dict, error: BaseException):
        current_task = self.signature
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

    async def should_run_task(self, message: dict) -> bool:
        signature = self.signature
        should_task_run = await signature.should_run()
        if should_task_run:
            return True
        await signature.task_status.aupdate(last_status=SignatureStatus.ACTIVE)

        # Update for resume
        if signature.task_status.status == SignatureStatus.SUSPENDED:
            await signature.on_pause_signature(message)
        elif signature.task_status.status == SignatureStatus.CANCELED:
            await signature.on_cancel_signature(message)

        return False
