from pydantic import TypeAdapter


def extract_hatchet_validator(workflow):
    validator = workflow.input_validator
    if isinstance(validator, TypeAdapter):
        validator = validator._type
    return validator
