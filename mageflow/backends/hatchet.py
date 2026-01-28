"""
Hatchet backend implementation for MageFlow.

This module provides the Hatchet-specific implementation of the BackendClient
interface, enabling MageFlow to work with Hatchet as its task execution backend.
"""

from datetime import timedelta
from typing import Any, Callable, cast

from hatchet_sdk import Hatchet, Context, Worker
from hatchet_sdk.clients.admin import TriggerWorkflowOptions
from hatchet_sdk.runnables.contextvars import ctx_additional_metadata
from hatchet_sdk.runnables.types import EmptyModel
from hatchet_sdk.runnables.workflow import Workflow, BaseWorkflow
from hatchet_sdk.utils.typing import JSONSerializableMapping
from pydantic import BaseModel

from mageflow.backends.base import (
    BackendClient,
    BackendType,
    TaskContext,
    WorkflowWrapper,
    WorkerWrapper,
)
from mageflow.utils.pythonic import deep_merge

TASK_DATA_PARAM_NAME = "task_data"


class ModelToDump(BaseModel):
    value: Any


class HatchetWorkflowWrapper(Workflow):
    """
    Hatchet-specific workflow wrapper that implements the WorkflowWrapper protocol.

    This class wraps a Hatchet Workflow and adds MageFlow-specific functionality
    like task context injection and parameter merging.
    """

    def __init__(
        self,
        workflow: Workflow,
        workflow_params: dict | None = None,
        return_value_field: str | None = None,
        task_ctx: dict | None = None,
    ):
        super().__init__(config=workflow.config, client=workflow.client)
        self._mageflow_workflow_params = workflow_params or {}
        self._return_value_field = return_value_field
        self._task_ctx = task_ctx or {}

    def _serialize_input(self, input: Any) -> JSONSerializableMapping:
        if isinstance(input, BaseModel):
            input = super(HatchetWorkflowWrapper, self)._serialize_input(input)

        # Force model dump
        kwargs = self._mageflow_workflow_params
        results_model = ModelToDump(value=kwargs)
        extra_params = super(HatchetWorkflowWrapper, self)._serialize_input(results_model)
        dumped_kwargs = extra_params["value"]

        if self._return_value_field:
            return_field = {self._return_value_field: input}
        else:
            return_field = input

        return deep_merge(return_field, dumped_kwargs)

    def _update_options(self, options: TriggerWorkflowOptions) -> TriggerWorkflowOptions:
        if self._task_ctx:
            options.additional_metadata[TASK_DATA_PARAM_NAME] = self._task_ctx
        return options

    def run(
        self,
        input: Any = cast(Any, EmptyModel()),
        options: TriggerWorkflowOptions | None = None,
    ):
        if options is None:
            options = TriggerWorkflowOptions()
        options = self._update_options(options)
        return super().run(input, options)

    def run_no_wait(
        self,
        input: Any = cast(Any, EmptyModel()),
        options: TriggerWorkflowOptions | None = None,
    ):
        if options is None:
            options = TriggerWorkflowOptions()
        options = self._update_options(options)
        return super().run_no_wait(input, options)

    async def aio_run_no_wait(
        self,
        input: Any = cast(Any, EmptyModel()),
        options: TriggerWorkflowOptions | None = None,
    ):
        if options is None:
            options = TriggerWorkflowOptions()
        options = self._update_options(options)
        return await super().aio_run_no_wait(input, options)

    async def aio_run(
        self,
        input: Any = cast(Any, EmptyModel()),
        options: TriggerWorkflowOptions | None = None,
    ):
        if options is None:
            options = TriggerWorkflowOptions()
        options = self._update_options(options)
        return await super().aio_run(input, options)


class HatchetBackend(BackendClient[Hatchet]):
    """
    Hatchet backend implementation for MageFlow.

    This class implements the BackendClient interface for Hatchet,
    providing all necessary operations for task orchestration.
    """

    backend_type = BackendType.HATCHET

    def __init__(self, hatchet_client: Hatchet):
        super().__init__(hatchet_client)

    def create_workflow(
        self,
        name: str,
        input_validator: type[BaseModel] | None = None,
        workflow_params: dict | None = None,
        return_value_field: str | None = None,
        task_ctx: dict | None = None,
    ) -> WorkflowWrapper:
        """Create a Hatchet workflow wrapper."""
        workflow = self._native_client.workflow(
            name=name, input_validator=input_validator
        )
        return HatchetWorkflowWrapper(
            workflow,
            workflow_params=workflow_params,
            return_value_field=return_value_field,
            task_ctx=task_ctx,
        )

    def create_task_decorator(
        self,
        name: str | None = None,
        input_validator: type[BaseModel] | None = None,
        retries: int = 0,
        **kwargs,
    ) -> Callable:
        """Create a Hatchet task decorator."""
        return self._native_client.task(
            name=name, input_validator=input_validator, retries=retries, **kwargs
        )

    def create_durable_task_decorator(
        self,
        name: str | None = None,
        input_validator: type[BaseModel] | None = None,
        retries: int = 0,
        **kwargs,
    ) -> Callable:
        """Create a Hatchet durable task decorator."""
        return self._native_client.durable_task(
            name=name, input_validator=input_validator, retries=retries, **kwargs
        )

    def create_worker(
        self,
        workflows: list[BaseWorkflow[Any]] | None = None,
        lifespan: Callable | None = None,
        **kwargs,
    ) -> Worker:
        """Create a Hatchet worker."""
        return self._native_client.worker(
            workflows=workflows, lifespan=lifespan, **kwargs
        )

    def create_task_context(self, message: BaseModel, raw_ctx: Context) -> TaskContext:
        """Create a unified TaskContext from Hatchet Context."""
        task_data = raw_ctx.additional_metadata.get(TASK_DATA_PARAM_NAME, {})

        # Clean up context metadata
        hatchet_ctx_metadata = ctx_additional_metadata.get() or {}
        hatchet_ctx_metadata.pop(TASK_DATA_PARAM_NAME, None)
        ctx_additional_metadata.set(hatchet_ctx_metadata)

        return TaskContext(
            task_id=task_data.get("task_id"),
            workflow_id=raw_ctx.workflow_id,
            attempt_number=raw_ctx.attempt_number,
            additional_metadata=task_data,
            raw_context=raw_ctx,
        )

    def extract_task_data(self, ctx: TaskContext) -> dict:
        """Extract MageFlow task data from the context."""
        return ctx.additional_metadata

    async def cancel_task(self, ctx: TaskContext) -> None:
        """Cancel the current task execution using Hatchet context."""
        if ctx.raw_context:
            await ctx.raw_context.aio_cancel()

    def get_job_name(self, ctx: TaskContext) -> str:
        """Get the job name from Hatchet context."""
        if ctx.raw_context:
            return ctx.raw_context.action.job_name
        return ""

    def log(self, ctx: TaskContext, message: str) -> None:
        """Log a message using Hatchet context."""
        if ctx.raw_context:
            ctx.raw_context.log(message)

    def refresh_timeout(self, ctx: TaskContext, seconds: float) -> None:
        """Refresh the task timeout using Hatchet context."""
        if ctx.raw_context:
            ctx.raw_context.refresh_timeout(timedelta(seconds=seconds))

    def init_mageflow_tasks(self) -> list[Any]:
        """Initialize MageFlow internal tasks for Hatchet."""
        from mageflow.callbacks import register_task
        from mageflow.chain.consts import ON_CHAIN_END, ON_CHAIN_ERROR
        from mageflow.chain.messages import ChainSuccessTaskCommandMessage
        from mageflow.chain.workflows import chain_end_task, chain_error_task
        from mageflow.swarm.consts import ON_SWARM_ERROR, ON_SWARM_END, ON_SWARM_START
        from mageflow.swarm.messages import SwarmResultsMessage
        from mageflow.swarm.workflows import (
            swarm_item_failed,
            swarm_item_done,
            swarm_start_tasks,
        )

        # Chain tasks
        hatchet_chain_done = self._native_client.task(
            name=ON_CHAIN_END,
            input_validator=ChainSuccessTaskCommandMessage,
            retries=3,
            execution_timeout=timedelta(minutes=5),
        )
        hatchet_chain_error = self._native_client.task(
            name=ON_CHAIN_ERROR, retries=3, execution_timeout=timedelta(minutes=5)
        )
        chain_done_task = hatchet_chain_done(chain_end_task)
        on_chain_error_task = hatchet_chain_error(chain_error_task)
        register_chain_done = register_task(ON_CHAIN_END)
        register_chain_error = register_task(ON_CHAIN_ERROR)
        chain_done_task = register_chain_done(chain_done_task)
        on_chain_error_task = register_chain_error(on_chain_error_task)

        # Swarm tasks
        swarm_start = self._native_client.task(
            name=ON_SWARM_START, retries=3, execution_timeout=timedelta(minutes=5)
        )
        swarm_done = self._native_client.task(
            name=ON_SWARM_END,
            input_validator=SwarmResultsMessage,
            retries=3,
            execution_timeout=timedelta(minutes=5),
        )
        swarm_error = self._native_client.task(
            name=ON_SWARM_ERROR, retries=3, execution_timeout=timedelta(minutes=5)
        )
        swarm_start = swarm_start(swarm_start_tasks)
        swarm_done = swarm_done(swarm_item_done)
        swarm_error = swarm_error(swarm_item_failed)
        register_swarm_start = register_task(ON_SWARM_START)
        register_swarm_done = register_task(ON_SWARM_END)
        register_swarm_error = register_task(ON_SWARM_ERROR)
        swarm_start = register_swarm_start(swarm_start)
        swarm_done = register_swarm_done(swarm_done)
        swarm_error = register_swarm_error(swarm_error)

        return [
            on_chain_error_task,
            chain_done_task,
            swarm_start,
            swarm_done,
            swarm_error,
        ]
