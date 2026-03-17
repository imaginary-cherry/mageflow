"""Tests for task dispatch assertion API in TestClientAdapter."""

import pytest

from mageflow.testing import (
    ChainDispatchRecord,
    SwarmDispatchRecord,
    TaskDispatchRecord,
    TestClientAdapter,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_adapter() -> TestClientAdapter:
    """Create a fresh TestClientAdapter without any Redis dependency."""
    return TestClientAdapter()


def _append_task(
    adapter: TestClientAdapter, task_name: str, input_data: dict, **kwargs
) -> None:
    """Directly append a TaskDispatchRecord — tests assertion logic, not recording."""
    adapter._typed_dispatches.append(
        TaskDispatchRecord(task_name=task_name, input_data=input_data, kwargs=kwargs)
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAssertTaskDispatchedByName:
    def test_found(self):
        adapter = _make_adapter()
        _append_task(adapter, "my-task", {"order_id": 1})
        record = adapter.assert_task_dispatched("my-task")
        assert isinstance(record, TaskDispatchRecord)
        assert record.task_name == "my-task"

    def test_returns_first_matching_record(self):
        adapter = _make_adapter()
        _append_task(adapter, "my-task", {"order_id": 1})
        _append_task(adapter, "my-task", {"order_id": 2})
        record = adapter.assert_task_dispatched("my-task")
        assert record.input_data["order_id"] == 1


class TestAssertTaskDispatchedPartialMatch:
    def test_subset_of_keys_passes(self):
        adapter = _make_adapter()
        _append_task(adapter, "my-task", {"order_id": 123, "extra": "val"})
        record = adapter.assert_task_dispatched("my-task", {"order_id": 123})
        assert record.task_name == "my-task"

    def test_superset_input_passes(self):
        adapter = _make_adapter()
        _append_task(adapter, "my-task", {"a": 1, "b": 2, "c": 3})
        record = adapter.assert_task_dispatched("my-task", {"a": 1})
        assert record is not None

    def test_value_mismatch_fails(self):
        adapter = _make_adapter()
        _append_task(adapter, "my-task", {"order_id": 456})
        with pytest.raises(AssertionError, match="input did not match"):
            adapter.assert_task_dispatched("my-task", {"order_id": 123})

    def test_empty_expected_always_passes(self):
        adapter = _make_adapter()
        _append_task(adapter, "my-task", {"x": 99})
        record = adapter.assert_task_dispatched("my-task", {})
        assert record is not None


class TestAssertTaskDispatchedExactMatch:
    def test_exact_match_pass(self):
        adapter = _make_adapter()
        _append_task(adapter, "my-task", {"order_id": 123})
        record = adapter.assert_task_dispatched(
            "my-task", {"order_id": 123}, exact=True
        )
        assert record is not None

    def test_exact_match_fail_extra_keys(self):
        adapter = _make_adapter()
        _append_task(adapter, "my-task", {"order_id": 123, "extra": "val"})
        with pytest.raises(AssertionError, match="input did not match"):
            adapter.assert_task_dispatched("my-task", {"order_id": 123}, exact=True)

    def test_exact_match_fail_missing_key(self):
        adapter = _make_adapter()
        _append_task(adapter, "my-task", {"order_id": 123})
        with pytest.raises(AssertionError, match="input did not match"):
            adapter.assert_task_dispatched(
                "my-task", {"order_id": 123, "missing": "x"}, exact=True
            )


class TestAssertTaskDispatchedNotFound:
    def test_not_dispatched_raises(self):
        adapter = _make_adapter()
        _append_task(adapter, "other-task", {"x": 1})
        with pytest.raises(AssertionError, match="was not dispatched"):
            adapter.assert_task_dispatched("my-task")

    def test_error_lists_dispatched_names(self):
        adapter = _make_adapter()
        _append_task(adapter, "task-a", {})
        _append_task(adapter, "task-b", {})
        with pytest.raises(AssertionError, match="task-a"):
            adapter.assert_task_dispatched("task-missing")


class TestAssertTaskDispatchedArgMismatch:
    def test_diff_shows_expected_vs_actual(self):
        adapter = _make_adapter()
        _append_task(adapter, "my-task", {"order_id": 456})
        with pytest.raises(AssertionError) as exc_info:
            adapter.assert_task_dispatched("my-task", {"order_id": 123})
        msg = str(exc_info.value)
        assert "input did not match" in msg

    def test_diff_message_includes_key_info(self):
        adapter = _make_adapter()
        _append_task(adapter, "my-task", {"order_id": 456})
        with pytest.raises(AssertionError) as exc_info:
            adapter.assert_task_dispatched("my-task", {"order_id": 123})
        # The diff formatter shows field names and values
        msg = str(exc_info.value)
        assert "order_id" in msg


class TestAssertNothingDispatched:
    def test_no_dispatches_passes(self):
        adapter = _make_adapter()
        adapter.assert_nothing_dispatched()  # should not raise

    def test_one_dispatch_fails(self):
        adapter = _make_adapter()
        _append_task(adapter, "my-task", {})
        with pytest.raises(AssertionError, match="Expected no dispatches"):
            adapter.assert_nothing_dispatched()

    def test_error_shows_count_and_names(self):
        adapter = _make_adapter()
        _append_task(adapter, "my-task", {})
        _append_task(adapter, "another-task", {})
        with pytest.raises(AssertionError) as exc_info:
            adapter.assert_nothing_dispatched()
        msg = str(exc_info.value)
        assert "my-task" in msg or "another-task" in msg


class TestTaskDispatchesProperty:
    def test_returns_copy(self):
        adapter = _make_adapter()
        _append_task(adapter, "my-task", {})
        dispatches = adapter.task_dispatches
        dispatches.clear()
        # Original should be unaffected
        assert len(adapter.task_dispatches) == 1

    def test_filters_to_task_records_only(self):
        adapter = _make_adapter()
        _append_task(adapter, "my-task", {})
        adapter._typed_dispatches.append(
            SwarmDispatchRecord(swarm_name="my-swarm", task_names=[], kwargs={})
        )
        adapter._typed_dispatches.append(
            ChainDispatchRecord(chain_name="my-chain", results={}, task_names=[])
        )
        task_dispatches = adapter.task_dispatches
        assert len(task_dispatches) == 1
        assert task_dispatches[0].task_name == "my-task"


class TestAtLeastOneSemantics:
    def test_dispatch_same_task_twice_matches_either(self):
        adapter = _make_adapter()
        _append_task(adapter, "my-task", {"order_id": 1})
        _append_task(adapter, "my-task", {"order_id": 2})
        # Matches the second dispatch
        record = adapter.assert_task_dispatched("my-task", {"order_id": 2})
        assert record.input_data["order_id"] == 2

    def test_no_matching_dispatch_among_multiple_fails(self):
        adapter = _make_adapter()
        _append_task(adapter, "my-task", {"order_id": 1})
        _append_task(adapter, "my-task", {"order_id": 2})
        with pytest.raises(AssertionError, match="input did not match"):
            adapter.assert_task_dispatched("my-task", {"order_id": 999})
