"""Tests proving the dispatch path works for WorkflowSignature objects.

Covers WFDSP-01 and WFDSP-02:
  WFDSP-01: Dispatching a WorkflowSignature via acall() triggers dispatch recording
  WFDSP-02: _update_options embeds TASK_ID_PARAM_NAME in additional_metadata

These tests confirm that NO changes to HatchetClientAdapter are needed — the existing
dispatch mechanism already handles Workflow objects transparently.
"""

import pytest
import pytest_asyncio
from hatchet_sdk import ClientConfig, Hatchet
from hatchet_sdk.clients.admin import TriggerWorkflowOptions
from thirdmagic.consts import TASK_ID_PARAM_NAME
from thirdmagic.task import TaskSignature

import mageflow
from mageflow.clients.hatchet.adapter import HatchetClientAdapter
from mageflow.testing import TaskDispatchRecord
from tests.integration.hatchet.models import ContextMessage

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FAKE_JWT = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    ".eyJhdWQiOiJodHRwczovL2xvY2FsaG9zdCIsImV4cCI6NDkwNTQ3NzYyNiwiZ3JwY19icm9h"
    "ZGNhc3RfYWRkcmVzcyI6Imh0dHBzOi8vbG9jYWxob3N0IiwiaWF0IjoxNzUxODc3NjI2LCJpc3"
    "MiOiJodHRwczovL2xvY2FsaG9zdCIsInNlcnZlcl91cmwiOiJodHRwczovL2xvY2FsaG9zdCIsI"
    "nN1YiI6IjdlY2U4ZTk4LWNiMjMtNDg3Ny1hZGNlLWFmYTBiNDMxYTgyMyIsInRva2VuX2lkIjoiN"
    "jk0MjBkOGMtMTQ4NS00NGRlLWFmY2YtMDlkYzM5NmJiYzI0In0"
    ".l2yHtg1ZGJSkge6MnLXj_zGyg1w_6LZ7ZuyyNrWORnc"
)


def _make_hatchet() -> Hatchet:
    return Hatchet(config=ClientConfig(token=_FAKE_JWT, tls_strategy="tls"))


# ---------------------------------------------------------------------------
# WFDSP-02: _update_options embeds signature key in additional_metadata
# ---------------------------------------------------------------------------


class TestUpdateOptionsMetadataEmbedding:
    """Tests for HatchetClientAdapter._update_options() — proves WFDSP-02."""

    @pytest.fixture
    def adapter(self):
        return HatchetClientAdapter(_make_hatchet())

    @pytest.mark.asyncio
    async def test_update_options_embeds_task_id_param_name(self, adapter):
        """_update_options sets TASK_ID_PARAM_NAME in additional_metadata (WFDSP-02)."""
        sig = await mageflow.asign("test-task", model_validators=ContextMessage)
        options = adapter._update_options(sig)
        assert TASK_ID_PARAM_NAME in options.additional_metadata
        assert options.additional_metadata[TASK_ID_PARAM_NAME] == sig.key

    @pytest.mark.asyncio
    async def test_update_options_with_existing_options(self, adapter):
        """_update_options merges into existing TriggerWorkflowOptions (WFDSP-02)."""
        sig = await mageflow.asign("test-task", model_validators=ContextMessage)
        existing = TriggerWorkflowOptions()
        existing.additional_metadata = {"other_key": "other_value"}
        options = adapter._update_options(sig, existing)
        assert options.additional_metadata[TASK_ID_PARAM_NAME] == sig.key
        assert options.additional_metadata["other_key"] == "other_value"

    @pytest.mark.asyncio
    async def test_update_options_creates_new_options_when_none(self, adapter):
        """_update_options creates TriggerWorkflowOptions when options=None (WFDSP-02)."""
        sig = await mageflow.asign("test-task", model_validators=ContextMessage)
        options = adapter._update_options(sig, None)
        assert isinstance(options, TriggerWorkflowOptions)
        assert TASK_ID_PARAM_NAME in options.additional_metadata

    @pytest.mark.asyncio
    async def test_update_options_uses_signature_key_as_task_id(self, adapter):
        """The embedded task ID matches sig.key exactly (WFDSP-02)."""
        sig = await mageflow.asign("my-workflow", model_validators=ContextMessage)
        options = adapter._update_options(sig)
        assert options.additional_metadata[TASK_ID_PARAM_NAME] == sig.key


# ---------------------------------------------------------------------------
# WFDSP-01: Dispatch via TestClientAdapter records a TaskDispatchRecord
# ---------------------------------------------------------------------------


class TestWorkflowDispatchRecording:
    """Tests proving the sign→acall→assert path works for Workflow objects (WFDSP-01)."""

    @pytest.mark.asyncio(loop_scope="session")
    async def test_dispatch_workflow_signature_creates_dispatch_record(
        self, mageflow_client
    ):
        """Dispatching a signed Workflow creates a TaskDispatchRecord (WFDSP-01)."""
        hatchet = _make_hatchet()
        wf = hatchet.workflow(name="test-dispatch-wf", input_validator=ContextMessage)

        sig = await mageflow.asign(wf)
        await sig.acall({"base_data": {"id": 1}})

        records = [
            d for d in mageflow_client._typed_dispatches if isinstance(d, TaskDispatchRecord)
        ]
        assert any(d.task_name == sig.task_name for d in records)

    @pytest.mark.asyncio(loop_scope="session")
    async def test_assert_task_dispatched_finds_workflow_by_signature_name(
        self, mageflow_client
    ):
        """assert_task_dispatched(sig.task_name) returns the record (WFDSP-01)."""
        hatchet = _make_hatchet()
        wf = hatchet.workflow(name="assert-wf-dispatch", input_validator=ContextMessage)

        sig = await mageflow.asign(wf)
        await sig.acall({"base_data": {"id": 2}})

        record = mageflow_client.assert_task_dispatched(sig.task_name)
        assert isinstance(record, TaskDispatchRecord)
        assert record.task_name == sig.task_name

    @pytest.mark.asyncio(loop_scope="session")
    async def test_dispatch_path_unchanged_for_workflow_vs_standalone(
        self, mageflow_client
    ):
        """The dispatch path for Workflow sigs is identical to standalone task sigs (WFDSP-01).

        Both TaskSignature objects go through the same acall_signature path — this test
        confirms dispatch recording works for workflow-derived task names.
        """
        # Standalone task signature
        standalone_sig = await mageflow.asign(
            "standalone-task", model_validators=ContextMessage
        )

        # Workflow-derived signature
        hatchet = _make_hatchet()
        wf = hatchet.workflow(name="workflow-vs-standalone", input_validator=ContextMessage)
        workflow_sig = await mageflow.asign(wf)

        await standalone_sig.acall({"base_data": {"key": "standalone"}})
        await workflow_sig.acall({"base_data": {"key": "workflow"}})

        standalone_record = mageflow_client.assert_task_dispatched("standalone-task")
        workflow_record = mageflow_client.assert_task_dispatched("workflow-vs-standalone")

        assert isinstance(standalone_record, TaskDispatchRecord)
        assert isinstance(workflow_record, TaskDispatchRecord)
