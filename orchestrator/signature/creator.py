from typing import TypeAlias

from orchestrator.signature.model import (
    TaskSignature,
    TaskIdentifierType,
    HatchetTaskType,
)

TaskSignatureConvertible: TypeAlias = (
    TaskIdentifierType | TaskSignature | HatchetTaskType
)


async def resolve_signature_id(task: TaskSignatureConvertible) -> TaskSignature:
    if isinstance(task, TaskSignature):
        return task
    elif isinstance(task, TaskIdentifierType):
        return await TaskSignature.from_id_safe(task)
    else:
        return await TaskSignature.from_task(task)
