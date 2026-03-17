"""Tests for chain dispatch assertion API in TestClientAdapter."""

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
    return TestClientAdapter()


def _append_chain(
    adapter: TestClientAdapter,
    chain_name: str,
    task_names: list[str],
    results: object = None,
) -> None:
    adapter._typed_dispatches.append(
        ChainDispatchRecord(
            chain_name=chain_name,
            results=results or {},
            task_names=task_names,
        )
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAssertChainDispatchedByName:
    def test_found(self):
        adapter = _make_adapter()
        _append_chain(adapter, "my-chain", ["task-a", "task-b"])
        record = adapter.assert_chain_dispatched("my-chain")
        assert isinstance(record, ChainDispatchRecord)
        assert record.chain_name == "my-chain"

    def test_not_found_raises(self):
        adapter = _make_adapter()
        _append_chain(adapter, "other-chain", [])
        with pytest.raises(AssertionError, match="was not dispatched"):
            adapter.assert_chain_dispatched("my-chain")

    def test_error_lists_dispatched_chains(self):
        adapter = _make_adapter()
        _append_chain(adapter, "chain-a", [])
        with pytest.raises(AssertionError, match="chain-a"):
            adapter.assert_chain_dispatched("chain-missing")


class TestAssertChainDispatchedWithTaskNames:
    def test_expected_task_names_subset_passes(self):
        adapter = _make_adapter()
        _append_chain(adapter, "my-chain", ["task-a", "task-b", "task-c"])
        record = adapter.assert_chain_dispatched(
            "my-chain", expected_task_names=["task-a"]
        )
        assert record is not None

    def test_all_expected_present_passes(self):
        adapter = _make_adapter()
        _append_chain(adapter, "my-chain", ["task-a", "task-b"])
        record = adapter.assert_chain_dispatched(
            "my-chain", expected_task_names=["task-a", "task-b"]
        )
        assert record is not None

    def test_missing_task_name_fails(self):
        adapter = _make_adapter()
        _append_chain(adapter, "my-chain", ["task-a"])
        with pytest.raises(AssertionError, match="task names did not match"):
            adapter.assert_chain_dispatched(
                "my-chain", expected_task_names=["task-a", "task-b"]
            )

    def test_error_message_includes_expected_and_actual(self):
        adapter = _make_adapter()
        _append_chain(adapter, "my-chain", ["task-x"])
        with pytest.raises(AssertionError) as exc_info:
            adapter.assert_chain_dispatched(
                "my-chain", expected_task_names=["task-missing"]
            )
        msg = str(exc_info.value)
        assert "task-missing" in msg
        assert "task-x" in msg


class TestChainDispatchesProperty:
    def test_filters_to_chain_records_only(self):
        adapter = _make_adapter()
        adapter._typed_dispatches.append(
            TaskDispatchRecord(task_name="my-task", input_data={}, kwargs={})
        )
        adapter._typed_dispatches.append(
            SwarmDispatchRecord(swarm_name="my-swarm", task_names=[], kwargs={})
        )
        _append_chain(adapter, "my-chain", ["task-a"])
        chain_dispatches = adapter.chain_dispatches
        assert len(chain_dispatches) == 1
        assert chain_dispatches[0].chain_name == "my-chain"


class TestMixedDispatchesFilteredCorrectly:
    def test_each_typed_property_returns_only_its_type(self):
        adapter = _make_adapter()

        adapter._typed_dispatches.append(
            TaskDispatchRecord(task_name="task-1", input_data={}, kwargs={})
        )
        adapter._typed_dispatches.append(
            SwarmDispatchRecord(swarm_name="swarm-1", task_names=[], kwargs={})
        )
        _append_chain(adapter, "chain-1", [])

        assert len(adapter.task_dispatches) == 1
        assert len(adapter.swarm_dispatches) == 1
        assert len(adapter.chain_dispatches) == 1

        assert adapter.task_dispatches[0].task_name == "task-1"
        assert adapter.swarm_dispatches[0].swarm_name == "swarm-1"
        assert adapter.chain_dispatches[0].chain_name == "chain-1"

    def test_dispatches_property_returns_all_raw_records(self):
        """dispatches property includes ALL RecordedDispatch items (separate list)."""
        adapter = _make_adapter()
        # typed dispatches are separate from raw dispatches
        adapter._typed_dispatches.append(
            TaskDispatchRecord(task_name="task-1", input_data={}, kwargs={})
        )
        adapter._dispatches.append(
            RecordedDispatch(
                dispatch_type="signature",
                signature_or_name="task-1",
                input_data={},
                kwargs={},
            )
        )
        assert len(adapter.dispatches) == 1
        assert len(adapter.task_dispatches) == 1

    def test_clear_resets_all_dispatch_lists(self):
        adapter = _make_adapter()
        adapter._typed_dispatches.append(
            TaskDispatchRecord(task_name="task-1", input_data={}, kwargs={})
        )

        adapter._dispatches.append(
            RecordedDispatch(
                dispatch_type="signature",
                signature_or_name="task-1",
                input_data={},
                kwargs={},
            )
        )
        adapter.clear()
        assert len(adapter.task_dispatches) == 0
        assert len(adapter.dispatches) == 0
