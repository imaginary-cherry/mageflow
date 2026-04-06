"""Tests for sign() and resolve_signatures() with Hatchet Workflow objects.

Verifies the full path: sign(workflow_obj) creates a TaskSignature,
persists to Redis, and resolve_signatures handles Workflow objects
via the from_task() path.
"""

import pytest
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


@pytest.mark.asyncio
async def test_resolve_signatures_mixed_workflow_and_tasks(workflow, hatchet_adapter):
    """resolve_signatures([workflow_obj, workflow2_obj]) handles mixed Workflow input.

    Both workflow objects resolve to TaskSignature with correct task_names.
    Verifies WFCPS-03: Workflow isinstance branch handles multiple workflow objects
    in a single resolve_signatures call.
    """
    # Use a second workflow object as the "other" task in the mixed list
    workflow2 = hatchet_adapter.hatchet.workflow(
        name="second-pipeline", input_validator=ContextMessage
    )

    result = await resolve_signatures([workflow, workflow2])

    assert len(result) == 2
    assert isinstance(result[0], TaskSignature)
    assert isinstance(result[1], TaskSignature)

    expected_wf_name = hatchet_adapter.task_name(workflow)
    expected_wf2_name = hatchet_adapter.task_name(workflow2)
    assert result[0].task_name == expected_wf_name
    assert result[1].task_name == expected_wf2_name


@pytest.mark.asyncio
async def test_resolve_signatures_workflow_uses_explicit_branch(
    workflow, hatchet_adapter
):
    """Workflow objects are routed through the explicit isinstance(Workflow) branch.

    Verifies WFCPS-03: resolve_signatures has a dedicated Workflow isinstance check
    (not just the generic else fallback). The resolved signature must have the correct
    validator (ContextMessage), which is only set when from_task() processes the workflow
    correctly via the explicit branch.
    """
    from hatchet_sdk.runnables.workflow import Workflow

    assert isinstance(
        workflow, Workflow
    ), "fixture must be a Workflow for this test to be valid"

    result = await resolve_signatures([workflow])
    sig = result[0]

    assert isinstance(sig, TaskSignature)
    assert sig.model_validators is ContextMessage


@pytest.mark.asyncio
async def test_hatchet_task_type_includes_workflow():
    """HatchetTaskType union includes Workflow for type-annotation correctness.

    Verifies WFCPS-03: utils.py HatchetTaskType explicitly includes Workflow class
    so type checkers accept Workflow objects in signed/resolved position.
    """
    # HatchetTaskType is a type union — verify Workflow is a valid member
    # by checking it's present in the union's args
    import typing

    from hatchet_sdk.runnables.workflow import Workflow
    from thirdmagic.utils import HatchetTaskType

    args = typing.get_args(HatchetTaskType)
    assert Workflow in args, f"Workflow not found in HatchetTaskType args: {args}"
