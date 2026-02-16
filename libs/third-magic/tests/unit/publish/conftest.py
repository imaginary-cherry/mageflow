from dataclasses import dataclass, field
from typing import Any

import pytest_asyncio

import thirdmagic
from tests.unit.messages import ContextMessage
from thirdmagic.swarm.model import SwarmConfig


@pytest_asyncio.fixture
async def chain_with_two_tasks():
    first_task_kwargs = {"first_param": "first_value"}
    first_task = await thirdmagic.sign(
        "first_task", model_validators=ContextMessage, **first_task_kwargs
    )
    second_task = await thirdmagic.sign("second_task", model_validators=ContextMessage)
    chain = await thirdmagic.chain([first_task, second_task])
    return chain, first_task, first_task_kwargs


@dataclass
class RunTaskCall:
    task_name: str
    msg: Any
    kwargs: dict = field(default_factory=dict)


@pytest_asyncio.fixture
async def swarm_with_kwargs():
    swarm_kwargs = {"existing": "value"}
    swarm = await thirdmagic.swarm(
        task_name="test_swarm",
        model_validators=ContextMessage,
        **swarm_kwargs,
        config=SwarmConfig(max_concurrency=5),
    )
    return swarm, swarm_kwargs
