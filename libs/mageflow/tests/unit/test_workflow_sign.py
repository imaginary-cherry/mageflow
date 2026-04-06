import typing

import pytest
from hatchet_sdk.runnables.workflow import BaseWorkflow, Workflow
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
    return hatchet_mock.workflow(name="order-pipeline", input_validator=ContextMessage)


@pytest.fixture
def hatchet_adapter(hatchet_mock):
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
    sig = await mageflow.asign(workflow)
    assert isinstance(sig, TaskSignature)


@pytest.mark.asyncio
async def test_sign_workflow_has_correct_task_name(workflow, hatchet_adapter):
    sig = await mageflow.asign(workflow)
    expected_name = hatchet_adapter.task_name(workflow)
    assert sig.task_name == expected_name


@pytest.mark.asyncio
async def test_sign_workflow_has_correct_validator(workflow, hatchet_adapter):
    sig = await mageflow.asign(workflow)
    assert sig.model_validators is ContextMessage


@pytest.mark.asyncio
async def test_sign_workflow_persists_to_redis(workflow, hatchet_adapter):
    sig = await mageflow.asign(workflow)
    # Retrieve from Redis by key
    retrieved = await TaskSignature.afind_one(sig.key)
    assert retrieved is not None
    assert retrieved.task_name == sig.task_name


@pytest.mark.asyncio
async def test_sign_workflow_with_callbacks(workflow, hatchet_adapter):
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
    result = await resolve_signatures([workflow])

    assert isinstance(result, list)
    assert len(result) == 1
    assert isinstance(result[0], TaskSignature)


@pytest.mark.asyncio
async def test_resolve_signatures_workflow_task_name_matches(workflow, hatchet_adapter):
    result = await resolve_signatures([workflow])
    expected_name = hatchet_adapter.task_name(workflow)
    assert result[0].task_name == expected_name


@pytest.mark.asyncio
async def test_resolve_signatures_mixed_workflow_and_tasks(workflow, hatchet_adapter):
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
    assert isinstance(
        workflow, Workflow
    ), "fixture must be a Workflow for this test to be valid"

    result = await resolve_signatures([workflow])
    sig = result[0]

    assert isinstance(sig, TaskSignature)
    assert sig.model_validators is ContextMessage


@pytest.mark.asyncio
async def test_hatchet_task_type_includes_workflow():
    # HatchetTaskType is a type union — verify Workflow is a valid member
    # by checking it's present in the union's args
    from thirdmagic.utils import HatchetTaskType

    args = typing.get_args(HatchetTaskType)
    assert BaseWorkflow in args, f"Workflow not found in HatchetTaskType args: {args}"
