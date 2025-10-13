from typing import Any

from hatchet_sdk.runnables.workflow import Workflow
from hatchet_sdk.utils.typing import JSONSerializableMapping
from pydantic import BaseModel

from orchestrator.utils.models import create_dynamic_model


class OrchestratorWorkflow(Workflow):
    def __init__(
        self,
        workflow: Workflow,
        workflow_params: dict,
        return_value_field: str = None,
    ):
        super().__init__(config=workflow.config, client=workflow.client)
        self._workflow_params = workflow_params
        self._return_value_field = return_value_field

    def _serialize_input(self, input: Any) -> JSONSerializableMapping:
        if isinstance(input, BaseModel):
            input = super(OrchestratorWorkflow, self)._serialize_input(input)

        # Force model dump
        kwargs = self._workflow_params
        results_model = create_dynamic_model(kwargs)

        extra_params = super(OrchestratorWorkflow, self)._serialize_input(results_model)
        if self._return_value_field:
            return_field = {self._return_value_field: input}
        else:
            return_field = input

        return deep_merge(return_field, extra_params)
