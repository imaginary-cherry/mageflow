import pytest
from hatchet_sdk.clients.admin import TriggerWorkflowOptions

import thirdmagic
from tests.unit.messages import ContextMessage
from thirdmagic.swarm.model import SwarmConfig, SwarmTaskSignature
from thirdmagic.task.model import TaskSignature

# ── aio_run_tasks_in_swarm ──────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.hatchet
async def test_aio_run_tasks_in_swarm_creates_tasks_in_swarm(
    mock_adapter, mock_close_swarm
):
    swarm = await thirdmagic.swarm(
        task_name="swarm_tasks", config=SwarmConfig(max_concurrency=5)
    )
    t1 = await thirdmagic.sign("task_a", model_validators=ContextMessage)
    t2 = await thirdmagic.sign("task_b", model_validators=ContextMessage)
    msgs = [ContextMessage(base_data={"a": 1}), ContextMessage(base_data={"b": 2})]

    await swarm.aio_run_tasks_in_swarm([t1, t2], msgs)

    reloaded = await SwarmTaskSignature.aget(swarm.key)
    assert len(reloaded.tasks) == 2
    mock_close_swarm.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.hatchet
async def test_aio_run_tasks_in_swarm_each_task_gets_own_message(mock_adapter):
    swarm = await thirdmagic.swarm(
        task_name="swarm_msgs", config=SwarmConfig(max_concurrency=5)
    )
    t1 = await thirdmagic.sign("task_a", model_validators=ContextMessage)
    t2 = await thirdmagic.sign("task_b", model_validators=ContextMessage)
    msg1 = ContextMessage(base_data={"a": 1})
    msg2 = ContextMessage(base_data={"b": 2})

    await swarm.aio_run_tasks_in_swarm([t1, t2], [msg1, msg2])

    reloaded = await SwarmTaskSignature.aget(swarm.key)
    sub1 = await TaskSignature.aget(reloaded.tasks[0])
    sub2 = await TaskSignature.aget(reloaded.tasks[1])
    assert sub1.kwargs["base_data"] == {"a": 1}
    assert sub2.kwargs["base_data"] == {"b": 2}


@pytest.mark.asyncio
@pytest.mark.hatchet
async def test_aio_run_tasks_in_swarm_no_close_when_close_on_max_task_false(
    mock_adapter, mock_close_swarm
):
    swarm = await thirdmagic.swarm(
        task_name="swarm_no_close",
        config=SwarmConfig(max_concurrency=5, max_task_allowed=2),
    )
    t1 = await thirdmagic.sign("task_a", model_validators=ContextMessage)
    t2 = await thirdmagic.sign("task_b", model_validators=ContextMessage)
    msgs = [ContextMessage(base_data={"a": 1}), ContextMessage(base_data={"b": 2})]

    await swarm.aio_run_tasks_in_swarm([t1, t2], msgs, close_on_max_task=False)

    mock_close_swarm.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.hatchet
async def test_aio_run_tasks_in_swarm_afill_swarm_called_with_options(mock_adapter):
    swarm = await thirdmagic.swarm(
        task_name="swarm_opts", config=SwarmConfig(max_concurrency=5)
    )
    t1 = await thirdmagic.sign("task_a", model_validators=ContextMessage)
    msgs = [ContextMessage(base_data={"a": 1})]
    options = TriggerWorkflowOptions(additional_metadata={"key": "val"})

    await swarm.aio_run_tasks_in_swarm([t1], msgs, options=options)

    mock_adapter.afill_swarm.assert_awaited_once_with(swarm, options=options)


@pytest.mark.asyncio
@pytest.mark.hatchet
async def test_aio_run_tasks_in_swarm_afill_swarm_called_without_options(mock_adapter):
    swarm = await thirdmagic.swarm(
        task_name="swarm_no_opts", config=SwarmConfig(max_concurrency=5)
    )
    t1 = await thirdmagic.sign("task_a", model_validators=ContextMessage)
    msgs = [ContextMessage(base_data={"a": 1})]

    await swarm.aio_run_tasks_in_swarm([t1], msgs)

    mock_adapter.afill_swarm.assert_awaited_once_with(swarm, options=None)


# ── aio_run_in_swarm ────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.hatchet
async def test_aio_run_in_swarm_single_task_added(mock_adapter):
    swarm = await thirdmagic.swarm(
        task_name="swarm_single", config=SwarmConfig(max_concurrency=5)
    )
    task = await thirdmagic.sign("task_a", model_validators=ContextMessage)
    msg = ContextMessage(base_data={"x": 1})

    await swarm.aio_run_in_swarm(task, msg)

    reloaded = await SwarmTaskSignature.aget(swarm.key)
    assert len(reloaded.tasks) == 1


@pytest.mark.asyncio
@pytest.mark.hatchet
async def test_aio_run_in_swarm_list_tasks_all_get_same_kwargs(mock_adapter):
    swarm = await thirdmagic.swarm(
        task_name="swarm_same_msg", config=SwarmConfig(max_concurrency=5)
    )
    t1 = await thirdmagic.sign("task_a", model_validators=ContextMessage)
    t2 = await thirdmagic.sign("task_b", model_validators=ContextMessage)
    msg = ContextMessage(base_data={"shared": "data"})

    await swarm.aio_run_in_swarm([t1, t2], msg)

    reloaded = await SwarmTaskSignature.aget(swarm.key)
    sub1 = await TaskSignature.aget(reloaded.tasks[0])
    sub2 = await TaskSignature.aget(reloaded.tasks[1])
    assert sub1.kwargs["base_data"] == {"shared": "data"}
    assert sub2.kwargs["base_data"] == {"shared": "data"}


@pytest.mark.asyncio
@pytest.mark.hatchet
async def test_aio_run_in_swarm_afill_swarm_max_tasks_for_list(mock_adapter):
    swarm = await thirdmagic.swarm(
        task_name="swarm_max_list", config=SwarmConfig(max_concurrency=5)
    )
    t1 = await thirdmagic.sign("task_a", model_validators=ContextMessage)
    t2 = await thirdmagic.sign("task_b", model_validators=ContextMessage)
    msg = ContextMessage(base_data={"x": 1})
    options = TriggerWorkflowOptions(additional_metadata={"k": "v"})

    await swarm.aio_run_in_swarm([t1, t2], msg, options=options)

    mock_adapter.afill_swarm.assert_awaited_once_with(
        swarm, max_tasks=2, options=options
    )


@pytest.mark.asyncio
@pytest.mark.hatchet
async def test_aio_run_in_swarm_afill_swarm_max_tasks_for_single(mock_adapter):
    swarm = await thirdmagic.swarm(
        task_name="swarm_max_single", config=SwarmConfig(max_concurrency=5)
    )
    task = await thirdmagic.sign("task_a", model_validators=ContextMessage)
    msg = ContextMessage(base_data={"x": 1})

    await swarm.aio_run_in_swarm(task, msg)

    mock_adapter.afill_swarm.assert_awaited_once_with(swarm, max_tasks=1, options=None)


@pytest.mark.asyncio
@pytest.mark.hatchet
async def test_aio_run_in_swarm_closes_at_max_task_allowed(
    mock_adapter, mock_close_swarm
):
    swarm = await thirdmagic.swarm(
        task_name="swarm_close2",
        config=SwarmConfig(max_concurrency=5, max_task_allowed=2),
    )
    t1 = await thirdmagic.sign("task_a", model_validators=ContextMessage)
    t2 = await thirdmagic.sign("task_b", model_validators=ContextMessage)
    msg = ContextMessage(base_data={"x": 1})

    await swarm.aio_run_in_swarm([t1, t2], msg)

    mock_close_swarm.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.hatchet
async def test_aio_run_in_swarm_no_close_when_close_on_max_task_false(
    mock_adapter, mock_close_swarm
):
    swarm = await thirdmagic.swarm(
        task_name="swarm_no_close2",
        config=SwarmConfig(max_concurrency=5, max_task_allowed=2),
    )
    t1 = await thirdmagic.sign("task_a", model_validators=ContextMessage)
    t2 = await thirdmagic.sign("task_b", model_validators=ContextMessage)
    msg = ContextMessage(base_data={"x": 1})

    await swarm.aio_run_in_swarm([t1, t2], msg, close_on_max_task=False)

    mock_close_swarm.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.hatchet
async def test_aio_run_in_swarm_tasks_in_redis_before_afill_swarm_called__when_swarm_is_closing(
    mock_adapter,
):
    """Tasks must be persisted to Redis BEFORE afill_swarm is invoked."""
    swarm = await thirdmagic.swarm(
        task_name="swarm_ordering",
        config=SwarmConfig(max_concurrency=5, max_task_allowed=2),
    )
    t1 = await thirdmagic.sign("task_a", model_validators=ContextMessage)
    t2 = await thirdmagic.sign("task_b", model_validators=ContextMessage)
    msg = ContextMessage(base_data={"order": "check"})

    # Capture swarm state from Redis on the FIRST afill_swarm call only
    snapshots = []

    async def capture_redis_state_on_call(swarm_arg, **kwargs):
        if not snapshots:
            reloaded = await SwarmTaskSignature.aget(swarm_arg.key)
            snapshots.append(
                {
                    "tasks": list(reloaded.tasks),
                    "tasks_left_to_run": list(reloaded.tasks_left_to_run),
                }
            )

    mock_adapter.afill_swarm.side_effect = capture_redis_state_on_call

    await swarm.aio_run_in_swarm([t1, t2], msg)

    # At the moment afill_swarm was first called, both tasks were already in Redis
    first_call_state = snapshots[0]
    assert len(first_call_state["tasks"]) == 2
    assert len(first_call_state["tasks_left_to_run"]) == 2
    assert set(first_call_state["tasks"]) == set(first_call_state["tasks_left_to_run"])
