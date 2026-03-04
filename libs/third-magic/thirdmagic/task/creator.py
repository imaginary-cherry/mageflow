from datetime import datetime
from typing import TypedDict, Any, overload, TypeAlias, Optional

import rapyer
from rapyer.fields import RapyerKey

from thirdmagic.signature import Signature
from thirdmagic.signature.retry_cache import (
    retry_cache_ctx,
    get_cached_signature,
    cache_signature,
)
from thirdmagic.signature.status import TaskStatus
from thirdmagic.task.model import TaskSignature
from thirdmagic.typing_support import Unpack
from thirdmagic.utils import HatchetTaskType

TaskSignatureConvertible: TypeAlias = RapyerKey | Signature | HatchetTaskType | str


async def resolve_signatures(
    tasks: list[TaskSignatureConvertible],
) -> list[Signature]:
    result: list[Optional[Signature]] = [None] * len(tasks)
    identifier_entries: list[tuple[int, RapyerKey]] = []
    hatchet_entries: list[tuple[int, HatchetTaskType]] = []
    task_names: list[tuple[int, str]] = []

    for i, task in enumerate(tasks):
        if isinstance(task, Signature):
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


async def resolve_signature(task: TaskSignatureConvertible) -> Signature:
    signatures = await resolve_signatures([task])
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
    cache_state = retry_cache_ctx.get()
    if cache_state and cache_state.is_retry and cache_state.cache:
        cached = await get_cached_signature(cache_state, TaskSignature)
        if cached is not None:
            return cached

    model_fields = list(TaskSignature.model_fields.keys())
    kwargs = {
        field_name: options.pop(field_name)
        for field_name in model_fields
        if field_name in options
    }

    if isinstance(task, str):
        signature = await TaskSignature.from_task_name(task, kwargs=options, **kwargs)
    else:
        signature = await TaskSignature.from_task(task, kwargs=options, **kwargs)

    if cache_state and not cache_state.is_retry:
        await cache_signature(cache_state, signature)

    return signature
