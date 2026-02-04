"""
Hatchet-specific workflow adapter.

This module provides the WorkflowAdapter implementation for Hatchet workflows.
It wraps Hatchet's Workflow class and handles Mageflow-specific context injection.
"""
from typing import Any, cast

from hatchet_sdk import WorkflowRunRef
from hatchet_sdk.clients.admin import TriggerWorkflowOptions, WorkflowRunTriggerConfig
from hatchet_sdk.runnables.types import TWorkflowInput, EmptyModel
from hatchet_sdk.runnables.workflow import Workflow
from hatchet_sdk.utils.typing import JSONSerializableMapping
from pydantic import BaseModel

from mageflow.adapters.protocols import WorkflowAdapter
from mageflow.utils.pythonic import deep_merge
from mageflow.workflows import TASK_DATA_PARAM_NAME


class ModelToDump(BaseModel):
    """Helper model for serializing workflow params."""

    value: Any


class HatchetWorkflowAdapter:
    """
    WorkflowAdapter implementation for Hatchet.

    This wraps a Hatchet Workflow and handles:
    - Mageflow task context injection (signature key, etc.)
    - Workflow parameter merging
    - Return value field mapping
    """

    def __init__(
        self,
        workflow: Workflow,
        task_ctx: dict | None = None,
        workflow_params: dict | None = None,
        return_value_field: str | None = None,
    ):
        self._workflow = workflow
        self._task_ctx = task_ctx or {}
        self._workflow_params = workflow_params or {}
        self._return_value_field = return_value_field

    @property
    def native_workflow(self) -> Workflow:
        """Get the underlying Hatchet Workflow."""
        return self._workflow

    def _serialize_input(self, input: Any) -> JSONSerializableMapping:
        """Serialize input and merge with workflow params."""
        if isinstance(input, BaseModel):
            input = self._workflow._serialize_input(input)

        # Force model dump for workflow params
        kwargs = self._workflow_params
        results_model = ModelToDump(value=kwargs)
        extra_params = self._workflow._serialize_input(results_model)
        dumped_kwargs = extra_params["value"]

        if self._return_value_field:
            return_field = {self._return_value_field: input}
        else:
            return_field = input

        return deep_merge(return_field, dumped_kwargs)

    def _update_options(self, options: TriggerWorkflowOptions) -> TriggerWorkflowOptions:
        """Inject Mageflow task context into options."""
        if self._task_ctx:
            options.additional_metadata[TASK_DATA_PARAM_NAME] = self._task_ctx
        return options

    def _prepare_options(self, options: dict | None) -> TriggerWorkflowOptions:
        """Convert dict options to TriggerWorkflowOptions."""
        if options is None:
            hatchet_options = TriggerWorkflowOptions()
        elif isinstance(options, TriggerWorkflowOptions):
            hatchet_options = options
        else:
            hatchet_options = TriggerWorkflowOptions(**options)
        return self._update_options(hatchet_options)

    def run(
        self,
        input: Any = None,
        options: dict | None = None,
    ) -> Any:
        """Run the workflow and wait for result."""
        if input is None:
            input = cast(TWorkflowInput, EmptyModel())
        hatchet_options = self._prepare_options(options)
        return self._workflow.run(input, hatchet_options)

    def run_no_wait(
        self,
        input: Any = None,
        options: dict | None = None,
    ) -> Any:
        """Trigger the workflow without waiting for result."""
        if input is None:
            input = cast(TWorkflowInput, EmptyModel())
        hatchet_options = self._prepare_options(options)
        return self._workflow.run_no_wait(input, hatchet_options)

    async def aio_run(
        self,
        input: Any = None,
        options: dict | None = None,
    ) -> Any:
        """Run the workflow asynchronously and wait for result."""
        if input is None:
            input = cast(TWorkflowInput, EmptyModel())
        hatchet_options = self._prepare_options(options)
        return await self._workflow.aio_run(input, hatchet_options)

    async def aio_run_no_wait(
        self,
        input: Any = None,
        options: dict | None = None,
    ) -> WorkflowRunRef:
        """Trigger the workflow asynchronously without waiting for result."""
        if input is None:
            input = cast(TWorkflowInput, EmptyModel())
        hatchet_options = self._prepare_options(options)
        return await self._workflow.aio_run_no_wait(input, hatchet_options)

    def run_many(
        self,
        workflows: list[WorkflowRunTriggerConfig],
        return_exceptions: bool = False,
    ) -> Any:
        """Run multiple workflow instances."""
        for wf in workflows:
            wf.options = self._update_options(wf.options)
        return self._workflow.run_many(workflows, return_exceptions)

    def run_many_no_wait(
        self,
        workflows: list[WorkflowRunTriggerConfig],
    ) -> Any:
        """Trigger multiple workflow instances without waiting."""
        for wf in workflows:
            wf.options = self._update_options(wf.options)
        return self._workflow.run_many_no_wait(workflows)

    async def aio_run_many(
        self,
        workflows: list[WorkflowRunTriggerConfig],
        return_exceptions: bool = False,
    ) -> Any:
        """Run multiple workflow instances asynchronously."""
        for wf in workflows:
            wf.options = self._update_options(wf.options)
        return await self._workflow.aio_run_many(workflows, return_exceptions)

    async def aio_run_many_no_wait(
        self,
        workflows: list[WorkflowRunTriggerConfig],
    ) -> Any:
        """Trigger multiple workflow instances asynchronously without waiting."""
        for wf in workflows:
            wf.options = self._update_options(wf.options)
        return await self._workflow.aio_run_many_no_wait(workflows)
