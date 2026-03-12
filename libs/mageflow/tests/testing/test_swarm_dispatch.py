"""Tests for swarm dispatch assertion API in TestClientAdapter."""

import pytest

from mageflow.testing._adapter import (
    ChainDispatchRecord,
    SwarmDispatchRecord,
    TaskDispatchRecord,
    TestClientAdapter,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_adapter() -> TestClientAdapter:
    return TestClientAdapter()


def _append_swarm(
    adapter: TestClientAdapter,
    swarm_name: str,
    task_names: list[str],
    **kwargs,
) -> None:
    adapter._typed_dispatches.append(
        SwarmDispatchRecord(swarm_name=swarm_name, task_names=task_names, kwargs=kwargs)
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAssertSwarmDispatchedByName:
    def test_found(self):
        adapter = _make_adapter()
        _append_swarm(adapter, "my-swarm", ["task-a", "task-b"])
        record = adapter.assert_swarm_dispatched("my-swarm")
        assert isinstance(record, SwarmDispatchRecord)
        assert record.swarm_name == "my-swarm"

    def test_not_found_raises(self):
        adapter = _make_adapter()
        _append_swarm(adapter, "other-swarm", [])
        with pytest.raises(AssertionError, match="was not dispatched"):
            adapter.assert_swarm_dispatched("my-swarm")

    def test_error_lists_dispatched_swarms(self):
        adapter = _make_adapter()
        _append_swarm(adapter, "swarm-a", [])
        with pytest.raises(AssertionError, match="swarm-a"):
            adapter.assert_swarm_dispatched("swarm-missing")


class TestAssertSwarmDispatchedWithTaskNames:
    def test_expected_task_names_subset_check_passes(self):
        adapter = _make_adapter()
        _append_swarm(adapter, "my-swarm", ["task-a", "task-b", "task-c"])
        record = adapter.assert_swarm_dispatched(
            "my-swarm", expected_task_names=["task-a", "task-b"]
        )
        assert record is not None

    def test_all_expected_task_names_present_passes(self):
        adapter = _make_adapter()
        _append_swarm(adapter, "my-swarm", ["task-a", "task-b"])
        record = adapter.assert_swarm_dispatched(
            "my-swarm", expected_task_names=["task-a", "task-b"]
        )
        assert record is not None

    def test_missing_expected_task_name_fails(self):
        adapter = _make_adapter()
        _append_swarm(adapter, "my-swarm", ["task-a"])
        with pytest.raises(AssertionError, match="task names did not match"):
            adapter.assert_swarm_dispatched(
                "my-swarm", expected_task_names=["task-a", "task-b"]
            )

    def test_error_message_includes_expected_and_actual(self):
        adapter = _make_adapter()
        _append_swarm(adapter, "my-swarm", ["task-x"])
        with pytest.raises(AssertionError) as exc_info:
            adapter.assert_swarm_dispatched(
                "my-swarm", expected_task_names=["task-missing"]
            )
        msg = str(exc_info.value)
        assert "task-missing" in msg
        assert "task-x" in msg


class TestSwarmDispatchesProperty:
    def test_filters_to_swarm_records_only(self):
        adapter = _make_adapter()
        adapter._typed_dispatches.append(
            TaskDispatchRecord(task_name="my-task", input_data={}, kwargs={})
        )
        _append_swarm(adapter, "my-swarm", ["task-a"])
        adapter._typed_dispatches.append(
            ChainDispatchRecord(chain_name="my-chain", results={}, task_names=[])
        )
        swarm_dispatches = adapter.swarm_dispatches
        assert len(swarm_dispatches) == 1
        assert swarm_dispatches[0].swarm_name == "my-swarm"


@pytest.mark.asyncio(loop_scope="session")
async def test_afill_swarm_resolves_task_names_from_signature(test_adapter):
    """Integration test: afill_swarm correctly resolves sub-task task_names from Redis.

    This proves the try/except in afill_swarm does NOT fall back to [] on the happy path.
    The test_adapter fixture depends on _mageflow_init_rapyer which provides a live Redis.
    """
    from pydantic import BaseModel

    import mageflow

    # Use model_validators to bypass MageflowTaskDefinition lookup in Redis
    task_sig_a = await mageflow.asign("swarm-sub-task-a", model_validators=BaseModel)
    task_sig_b = await mageflow.asign("swarm-sub-task-b", model_validators=BaseModel)

    swarm_sig = await mageflow.aswarm(
        tasks=[task_sig_a.key, task_sig_b.key],
        task_name="test-swarm-integration",
    )

    # Call afill_swarm directly on the test_adapter
    await test_adapter.afill_swarm(swarm_sig)

    record = test_adapter.assert_swarm_dispatched("test-swarm-integration")
    assert isinstance(record, SwarmDispatchRecord)
    # The key assertion: task_names must be non-empty (not the [] fallback from except branch)
    assert len(record.task_names) == 2
    assert "swarm-sub-task-a" in record.task_names
    assert "swarm-sub-task-b" in record.task_names
