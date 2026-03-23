"""Tests for Workflow dispatch and assertion via TestClientAdapter.

Verifies the full sign-to-dispatch-to-assert path for Hatchet Workflow objects:
sign(workflow_obj) → acall() → assert_task_dispatched(workflow_name).
"""

import pytest
from hatchet_sdk import ClientConfig, Hatchet
from pydantic import BaseModel

import mageflow
from mageflow.testing import TaskDispatchRecord
from tests.integration.hatchet.models import ContextMessage

# ---------------------------------------------------------------------------
# Shared JWT token for creating Hatchet instances in tests
# ---------------------------------------------------------------------------

_FAKE_JWT = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    ".eyJhdWQiOiJodHRwczovL2xvY2FsaG9zdCIsImV4cCI6NDkwNTQ3NzYyNiwiZ3JwY19icm9"
    "hZGNhc3RfYWRkcmVzcyI6Imh0dHBzOi8vbG9jYWxob3N0IiwiaWF0IjoxNzUxODc3NjI2LCJpc"
    "3MiOiJodHRwczovL2xvY2FsaG9zdCIsInNlcnZlcl91cmwiOiJodHRwczovL2xvY2FsaG9zdCIsI"
    "nN1YiI6IjdlY2U4ZTk4LWNiMjMtNDg3Ny1hZGNlLWFmYTBiNDMxYTgyMyIsInRva2VuX2lkIjoiN"
    "jk0MjBkOGMtMTQ4NS00NGRlLWFmY2YtMDlkYzM5NmJiYzI0In0"
    ".l2yHtg1ZGJSkge6MnLXj_zGyg1w_6LZ7ZuyyNrWORnc"
)


def _make_hatchet() -> Hatchet:
    """Create a Hatchet instance with fake JWT for tests."""
    return Hatchet(config=ClientConfig(token=_FAKE_JWT, tls_strategy="tls"))


# ---------------------------------------------------------------------------
# Tests: sign + dispatch + assert for Workflow objects
# ---------------------------------------------------------------------------


class TestWorkflowDispatch:
    """Full sign-to-dispatch-to-assert path for Workflow objects."""

    @pytest.mark.asyncio(loop_scope="session")
    async def test_dispatch_workflow_records_task_dispatch_record(self, mageflow_client):
        """After sign(workflow) + acall(), _typed_dispatches contains a TaskDispatchRecord."""
        hatchet = _make_hatchet()
        workflow = hatchet.workflow(name="order-pipeline", input_validator=ContextMessage)

        sig = await mageflow.asign(workflow)
        await sig.acall({"base_data": {"order_id": 1}})

        task_dispatches = [
            d for d in mageflow_client._typed_dispatches
            if isinstance(d, TaskDispatchRecord)
        ]
        assert len(task_dispatches) >= 1
        assert any(d.task_name == sig.task_name for d in task_dispatches)

    @pytest.mark.asyncio(loop_scope="session")
    async def test_assert_task_dispatched_finds_workflow_by_name(self, mageflow_client):
        """assert_task_dispatched(workflow_name) returns the TaskDispatchRecord."""
        hatchet = _make_hatchet()
        workflow = hatchet.workflow(name="payment-workflow", input_validator=ContextMessage)

        sig = await mageflow.asign(workflow)
        await sig.acall({"base_data": {"amount": 100}})

        record = mageflow_client.assert_task_dispatched(sig.task_name)
        assert isinstance(record, TaskDispatchRecord)
        assert record.task_name == sig.task_name

    @pytest.mark.asyncio(loop_scope="session")
    async def test_dispatched_record_has_correct_input(self, mageflow_client):
        """record.input_data matches the dict passed to acall()."""
        hatchet = _make_hatchet()
        workflow = hatchet.workflow(name="inventory-workflow", input_validator=BaseModel)

        sig = await mageflow.asign(workflow)
        input_data = {"product_id": 42, "quantity": 5}
        await sig.acall(input_data)

        record = mageflow_client.assert_task_dispatched(sig.task_name, {"product_id": 42})
        assert record.input_data == input_data

    @pytest.mark.asyncio(loop_scope="session")
    async def test_workflow_task_name_derived_from_workflow_name(self, mageflow_client):
        """The dispatched task name matches the Hatchet workflow.name attribute."""
        hatchet = _make_hatchet()
        workflow_name = "notification-workflow"
        workflow = hatchet.workflow(name=workflow_name, input_validator=BaseModel)

        sig = await mageflow.asign(workflow)
        assert sig.task_name == workflow_name

        await sig.acall({"user_id": 99})
        record = mageflow_client.assert_task_dispatched(workflow_name)
        assert record.task_name == workflow_name
