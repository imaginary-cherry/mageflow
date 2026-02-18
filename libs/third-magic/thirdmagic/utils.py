import dataclasses
from typing import TypeVar, get_type_hints, Optional, Callable, Any

from pydantic import BaseModel

from thirdmagic.message import ReturnValueAnnotation, DEFAULT_RESULT_NAME

PropType = TypeVar("PropType", bound=dataclasses.dataclass)


def get_marked_fields(
    model: type[BaseModel], mark_type: type[PropType]
) -> list[tuple[PropType, str]]:
    hints = get_type_hints(model, include_extras=True)
    marked = []
    for field_name, annotated_type in hints.items():
        if hasattr(annotated_type, "__metadata__"):  # Annotated stores extras here
            for meta in annotated_type.__metadata__:
                if isinstance(meta, mark_type):
                    marked.append((meta, field_name))
    return marked


def return_value_field(model_validators: type[BaseModel]) -> Optional[str]:
    try:
        marked_field = get_marked_fields(model_validators, ReturnValueAnnotation)
        return_field_name = marked_field[0][1]
    except (IndexError, TypeError):
        return_field_name = None
    return return_field_name or DEFAULT_RESULT_NAME


def deep_merge(base: dict, updates: dict) -> dict:
    results = base.copy()
    for key, value in updates.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            results[key] = deep_merge(base[key], value)
        else:
            results[key] = value
    return results


class ModelToDump(BaseModel):
    value: Any


# Which client is installed
try:
    HAS_HATCHET = True
    from hatchet_sdk.runnables.workflow import BaseWorkflow

    HatchetTaskType = BaseWorkflow | Callable
except ImportError:
    HAS_HATCHET = False
    HatchetTaskType = Callable

# try:
#     HAS_TEMPORAL = True
#     HatchetTaskType = None
# except ImportError:
#     HAS_TEMPORAL = False
