from datetime import timedelta

from hatchet_sdk.runnables.types import ConcurrencyLimitStrategy

from mageflow.clients.hatchet.mageflow import HatchetMageflow
from mageflow.clients.inner_task_names import (
    ON_CHAIN_END,
    ON_CHAIN_ERROR,
    ON_SWARM_ITEM_DONE,
    ON_SWARM_ITEM_ERROR,
    SWARM_FILL_TASK,
)
from mageflow.swarm.consts import SWARM_ITEM_ID_PARAM_NAME, SWARM_TASK_ID_PARAM_NAME


def test_internal_swarm_callback_tasks_are_serialized_per_swarm_item(
    hatchet_mock, redis_client, monkeypatch
):
    expected_task_count = 5
    expected_registered_task_names = {
        ON_CHAIN_END,
        ON_CHAIN_ERROR,
        ON_SWARM_ITEM_DONE,
        ON_SWARM_ITEM_ERROR,
        SWARM_FILL_TASK,
    }
    expected_expression = (
        f"input.{SWARM_TASK_ID_PARAM_NAME} + ':' + input.{SWARM_ITEM_ID_PARAM_NAME}"
    )
    expected_callback_task_names = (ON_SWARM_ITEM_DONE, ON_SWARM_ITEM_ERROR)
    expected_concurrency_count = 1
    expected_max_runs = 1
    expected_limit_strategy = ConcurrencyLimitStrategy.GROUP_ROUND_ROBIN
    expected_done_timeout = timedelta(minutes=1)
    expected_error_timeout = timedelta(minutes=5)

    # Arrange
    registered_tasks = {}

    def fake_durable_task(**kwargs):
        registered_tasks[kwargs["name"]] = kwargs

        def decorator(func):
            return func

        return decorator

    monkeypatch.setattr(hatchet_mock, "durable_task", fake_durable_task)
    client = HatchetMageflow(hatchet=hatchet_mock, redis_client=redis_client)

    # Act
    tasks = client.init_mageflow_hatchet_tasks()

    # Assert
    assert len(tasks) == expected_task_count
    assert set(registered_tasks) == expected_registered_task_names

    for task_name in expected_callback_task_names:
        concurrency = registered_tasks[task_name]["concurrency"]

        assert len(concurrency) == expected_concurrency_count
        assert concurrency[0].expression == expected_expression
        assert concurrency[0].max_runs == expected_max_runs
        assert concurrency[0].limit_strategy == expected_limit_strategy

    assert (
        registered_tasks[ON_SWARM_ITEM_DONE]["execution_timeout"]
        == expected_done_timeout
    )
    assert (
        registered_tasks[ON_SWARM_ITEM_ERROR]["execution_timeout"]
        == expected_error_timeout
    )


def test_internal_swarm_fill_task_keeps_existing_concurrency_gate(
    hatchet_mock, redis_client, monkeypatch
):
    expected_concurrency_count = 2
    expected_expression = f"input.{SWARM_TASK_ID_PARAM_NAME}"
    expected_cancel_newest_max_runs = 2
    expected_cancel_newest_strategy = ConcurrencyLimitStrategy.CANCEL_NEWEST
    expected_round_robin_max_runs = 1
    expected_round_robin_strategy = ConcurrencyLimitStrategy.GROUP_ROUND_ROBIN

    # Arrange
    registered_tasks = {}

    def fake_durable_task(**kwargs):
        registered_tasks[kwargs["name"]] = kwargs

        def decorator(func):
            return func

        return decorator

    monkeypatch.setattr(hatchet_mock, "durable_task", fake_durable_task)
    client = HatchetMageflow(hatchet=hatchet_mock, redis_client=redis_client)

    # Act
    client.init_mageflow_hatchet_tasks()

    # Assert
    concurrency = registered_tasks[SWARM_FILL_TASK]["concurrency"]

    assert len(concurrency) == expected_concurrency_count
    assert concurrency[0].expression == expected_expression
    assert concurrency[0].max_runs == expected_cancel_newest_max_runs
    assert concurrency[0].limit_strategy == expected_cancel_newest_strategy
    assert concurrency[1].expression == expected_expression
    assert concurrency[1].max_runs == expected_round_robin_max_runs
    assert concurrency[1].limit_strategy == expected_round_robin_strategy
