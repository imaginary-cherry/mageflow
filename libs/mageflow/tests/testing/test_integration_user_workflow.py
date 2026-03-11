"""Integration tests emulating user workflows with the mageflow testing API.

These tests serve as usage examples for downstream consumers.
"""

import pytest

import mageflow
from mageflow.testing._adapter import SwarmDispatchRecord, TaskDispatchRecord
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# TestTaskDispatchWorkflow
# ---------------------------------------------------------------------------


class TestTaskDispatchWorkflow:
    """A user creates task signatures, dispatches them, and verifies dispatches."""

    @pytest.mark.asyncio(loop_scope="session")
    async def test_dispatch_task_and_verify(self, mageflow_client):
        """User dispatches a single task and asserts it was recorded."""
        # Create a task signature via the public mageflow API
        task_sig = await mageflow.asign("process-order", model_validators=BaseModel)

        # Dispatch the task
        await task_sig.acall({"order_id": 123})

        # Assert it was dispatched with the expected input
        record = mageflow_client.assert_task_dispatched("process-order", {"order_id": 123})
        assert isinstance(record, TaskDispatchRecord)
        assert record.task_name == "process-order"
        assert record.input_data == {"order_id": 123}

    @pytest.mark.asyncio(loop_scope="session")
    async def test_dispatch_multiple_tasks_and_verify_each(self, mageflow_client):
        """User dispatches two different tasks and verifies each independently."""
        sig_email = await mageflow.asign("send-email", model_validators=BaseModel)
        sig_inventory = await mageflow.asign("update-inventory", model_validators=BaseModel)

        await sig_email.acall({"to": "user@example.com"})
        await sig_inventory.acall({"product_id": 42, "quantity": 5})

        # Verify each task was dispatched
        email_record = mageflow_client.assert_task_dispatched("send-email", {"to": "user@example.com"})
        assert email_record.task_name == "send-email"

        inventory_record = mageflow_client.assert_task_dispatched("update-inventory", {"product_id": 42})
        assert inventory_record.task_name == "update-inventory"

        # Verify total task dispatch count
        assert len(mageflow_client.task_dispatches) == 2

    @pytest.mark.asyncio(loop_scope="session")
    async def test_dispatch_task_with_partial_input_match(self, mageflow_client):
        """User can assert with partial match (default) or exact match (opt-in)."""
        task_sig = await mageflow.asign("track-event", model_validators=BaseModel)
        full_input = {"user_id": 1, "action": "buy", "timestamp": "now"}

        await task_sig.acall(full_input)

        # Partial match: only assert the key fields the test cares about
        record = mageflow_client.assert_task_dispatched("track-event", {"user_id": 1})
        assert record is not None

        # Exact match: full dict must match exactly
        record = mageflow_client.assert_task_dispatched(
            "track-event", full_input, exact=True
        )
        assert record is not None


# ---------------------------------------------------------------------------
# TestChainDispatchWorkflow
# ---------------------------------------------------------------------------


class TestChainDispatchWorkflow:
    """A user creates a chain of tasks and dispatches it."""

    @pytest.mark.asyncio(loop_scope="session")
    async def test_dispatch_chain_and_verify(self, mageflow_client):
        """User dispatches a chain and verifies the first task was dispatched.

        Note: chain.acall dispatches the first task in the chain (not the chain
        itself). assert_chain_dispatched only fires on acall_chain_done, which
        requires the callback flow — not triggered by acall alone.
        """
        sig_validate = await mageflow.asign("validate-order", model_validators=BaseModel)
        sig_charge = await mageflow.asign("charge-payment", model_validators=BaseModel)

        chain_sig = await mageflow.achain(
            tasks=[sig_validate.key, sig_charge.key],
            name="order-pipeline",
        )

        # Dispatch the chain — this dispatches the first task in the chain
        await chain_sig.acall({"order_id": 456})

        # The first task in the chain gets dispatched via acall
        record = mageflow_client.assert_task_dispatched("validate-order")
        assert isinstance(record, TaskDispatchRecord)
        assert record.task_name == "validate-order"


# ---------------------------------------------------------------------------
# TestSwarmDispatchWorkflow
# ---------------------------------------------------------------------------


class TestSwarmDispatchWorkflow:
    """A user creates a swarm of tasks and dispatches it."""

    @pytest.mark.asyncio(loop_scope="session")
    async def test_dispatch_swarm_and_verify(self, mageflow_client):
        """User fills a swarm and verifies the dispatch with task name assertions."""
        sig_resize = await mageflow.asign("resize-image", model_validators=BaseModel)
        sig_compress = await mageflow.asign("compress-image", model_validators=BaseModel)

        swarm_sig = await mageflow.aswarm(
            tasks=[sig_resize.key, sig_compress.key],
            task_name="image-processing",
        )

        # acall on a swarm calls afill_swarm internally
        await swarm_sig.acall({"batch_id": 789})

        # Verify the swarm was dispatched with both sub-tasks
        record = mageflow_client.assert_swarm_dispatched(
            "image-processing",
            expected_task_names=["resize-image", "compress-image"],
        )
        assert isinstance(record, SwarmDispatchRecord)
        assert record.swarm_name == "image-processing"
        assert "resize-image" in record.task_names
        assert "compress-image" in record.task_names


# ---------------------------------------------------------------------------
# TestCleanSlateWorkflow
# ---------------------------------------------------------------------------


class TestCleanSlateWorkflow:
    """A user verifies the adapter is clean before and after tests."""

    @pytest.mark.asyncio(loop_scope="session")
    async def test_nothing_dispatched_on_fresh_adapter(self, mageflow_client):
        """User asserts nothing was dispatched on a freshly created adapter."""
        # No dispatches have occurred — should pass without error
        mageflow_client.assert_nothing_dispatched()

    @pytest.mark.asyncio(loop_scope="session")
    async def test_clear_resets_after_dispatches(self, mageflow_client):
        """User dispatches a task, clears the adapter, and verifies clean state."""
        task_sig = await mageflow.asign("cleanup-task", model_validators=BaseModel)
        await task_sig.acall({"resource": "temp-file"})

        # Something was dispatched
        assert len(mageflow_client.task_dispatches) == 1

        # Clear all recorded dispatches
        mageflow_client.clear()

        # Now the adapter is clean again
        mageflow_client.assert_nothing_dispatched()
        assert len(mageflow_client.task_dispatches) == 0
        assert len(mageflow_client.dispatches) == 0


# ---------------------------------------------------------------------------
# TestMixedWorkflow
# ---------------------------------------------------------------------------


class TestMixedWorkflow:
    """A user dispatches multiple signature types in the same test."""

    @pytest.mark.asyncio(loop_scope="session")
    async def test_dispatch_task_and_swarm_then_verify_independently(self, mageflow_client):
        """User dispatches a task and a swarm, then verifies each independently.

        Demonstrates that task_dispatches, swarm_dispatches, and dispatches (raw)
        are separate views over the same adapter state.
        """
        # Dispatch a single task
        task_sig = await mageflow.asign("log-event", model_validators=BaseModel)
        await task_sig.acall({"event": "user-login"})

        # Dispatch a swarm
        sig_a = await mageflow.asign("notify-sms", model_validators=BaseModel)
        sig_b = await mageflow.asign("notify-push", model_validators=BaseModel)
        swarm_sig = await mageflow.aswarm(
            tasks=[sig_a.key, sig_b.key],
            task_name="notification-swarm",
        )
        await swarm_sig.acall({"user_id": 99})

        # Verify typed dispatch counts
        assert len(mageflow_client.task_dispatches) == 1
        assert len(mageflow_client.swarm_dispatches) == 1

        # Raw dispatches includes both (acall_signature + afill_swarm)
        assert len(mageflow_client.dispatches) == 2

        # Use typed assertion methods for each
        task_record = mageflow_client.assert_task_dispatched("log-event", {"event": "user-login"})
        assert task_record.task_name == "log-event"

        swarm_record = mageflow_client.assert_swarm_dispatched(
            "notification-swarm",
            expected_task_names=["notify-sms", "notify-push"],
        )
        assert swarm_record.swarm_name == "notification-swarm"
