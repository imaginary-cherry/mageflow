import dataclasses
from typing import TypeVar, get_type_hints, Optional, Callable, TypeAlias, Any

import rapyer
from pydantic import BaseModel
from rapyer.fields import RapyerKey

from thirdmagic.message import ReturnValueAnnotation, DEFAULT_RESULT_NAME
from thirdmagic.signatures.siganture import TaskSignature

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
    from hatchet_sdk.workflows import BaseWorkflow

    HatchetTaskType = BaseWorkflow | Callable
except ImportError:
    HAS_HATCHET = False

try:
    HAS_TEMPORAL = True
    HatchetTaskType = None
except ImportError:
    HAS_TEMPORAL = False


TaskSignatureConvertible: TypeAlias = RapyerKey | TaskSignature | HatchetTaskType | str


async def resolve_signatures(
    tasks: list[TaskSignatureConvertible],
) -> list["TaskSignature"]:
    result: list[Optional[TaskSignature]] = [None] * len(tasks)
    identifier_entries: list[tuple[int, RapyerKey]] = []
    hatchet_entries: list[tuple[int, HatchetTaskType]] = []
    task_names: list[tuple[int, str]] = []

    for i, task in enumerate(tasks):
        if isinstance(task, TaskSignature):
            result[i] = task
        elif isinstance(task, RapyerKey):
            identifier_entries.append((i, task))
        elif isinstance(task, str):
            task_names.append((i, task))
        else:
            hatchet_entries.append((i, task))

    if identifier_entries:
        keys = [key for _, key in identifier_entries]
        found = await rapyer.afind(*keys, skip_missing=True)
        found_by_key = {sig.key: sig for sig in found}
        for i, key in identifier_entries:
            result[i] = found_by_key.get(key)

    if hatchet_entries:
        async with rapyer.apipeline():
            for i, task in hatchet_entries:
                result[i] = await TaskSignature.from_task(task)

    if task_names:
        async with rapyer.apipeline():
            for i, task_name in task_names:
                result[i] = await TaskSignature.from_task_name(task_name)

    return result
