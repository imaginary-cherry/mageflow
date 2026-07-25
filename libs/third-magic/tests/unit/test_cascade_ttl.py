import pytest
from rapyer.actions import ActionGroup
from rapyer.cascade import CascadeTTL
from rapyer.cascade.planner import build_cascade_plan

import thirdmagic
from thirdmagic.chain.model import ChainTaskSignature
from thirdmagic.swarm.model import SwarmTaskSignature
from thirdmagic.task.model import TaskSignature

WRITE_ACTIONS = (
    ActionGroup.CREATE
    | ActionGroup.UPDATE
    | ActionGroup.APPEND
    | ActionGroup.ERASE
    | ActionGroup.ARITHMETIC
)


@pytest.mark.parametrize("container_cls", [SwarmTaskSignature, ChainTaskSignature])
def test_container_refreshes_and_cascades_on_write(container_cls):
    # Assert: writes refresh TTL, and the tasks edge carries a cascade marker
    assert container_cls.Meta.refresh_ttl == WRITE_ACTIONS
    assert "tasks" in container_cls._contain_fk
    metadata = container_cls.model_fields["tasks"].metadata
    assert any(isinstance(marker, CascadeTTL) for marker in metadata)


def test_cascade_plan_has_container_to_task_edges():
    # Act
    plan = build_cascade_plan([SwarmTaskSignature, ChainTaskSignature, TaskSignature])

    # Assert
    for name in ("SwarmTaskSignature", "ChainTaskSignature"):
        edges = plan[name].fks
        targets = {edge.target for edge in edges}
        assert "TaskSignature" in targets
        assert any(edge.path == "$.tasks" for edge in edges)


@pytest.mark.asyncio
async def test_chain_tasks_persist_as_references(mock_task_def):
    # Arrange
    tasks = [await thirdmagic.sign(f"chain_task_{i}") for i in range(3)]
    chain = await thirdmagic.chain([task.key for task in tasks])

    # Act
    reloaded = await ChainTaskSignature.aget(chain.key)

    # Assert
    assert reloaded.task_ids == [task.key for task in tasks]


@pytest.mark.asyncio
async def test_swarm_tasks_persist_as_references_on_add(mock_task_def):
    # Arrange
    swarm = await thirdmagic.swarm(task_name="test_swarm")
    tasks = [await thirdmagic.sign(f"test_task_{i}") for i in range(3)]

    # Act
    await swarm.add_tasks(tasks)
    reloaded = await SwarmTaskSignature.aget(swarm.key)

    # Assert
    assert reloaded.task_ids == [task.key for task in tasks]
