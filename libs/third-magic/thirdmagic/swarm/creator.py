import uuid
from typing import Any, overload

import rapyer

from thirdmagic.signature.retry_cache import (
    cache_signature,
    get_cached_signature,
    retry_cache_ctx,
)
from thirdmagic.swarm.model import SwarmConfig, SwarmTaskSignature
from thirdmagic.swarm.state import PublishState
from thirdmagic.task.creator import TaskSignatureConvertible, TaskSignatureOptions
from thirdmagic.typing_support import Unpack


class SignatureOptions(TaskSignatureOptions):
    is_swarm_closed: bool
    config: SwarmConfig
    task_kwargs: dict


@overload
async def swarm(
    tasks: list[TaskSignatureConvertible],
    task_name: str = None,
    **options: Unpack[TaskSignatureOptions],
) -> SwarmTaskSignature: ...
@overload
async def swarm(
    tasks: list[TaskSignatureConvertible], task_name: str = None, **options: Any
) -> SwarmTaskSignature: ...


async def swarm(
    tasks: list[TaskSignatureConvertible] = None,
    task_name: str = None,
    **options: Unpack[SignatureOptions],
) -> SwarmTaskSignature:
    cache_state = retry_cache_ctx.get()
    if cache_state and cache_state.is_retry and cache_state.cache:
        cached = await get_cached_signature(cache_state, SwarmTaskSignature)
        if cached is not None:
            return cached

    tasks = tasks or []
    task_name = task_name or f"swarm-task-{uuid.uuid4()}"
    publish_state = PublishState()
    model_fields = list(SwarmTaskSignature.model_fields.keys())
    direct_kwargs_param = options.pop("kwargs", {})
    kwargs = {
        field_name: options.pop(field_name)
        for field_name in model_fields
        if field_name in options
    }
    swarm_signature = SwarmTaskSignature(
        **kwargs,
        task_name=task_name,
        publishing_state_id=publish_state.key,
        kwargs=direct_kwargs_param | options,
    )
    await rapyer.ainsert(publish_state, swarm_signature)
    await swarm_signature.add_tasks(tasks)

    if cache_state and not cache_state.is_retry:
        await cache_signature(cache_state, swarm_signature)

    return swarm_signature
