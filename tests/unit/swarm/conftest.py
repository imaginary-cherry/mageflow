from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from hatchet_sdk import Context
from rapyer.types import RedisInt

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


@pytest.fixture
def mock_context():
    ctx = MagicMock(spec=Context)
    ctx.log = MagicMock()
    ctx.additional_metadata = {}
    return ctx


@pytest.fixture
def mock_redis_int_increase_error():
    with patch.object(
        RedisInt, "increase", side_effect=RuntimeError("Redis error")
    ) as mock_increase:
        yield mock_increase
