from typing import Any, cast

from hatchet_sdk import WorkflowRunRef
from hatchet_sdk.clients.admin import TriggerWorkflowOptions, WorkflowRunTriggerConfig
from hatchet_sdk.runnables.types import TWorkflowInput, EmptyModel

from hatchet_sdk.runnables.workflow import Workflow
from hatchet_sdk.utils.typing import JSONSerializableMapping
from pydantic import BaseModel

from orchestrator.utils.pythonic import deep_merge, create_dynamic_model

TASK_DATA_PARAM_NAME = "task_data"


class OrchestratorWorkflow(Workflow):
    def __init__(
        self,
        workflow: Workflow,
        workflow_params: dict,
        return_value_field: str = None,
        task_ctx: dict = None,
    ):
        super().__init__(config=workflow.config, client=workflow.client)
        self._orchestrator_workflow_params = workflow_params
        self._return_value_field = return_value_field
        self._task_ctx = task_ctx or {}

    def _serialize_input(self, input: Any) -> JSONSerializableMapping:
        if isinstance(input, BaseModel):
            input = super(OrchestratorWorkflow, self)._serialize_input(input)

        # Force model dump
        kwargs = self._orchestrator_workflow_params
        results_model = create_dynamic_model(kwargs)

        extra_params = super(OrchestratorWorkflow, self)._serialize_input(results_model)
        if self._return_value_field:
            return_field = {self._return_value_field: input}
        else:
            return_field = input

        return deep_merge(return_field, extra_params)

    def _update_options(self, options: TriggerWorkflowOptions):
        if self._task_ctx:
            options.additional_metadata[TASK_DATA_PARAM_NAME] = self._task_ctx
        return options

    def run(
        self,
        input: TWorkflowInput = cast(TWorkflowInput, EmptyModel()),
        options: TriggerWorkflowOptions = None,
    ):
        if options is None:
            options = TriggerWorkflowOptions()
        options = self._update_options(options)
        return super().run(input, options)

    def run_no_wait(
        self,
        input: TWorkflowInput = cast(TWorkflowInput, EmptyModel()),
        options: TriggerWorkflowOptions = None,
    ):
        if options is None:
            options = TriggerWorkflowOptions()
        options = self._update_options(options)
        return super().run_no_wait(input, options)

    def run_many(
        self,
        workflows: list[WorkflowRunTriggerConfig],
        return_exceptions: bool = False,
    ):
        for wf in workflows:
            wf.options = self._update_options(wf.options)
        return super().run_many(workflows, return_exceptions)

    def run_many_no_wait(
        self,
        workflows: list[WorkflowRunTriggerConfig],
    ):
        for wf in workflows:
            wf.options = self._update_options(wf.options)
        return super().run_many_no_wait(workflows)

    async def aio_run_no_wait(
        self,
        input: TWorkflowInput = cast(TWorkflowInput, EmptyModel()),
        options: TriggerWorkflowOptions = None,
    ) -> WorkflowRunRef:
        if options is None:
            options = TriggerWorkflowOptions()
        options = self._update_options(options)
        return await super().aio_run_no_wait(input, options)

    async def aio_run(
        self,
        input: TWorkflowInput = cast(TWorkflowInput, EmptyModel()),
        options: TriggerWorkflowOptions = None,
    ):
        if options is None:
            options = TriggerWorkflowOptions()
        options = self._update_options(options)
        return await super().aio_run(input, options)

    async def aio_run_many_no_wait(
        self,
        workflows: list[WorkflowRunTriggerConfig],
    ):
        for wf in workflows:
            wf.options = self._update_options(wf.options)

        return await super().aio_run_many_no_wait(workflows)

    async def aio_run_many(
        self,
        workflows: list[WorkflowRunTriggerConfig],
        return_exceptions: bool = False,
    ):
        for wf in workflows:
            wf.options = self._update_options(wf.options)

        return await super().aio_run_many(workflows, return_exceptions)
