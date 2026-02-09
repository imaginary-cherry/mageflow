import asyncio
import json
import logging
import uuid
from typing import Any

from pydantic import BaseModel

from mageflow.invokers.base import BaseInvoker, TaskClientAdapter
from mageflow.signature.consts import TASK_ID_PARAM_NAME
from mageflow.signature.model import TaskSignature
from mageflow.signature.status import SignatureStatus

logger = logging.getLogger(__name__)

TASK_DATA_HEADER_KEY = "mageflow_task_data"


class TemporalInvoker(BaseInvoker):
    """Per-execution invoker for Temporal activities/workflows."""

    def __init__(self, message: BaseModel, activity_info: Any):
        self.message = message
        self._activity_info = activity_info
        self.task_data = self._extract_task_data(activity_info)
        self.workflow_run_id = getattr(activity_info, "workflow_run_id", "")

    @staticmethod
    def _extract_task_data(activity_info: Any) -> dict:
        """Extract mageflow task_data from Temporal headers or search attributes."""
        # Temporal passes metadata via workflow headers
        headers = getattr(activity_info, "header", {}) or {}
        task_data_raw = headers.get(TASK_DATA_HEADER_KEY, None)
        if task_data_raw:
            if isinstance(task_data_raw, bytes):
                task_data_raw = task_data_raw.decode()
            if isinstance(task_data_raw, str):
                return json.loads(task_data_raw)
            return task_data_raw
        return {}

    @property
    def task_ctx(self) -> dict:
        return self.task_data

    @property
    def task_id(self) -> str | None:
        return self.task_data.get(TASK_ID_PARAM_NAME, None)

    def is_vanilla_run(self) -> bool:
        return self.task_id is None

    def get_attempt_number(self) -> int:
        return getattr(self._activity_info, "attempt", 1)

    async def cancel_current_task(self):
        try:
            from temporalio import activity

            activity.raise_complete_async()
        except ImportError:
            raise RuntimeError("temporalio is required for TemporalInvoker")

    async def log(self, message: str):
        logger.info(message)

    async def refresh_timeout(self, timeout):
        try:
            from temporalio import activity

            activity.heartbeat(f"timeout_refresh:{timeout}")
        except ImportError:
            pass

    async def start_task(self) -> TaskSignature | None:
        task_id = self.task_id
        if task_id:
            async with TaskSignature.alock_from_key(task_id) as signature:
                await signature.change_status(SignatureStatus.ACTIVE)
                await signature.task_status.aupdate(
                    worker_task_id=self.workflow_run_id
                )
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
        from temporalio.client import Client as TemporalClient

        client = TemporalClientAdapter._temporal_client
        if client is None:
            raise RuntimeError("Temporal client not configured")
        return await client.execute_workflow(
            task_name,
            msg.model_dump(mode="json"),
            id=f"{task_name}-{uuid.uuid4().hex[:12]}",
            task_queue=TemporalClientAdapter._task_queue,
        )


class TemporalClientAdapter(TaskClientAdapter):
    """
    Client-level adapter for Temporal task manager.

    Temporal concepts mapping:
    - task() -> Temporal workflow with a single activity
    - durable_task() -> Temporal workflow with heartbeating activity
    - worker() -> Temporal Worker
    - run_task_no_wait -> client.start_workflow()
    - run_task_and_wait -> client.execute_workflow()
    """

    _temporal_client = None
    _task_queue: str = "mageflow"

    def __init__(self, temporal_client, task_queue: str = "mageflow"):
        self.client = temporal_client
        TemporalClientAdapter._temporal_client = temporal_client
        TemporalClientAdapter._task_queue = task_queue
        self.task_queue = task_queue
        self._registered_workflows = {}
        self._registered_activities = {}

    def task(self, name: str, **kwargs):
        """
        Returns a decorator that registers a function as a Temporal workflow
        wrapping a single activity.
        """

        def decorator(func):
            self._registered_activities[name] = {
                "func": func,
                "name": name,
                "kwargs": kwargs,
                "durable": False,
            }
            func._temporal_task_name = name
            func._temporal_kwargs = kwargs
            func._temporal_durable = False
            func._temporal_input_validator = kwargs.get("input_validator")
            func._temporal_retries = kwargs.get("retries", 0)
            return func

        return decorator

    def durable_task(self, name: str, **kwargs):
        """
        Returns a decorator that registers a function as a Temporal workflow
        with heartbeating enabled (for long-running activities).
        """

        def decorator(func):
            self._registered_activities[name] = {
                "func": func,
                "name": name,
                "kwargs": kwargs,
                "durable": True,
            }
            func._temporal_task_name = name
            func._temporal_kwargs = kwargs
            func._temporal_durable = True
            func._temporal_input_validator = kwargs.get("input_validator")
            func._temporal_retries = kwargs.get("retries", 0)
            return func

        return decorator

    def worker(self, name: str, **kwargs):
        """
        Create a Temporal Worker.

        Returns a configured temporalio.worker.Worker that can be started.
        """
        try:
            from temporalio.worker import Worker as TemporalWorker
        except ImportError:
            raise RuntimeError(
                "temporalio is required. Install with: pip install temporalio"
            )

        # Collect all registered activities
        activities = []
        for task_info in self._registered_activities.values():
            activities.append(task_info["func"])

        # Collect workflows from kwargs
        workflows = kwargs.pop("workflows", []) or []

        return TemporalWorker(
            self.client,
            task_queue=self.task_queue,
            workflows=workflows,
            activities=activities,
            **kwargs,
        )

    def create_invoker(self, message: BaseModel, ctx: Any) -> TemporalInvoker:
        return TemporalInvoker(message, ctx)

    async def run_task_no_wait(
        self,
        task_name: str,
        msg: BaseModel,
        task_ctx: dict = None,
        input_validator: type[BaseModel] = None,
        extra_params: dict = None,
        return_value_field: str = None,
    ):
        """Start a Temporal workflow without waiting for completion."""
        input_data = msg.model_dump(mode="json")
        if extra_params:
            input_data.update(extra_params)
        if return_value_field:
            input_data = {return_value_field: input_data}

        # Pass mageflow task context via headers
        headers = {}
        if task_ctx:
            headers[TASK_DATA_HEADER_KEY] = json.dumps(task_ctx)

        workflow_id = f"{task_name}-{uuid.uuid4().hex[:12]}"

        handle = await self.client.start_workflow(
            task_name,
            input_data,
            id=workflow_id,
            task_queue=self.task_queue,
            headers=headers,
        )
        return handle

    async def run_task_and_wait(
        self,
        task_name: str,
        msg: BaseModel,
        input_validator: type[BaseModel] = None,
    ):
        """Start a Temporal workflow and wait for it to complete."""
        input_data = msg.model_dump(mode="json")
        workflow_id = f"{task_name}-{uuid.uuid4().hex[:12]}"
        return await self.client.execute_workflow(
            task_name,
            input_data,
            id=workflow_id,
            task_queue=self.task_queue,
        )

    def init_internal_tasks(self) -> list:
        """Register mageflow internal workflows as Temporal activities."""
        from mageflow.callbacks import register_task
        from mageflow.chain.consts import ON_CHAIN_END, ON_CHAIN_ERROR
        from mageflow.chain.workflows import chain_end_task, chain_error_task
        from mageflow.swarm.consts import (
            ON_SWARM_ERROR,
            ON_SWARM_END,
            ON_SWARM_START,
            SWARM_FILL_TASK,
        )
        from mageflow.swarm.workflows import (
            swarm_item_failed,
            swarm_item_done,
            swarm_start_tasks,
            fill_swarm_running_tasks,
        )

        internal_tasks = []

        # Chain tasks
        chain_done_dec = self.task(name=ON_CHAIN_END, retries=3)
        chain_error_dec = self.task(name=ON_CHAIN_ERROR, retries=3)
        chain_done_fn = chain_done_dec(chain_end_task)
        chain_error_fn = chain_error_dec(chain_error_task)
        chain_done_fn = register_task(ON_CHAIN_END)(chain_done_fn)
        chain_error_fn = register_task(ON_CHAIN_ERROR)(chain_error_fn)
        internal_tasks.extend([chain_error_fn, chain_done_fn])

        # Swarm tasks
        swarm_start_dec = self.durable_task(name=ON_SWARM_START, retries=3)
        swarm_done_dec = self.durable_task(name=ON_SWARM_END, retries=5)
        swarm_error_dec = self.durable_task(name=ON_SWARM_ERROR, retries=5)
        swarm_fill_dec = self.durable_task(name=SWARM_FILL_TASK, retries=4)

        swarm_start_fn = swarm_start_dec(swarm_start_tasks)
        swarm_done_fn = swarm_done_dec(swarm_item_done)
        swarm_error_fn = swarm_error_dec(swarm_item_failed)
        swarm_fill_fn = swarm_fill_dec(fill_swarm_running_tasks)

        swarm_start_fn = register_task(ON_SWARM_START)(swarm_start_fn)
        swarm_done_fn = register_task(ON_SWARM_END)(swarm_done_fn)
        swarm_error_fn = register_task(ON_SWARM_ERROR)(swarm_error_fn)

        internal_tasks.extend([swarm_start_fn, swarm_done_fn, swarm_error_fn, swarm_fill_fn])

        return internal_tasks

    def get_task_name(self, workflow_or_func) -> str:
        temporal_name = getattr(workflow_or_func, "_temporal_task_name", None)
        if temporal_name:
            return temporal_name
        return getattr(workflow_or_func, "__name__", str(workflow_or_func))

    def get_input_validator(self, workflow_or_func) -> type[BaseModel] | None:
        return getattr(workflow_or_func, "_temporal_input_validator", None)

    def get_retries(self, workflow_or_func) -> int | None:
        return getattr(workflow_or_func, "_temporal_retries", None)
