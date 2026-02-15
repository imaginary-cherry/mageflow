import uuid
from typing import overload, Any

import rapyer

from thirdmagic.signature.creator import TaskSignatureOptions, TaskSignatureConvertible
from thirdmagic.swarm.model import SwarmConfig, SwarmTaskSignature
from thirdmagic.swarm.state import PublishState
from thirdmagic.typing_support import Unpack


class SignatureOptions(TaskSignatureOptions):
    is_swarm_closed: bool
    config: SwarmConfig
    task_kwargs: dict


@overload
async def swarm(
    tasks: list[TaskSignatureConvertible], **options: Unpack[TaskSignatureOptions]
) -> SwarmTaskSignature: ...
@overload
async def swarm(
    tasks: list[TaskSignatureConvertible], **options: Any
) -> SwarmTaskSignature: ...


async def swarm(
    tasks: list[TaskSignatureConvertible] = None,
    task_name: str = None,
    **options: Unpack[SignatureOptions],
) -> SwarmTaskSignature:
    tasks = tasks or []
    task_name = task_name or f"swarm-task-{uuid.uuid4()}"
    publish_state = PublishState()
    model_fields = list(SwarmTaskSignature.model_fields.keys())
    kwargs = {
        field_name: options.pop(field_name)
        for field_name in model_fields
        if field_name in options
    }
    swarm_signature = SwarmTaskSignature(
        **kwargs,
        task_name=task_name,
        publishing_state_id=publish_state.key,
        kwargs=options,
    )
    await rapyer.ainsert(publish_state, swarm_signature)
    await swarm_signature.add_tasks(tasks)
    return swarm_signature
