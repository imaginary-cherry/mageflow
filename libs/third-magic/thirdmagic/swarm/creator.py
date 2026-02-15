import uuid

import rapyer

from thirdmagic.signature.creator import TaskSignatureOptions, TaskSignatureConvertible
from thirdmagic.swarm.model import SwarmConfig, SwarmTaskSignature
from thirdmagic.swarm.state import PublishState
from thirdmagic.typing_support import Unpack


class SignatureOptions(TaskSignatureOptions):
    is_swarm_closed: bool
    config: SwarmConfig
    task_kwargs: dict


async def swarm(
    tasks: list[TaskSignatureConvertible] = None,
    task_name: str = None,
    **kwargs: Unpack[SignatureOptions],
) -> SwarmTaskSignature:
    tasks = tasks or []
    task_name = task_name or f"swarm-task-{uuid.uuid4()}"
    publish_state = PublishState()
    swarm_signature = SwarmTaskSignature(
        **kwargs, task_name=task_name, publishing_state_id=publish_state.key
    )
    await rapyer.ainsert(publish_state, swarm_signature)
    await swarm_signature.add_tasks(tasks)
    return swarm_signature
