"""Tests for sign() and resolve_signatures() with Hatchet Workflow objects.

Verifies the full path: sign(workflow_obj) creates a TaskSignature,
persists to Redis, and resolve_signatures handles Workflow objects
via the from_task() path.
"""

import pytest
import pytest_asyncio
import rapyer
from thirdmagic.signature import Signature
from thirdmagic.task import TaskSignature
from thirdmagic.task.creator import resolve_signatures

import mageflow
from mageflow.clients.hatchet.adapter import HatchetClientAdapter
from tests.integration.hatchet.models import ContextMessage


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def workflow(hatchet_mock):
    """Create a Workflow object for testing sign()."""
    return hatchet_mock.workflow(name="order-pipeline", input_validator=ContextMessage)


@pytest.fixture
def hatchet_adapter(hatchet_mock):
    """Set HatchetClientAdapter as the active Signature.ClientAdapter.

    Saves and restores original adapter around each test to avoid cross-test pollution.
    """
    adapter = HatchetClientAdapter(hatchet_mock)
    original = Signature.ClientAdapter
    Signature.ClientAdapter = adapter
    yield adapter
    Signature.ClientAdapter = original


# ---------------------------------------------------------------------------
# Tests: sign(workflow_obj)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sign_workflow_returns_task_signature(workflow, hatchet_adapter):
    """sign(workflow_obj) returns a TaskSignature instance."""
    sig = await mageflow.asign(workflow)
    assert isinstance(sig, TaskSignature)


@pytest.mark.asyncio
async def test_sign_workflow_has_correct_task_name(workflow, hatchet_adapter):
    """sig.task_name matches the adapter-derived name (workflow.name)."""
    sig = await mageflow.asign(workflow)
    expected_name = hatchet_adapter.task_name(workflow)
    assert sig.task_name == expected_name


@pytest.mark.asyncio
async def test_sign_workflow_has_correct_validator(workflow, hatchet_adapter):
    """sig.model_validators is ContextMessage (the workflow's input_validator)."""
    sig = await mageflow.asign(workflow)
    assert sig.model_validators is ContextMessage


@pytest.mark.asyncio
async def test_sign_workflow_persists_to_redis(workflow, hatchet_adapter):
    """After sign(), TaskSignature.afind(sig.key) retrieves the same signature."""
    sig = await mageflow.asign(workflow)
    # Retrieve from Redis by key
    retrieved = await rapyer.afind_one(sig.key)
    assert retrieved is not None
    assert retrieved.task_name == sig.task_name


@pytest.mark.asyncio
async def test_sign_workflow_with_callbacks(workflow, hatchet_adapter):
    """sign(workflow, on_success='cb-task') sets success callback on the signature."""
    # Create a callback task first
    cb_sig = await mageflow.asign("cb-task", model_validators=ContextMessage)
    sig = await mageflow.asign(workflow, success_callbacks=[cb_sig.key])
    assert len(sig.success_callbacks) == 1
    assert sig.success_callbacks[0] == cb_sig.key


# ---------------------------------------------------------------------------
# Tests: resolve_signatures([workflow_obj])
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_signatures_with_workflow(workflow, hatchet_adapter):
    """resolve_signatures([workflow_obj]) returns a list with one TaskSignature."""
    result = await resolve_signatures([workflow])

    assert isinstance(result, list)
    assert len(result) == 1
    assert isinstance(result[0], TaskSignature)


@pytest.mark.asyncio
async def test_resolve_signatures_workflow_task_name_matches(workflow, hatchet_adapter):
    """The resolved TaskSignature has the correct task_name derived from the workflow."""
    result = await resolve_signatures([workflow])
    expected_name = hatchet_adapter.task_name(workflow)
    assert result[0].task_name == expected_name
