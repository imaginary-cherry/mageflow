from dataclasses import dataclass

import pytest_asyncio

import mageflow
from mageflow.swarm.model import SwarmTaskSignature
from tests.integration.hatchet.models import ContextMessage


@dataclass
class SwarmTestData:
    task_signatures: list
    swarm_signature: SwarmTaskSignature


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
