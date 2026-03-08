from typing import Any

from hatchet_sdk.runnables.workflow import Workflow
from hatchet_sdk.utils.typing import JSONSerializableMapping
from pydantic import BaseModel

from thirdmagic.utils import deep_merge


class MageflowWorkflow(Workflow):
    def __init__(
        self,
        workflow: Workflow,
        workflow_params: dict,
        return_value_field: str = None,
    ):
        super().__init__(config=workflow.config, client=workflow.client)
        self._mageflow_workflow_params = workflow_params
        self._return_value_field = return_value_field

    def _serialize_input(self, input: Any) -> JSONSerializableMapping:
        if isinstance(input, BaseModel):
            input = input.model_dump(mode="json")

        # Force model dump
        kwargs = self._mageflow_workflow_params

        if self._return_value_field:
            return_field = {self._return_value_field: input}
        else:
            return_field = input

        full_msg = deep_merge(return_field, kwargs)
        return super(MageflowWorkflow, self)._serialize_input(full_msg)
