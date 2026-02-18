from dataclasses import dataclass

import pytest
import pytest_asyncio

import thirdmagic
from tests.unit.messages import ContextMessage
from tests.unit.utils import extract_hatchet_validator
from thirdmagic.chain import ChainTaskSignature
from thirdmagic.task import TaskSignature, SignatureStatus
from thirdmagic.swarm import SwarmTaskSignature


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
async def chain_with_tasks():
    task_signatures = [
        await thirdmagic.sign(f"chain_task_{i}", model_validators=ContextMessage)
        for i in range(1, 4)
    ]

    chain_signature = await thirdmagic.chain([task.key for task in task_signatures])

    return ChainTestData(
        task_signatures=task_signatures, chain_signature=chain_signature
    )


@pytest_asyncio.fixture
async def swarm_with_tasks():
    task_signatures = [
        await thirdmagic.sign(f"swarm_task_{i}", model_validators=ContextMessage)
        for i in range(1, 4)
    ]

    swarm_signature = await thirdmagic.swarm(
        task_name="test_swarm",
        model_validators=ContextMessage,
        tasks=task_signatures,
    )

    return SwarmTestData(
        task_signatures=task_signatures, swarm_signature=swarm_signature
    )


@pytest.fixture()
def hatchet_client_adapter(mock_adapter):
    mock_adapter.extract_validator.side_effect = extract_hatchet_validator
    mock_adapter.task_name.side_effect = lambda fn: fn.name
    yield mock_adapter
