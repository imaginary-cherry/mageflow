from datetime import datetime
from typing import TypeAlias, TypedDict, Any, Optional, overload

import rapyer

from mageflow.signature.model import (
    TaskSignature,
    TaskIdentifierType,
    HatchetTaskType,
)
from mageflow.signature.status import TaskStatus
from mageflow.typing_support import Unpack

TaskSignatureConvertible: TypeAlias = (
    TaskIdentifierType | TaskSignature | HatchetTaskType
)


async def resolve_signature_key(task: TaskSignatureConvertible) -> TaskSignature:
    signatures = await resolve_signature_keys([task])
    return signatures[0]


async def resolve_signature_keys(
    tasks: list[TaskSignatureConvertible],
) -> list[Optional[TaskSignature]]:
    result: list[Optional[TaskSignature]] = [None] * len(tasks)
    identifier_entries: list[tuple[int, str]] = []
    hatchet_entries: list[tuple[int, HatchetTaskType]] = []

    for i, task in enumerate(tasks):
        if isinstance(task, TaskSignature):
            result[i] = task
        elif isinstance(task, TaskIdentifierType):
            identifier_entries.append((i, task))
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

    return result


class TaskSignatureOptions(TypedDict, total=False):
    kwargs: dict
    creation_time: datetime
    model_validators: Any
    success_callbacks: list[TaskIdentifierType]
    error_callbacks: list[TaskIdentifierType]
    task_status: TaskStatus


@overload
async def sign(
    task: str | HatchetTaskType, **options: Unpack[TaskSignatureOptions]
) -> TaskSignature: ...
@overload
async def sign(task: str | HatchetTaskType, **options: Any) -> TaskSignature: ...


async def sign(task: str | HatchetTaskType, **options: Any) -> TaskSignature:
    model_fields = list(TaskSignature.model_fields.keys())
    kwargs = {
        field_name: options.pop(field_name)
        for field_name in model_fields
        if field_name in options
    }

    if isinstance(task, str):
        return await TaskSignature.from_task_name(task, kwargs=options, **kwargs)
    else:
        return await TaskSignature.from_task(task, kwargs=options, **kwargs)


load_signature = TaskSignature.get_safe
resume_task = TaskSignature.resume_from_key
lock_task = TaskSignature.alock_from_key
resume = TaskSignature.resume_from_key
pause = TaskSignature.pause_from_key
remove = TaskSignature.remove_from_key
