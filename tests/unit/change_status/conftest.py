from dataclasses import dataclass

import pytest_asyncio

import mageflow
from mageflow.chain.model import ChainTaskSignature
from mageflow.signature.model import TaskSignature
from mageflow.signature.status import SignatureStatus
from mageflow.swarm.model import SwarmTaskSignature
from tests.integration.hatchet.models import ContextMessage


@dataclass
class SwarmTestData:
    task_signatures: list
    swarm_signature: SwarmTaskSignature


@dataclass
class ChainTestData:
    task_signatures: list
    chain_signature: ChainTaskSignature


@dataclass
class TaskResumeConfig:
    name: str
    last_status: SignatureStatus


async def delete_tasks_by_indices(
    task_signatures: list[TaskSignature],
    indices: list[int],
) -> list[str]:
    deleted_task_ids = []
    for idx in indices:
        await task_signatures[idx].adelete()
        deleted_task_ids.append(task_signatures[idx].key)
    return deleted_task_ids


def get_non_deleted_task_keys(
    task_signatures: list[TaskSignature],
    deleted_indices: list[int],
) -> list[str]:
    return [
        task_signatures[i].key
        for i in range(len(task_signatures))
        if i not in deleted_indices
    ]


@pytest_asyncio.fixture
async def swarm_with_tasks():
    task_signatures = [
        await mageflow.sign(f"swarm_task_{i}", model_validators=ContextMessage)
        for i in range(1, 4)
    ]

    swarm_signature = await mageflow.swarm(
        task_name="test_swarm",
        model_validators=ContextMessage,
        tasks=task_signatures,
    )

    return SwarmTestData(
        task_signatures=task_signatures, swarm_signature=swarm_signature
    )
