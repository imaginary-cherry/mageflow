import asyncio
from datetime import timedelta
from typing import Any

from hatchet_sdk import Context, Hatchet
from hatchet_sdk.runnables.contextvars import ctx_additional_metadata
from hatchet_sdk.runnables.types import (
    ConcurrencyExpression,
    ConcurrencyLimitStrategy,
)
from hatchet_sdk.runnables.workflow import BaseWorkflow
from pydantic import BaseModel

from mageflow.invokers.base import BaseInvoker, TaskClientAdapter
from mageflow.signature.consts import TASK_ID_PARAM_NAME
from mageflow.signature.model import TaskSignature
from mageflow.signature.status import SignatureStatus
from mageflow.workflows import MageflowWorkflow, TASK_DATA_PARAM_NAME


class HatchetInvoker(BaseInvoker):
    """Per-execution invoker for Hatchet tasks."""

    # TODO - This should be in init, and the entire class created via factory in mageflow_config
    client: Hatchet = None

    def __init__(self, message: BaseModel, ctx: Context):
        self.message = message
        self.ctx = ctx
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

    def get_attempt_number(self) -> int:
        return self.ctx.attempt_number

    async def cancel_current_task(self):
        await self.ctx.aio_cancel()

    async def log(self, message: str):
        self.ctx.log(message)

    async def refresh_timeout(self, timeout):
        self.ctx.refresh_timeout(timeout)

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
            task_success_workflows = current_task.activate_success(result)
            success_publish_tasks.append(asyncio.create_task(task_success_workflows))

            if success_publish_tasks:
                await asyncio.gather(*success_publish_tasks)

            await current_task.remove(with_success=False)

    async def task_failed(self):
        error_publish_tasks = []
        task_id = self.task_id
        if task_id:
            current_task = await TaskSignature.get_safe(task_id)
            task_error_workflows = current_task.activate_error(self.message)
            error_publish_tasks.append(asyncio.create_task(task_error_workflows))

            if error_publish_tasks:
                await asyncio.gather(*error_publish_tasks)

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

    async def wait_task(
        self, task_name: str, msg: BaseModel, validator: type[BaseModel] = None
    ):
        wf = self.client.workflow(name=task_name, input_validator=validator)
        return await wf.aio_run(msg)


class HatchetClientAdapter(TaskClientAdapter):
    """Client-level adapter for Hatchet task manager."""

    def __init__(self, hatchet_client: Hatchet, hatchet_caller: Hatchet = None):
        self.client = hatchet_client
        # hatchet_caller has empty namespace for creating workflows
        self.caller = hatchet_caller or hatchet_client

    def task(self, name: str, **kwargs):
        return self.client.task(name=name, **kwargs)

    def durable_task(self, name: str, **kwargs):
        return self.client.durable_task(name=name, **kwargs)

    def worker(self, name: str, **kwargs):
        return self.client.worker(name, **kwargs)

    def create_invoker(self, message: BaseModel, ctx: Any) -> HatchetInvoker:
        return HatchetInvoker(message, ctx)

    async def run_task_no_wait(
        self,
        task_name: str,
        msg: BaseModel,
        task_ctx: dict = None,
        input_validator: type[BaseModel] = None,
        extra_params: dict = None,
        return_value_field: str = None,
    ):
        workflow = self.caller.workflow(
            name=task_name, input_validator=input_validator
        )
        mageflow_wf = MageflowWorkflow(
            workflow,
            workflow_params=extra_params or {},
            return_value_field=return_value_field,
            task_ctx=task_ctx,
        )
        return await mageflow_wf.aio_run_no_wait(msg)

    async def run_task_and_wait(
        self,
        task_name: str,
        msg: BaseModel,
        input_validator: type[BaseModel] = None,
    ):
        wf = self.caller.workflow(name=task_name, input_validator=input_validator)
        return await wf.aio_run(msg)

    def init_internal_tasks(self) -> list:
        from mageflow.callbacks import register_task
        from mageflow.chain.consts import ON_CHAIN_END, ON_CHAIN_ERROR
        from mageflow.chain.messages import ChainCallbackMessage
        from mageflow.chain.workflows import chain_end_task, chain_error_task
        from mageflow.swarm.consts import (
            ON_SWARM_ERROR,
            ON_SWARM_END,
            ON_SWARM_START,
            SWARM_FILL_TASK,
            SWARM_TASK_ID_PARAM_NAME,
        )
        from mageflow.swarm.messages import SwarmResultsMessage, SwarmMessage
        from mageflow.swarm.workflows import (
            swarm_item_failed,
            swarm_item_done,
            swarm_start_tasks,
            fill_swarm_running_tasks,
        )

        # Chain tasks
        hatchet_chain_done = self.client.task(
            name=ON_CHAIN_END,
            input_validator=ChainCallbackMessage,
            retries=3,
            execution_timeout=timedelta(minutes=5),
        )
        hatchet_chain_error = self.client.task(
            name=ON_CHAIN_ERROR,
            retries=3,
            execution_timeout=timedelta(minutes=5),
        )
        chain_done_task = hatchet_chain_done(chain_end_task)
        on_chain_error_task = hatchet_chain_error(chain_error_task)
        chain_done_task = register_task(ON_CHAIN_END)(chain_done_task)
        on_chain_error_task = register_task(ON_CHAIN_ERROR)(on_chain_error_task)

        # Swarm tasks
        swarm_start = self.client.durable_task(
            name=ON_SWARM_START,
            retries=3,
            execution_timeout=timedelta(minutes=5),
            concurrency=ConcurrencyExpression(
                expression=f"input.{SWARM_TASK_ID_PARAM_NAME}",
                max_runs=1,
                limit_strategy=ConcurrencyLimitStrategy.CANCEL_NEWEST,
            ),
        )
        swarm_done = self.client.durable_task(
            name=ON_SWARM_END,
            input_validator=SwarmResultsMessage,
            retries=5,
            execution_timeout=timedelta(minutes=1),
        )
        swarm_error = self.client.durable_task(
            name=ON_SWARM_ERROR,
            retries=5,
            execution_timeout=timedelta(minutes=5),
        )
        swarm_start = swarm_start(swarm_start_tasks)
        swarm_done = swarm_done(swarm_item_done)
        swarm_error = swarm_error(swarm_item_failed)
        swarm_start = register_task(ON_SWARM_START)(swarm_start)
        swarm_done = register_task(ON_SWARM_END)(swarm_done)
        swarm_error = register_task(ON_SWARM_ERROR)(swarm_error)

        swarm_fill_task = self.client.durable_task(
            name=SWARM_FILL_TASK,
            input_validator=SwarmMessage,
            retries=4,
            concurrency=ConcurrencyExpression(
                expression=f"input.{SWARM_TASK_ID_PARAM_NAME}",
                max_runs=2,
                limit_strategy=ConcurrencyLimitStrategy.CANCEL_NEWEST,
            ),
        )
        swarm_fill_task = swarm_fill_task(fill_swarm_running_tasks)

        return [
            on_chain_error_task,
            chain_done_task,
            swarm_start,
            swarm_done,
            swarm_error,
            swarm_fill_task,
        ]

    def get_task_name(self, workflow_or_func) -> str:
        if isinstance(workflow_or_func, BaseWorkflow):
            return workflow_or_func.name
        return getattr(workflow_or_func, "__name__", str(workflow_or_func))

    def get_input_validator(self, workflow_or_func) -> type[BaseModel] | None:
        if isinstance(workflow_or_func, BaseWorkflow):
            return workflow_or_func.input_validator
        return None

    def get_retries(self, workflow_or_func) -> int | None:
        if isinstance(workflow_or_func, BaseWorkflow):
            tasks = getattr(workflow_or_func, "tasks", [])
            if tasks:
                return tasks[0].retries
        return None
