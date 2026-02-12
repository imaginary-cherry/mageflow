from hatchet_sdk.runnables.workflow import BaseWorkflow
from pydantic import TypeAdapter


def extract_hatchet_validator(workflow: BaseWorkflow):
    validator = workflow.input_validator
    if isinstance(validator, TypeAdapter):
        validator = validator._type
    return validator
