from datetime import datetime
from typing import TypedDict, Any, overload, TypeAlias, Optional

import rapyer
from rapyer.fields import RapyerKey

from thirdmagic.task.model import TaskSignature
from thirdmagic.task.status import TaskStatus
from thirdmagic.typing_support import Unpack
from thirdmagic.utils import HatchetTaskType

TaskSignatureConvertible: TypeAlias = RapyerKey | TaskSignature | HatchetTaskType | str


async def resolve_signatures(
    tasks: list[TaskSignatureConvertible],
) -> list[TaskSignature]:
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


async def resolve_signature(task: TaskSignatureConvertible) -> TaskSignature:
    signatures = await resolve_signature([task])
    return signatures[0]


class TaskSignatureOptions(TypedDict, total=False):
    kwargs: dict
    creation_time: datetime
    model_validators: Any
    success_callbacks: list[RapyerKey]
    error_callbacks: list[RapyerKey]
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
