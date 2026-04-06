"""Unit tests for workflow composition in chain and swarm (WFCPS-02, WFCPS-03).

Proves that:
  WFCPS-02: WorkflowSignature participates in SwarmTaskSignature as a single atomic unit
  WFCPS-03: resolve_signatures() explicitly converts Workflow objects via isinstance branch

Tests use the hatchet_mock and hatchet_adapter fixtures from the unit conftest,
following the same pattern as test_workflow_sign.py.
"""

import pytest
import rapyer
from thirdmagic.chain.model import ChainTaskSignature
from thirdmagic.signature import Signature
from thirdmagic.swarm.model import SwarmTaskSignature
from thirdmagic.task import TaskSignature

import mageflow
from mageflow.clients.hatchet.adapter import HatchetClientAdapter
from tests.integration.hatchet.models import ContextMessage

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def workflow(hatchet_mock):
    """Create a primary Workflow object for composition tests."""
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
# WFCPS-03: Workflow in chain composition
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_workflow_in_chain_creates_correct_subtasks(workflow, hatchet_adapter):
    """achain([workflow_obj, task_sig]) returns ChainTaskSignature with 2 sub-tasks.

    The first sub-task is a workflow-derived TaskSignature with task_name == workflow.name.
    Covers WFCPS-03: raw Workflow object auto-resolved via resolve_signatures.
    """
    task_sig = await mageflow.asign("support-task", model_validators=ContextMessage)

    chain_sig = await mageflow.achain([workflow, task_sig])

    assert isinstance(chain_sig, ChainTaskSignature)
    assert len(chain_sig.tasks) == 2

    # First sub-task should be the workflow-derived TaskSignature
    wf_task = await rapyer.afind_one(chain_sig.tasks[0])
    assert wf_task is not None
    assert isinstance(wf_task, TaskSignature)
    assert wf_task.task_name == workflow.name


@pytest.mark.asyncio
async def test_workflow_in_chain_subtask_has_container_id(workflow, hatchet_adapter):
    """After chaining, the workflow-derived sub-task has signature_container_id == chain_sig.key.

    Covers WFCPS-03: chain composition sets container_id on each sub-task.
    """
    task_sig = await mageflow.asign("support-task", model_validators=ContextMessage)

    chain_sig = await mageflow.achain([workflow, task_sig])

    wf_task = await rapyer.afind_one(chain_sig.tasks[0])
    assert wf_task is not None
    assert wf_task.signature_container_id == chain_sig.key


@pytest.mark.asyncio
async def test_workflow_in_chain_with_raw_object(workflow, hatchet_adapter):
    """achain([workflow_obj, workflow2_obj]) — raw Workflow objects auto-resolved.

    Both Workflow objects are converted to TaskSignature via resolve_signatures
    (which now has an explicit isinstance(Workflow) branch per WFCPS-03).
    Chain has 2 tasks, first one's task_name matches workflow.name.
    """
    workflow2 = hatchet_adapter.hatchet.workflow(
        name="notification-pipeline", input_validator=ContextMessage
    )

    chain_sig = await mageflow.achain([workflow, workflow2])

    assert isinstance(chain_sig, ChainTaskSignature)
    assert len(chain_sig.tasks) == 2

    first_task = await rapyer.afind_one(chain_sig.tasks[0])
    second_task = await rapyer.afind_one(chain_sig.tasks[1])

    assert first_task is not None
    assert second_task is not None
    assert first_task.task_name == workflow.name
    assert second_task.task_name == workflow2.name


# ---------------------------------------------------------------------------
# WFCPS-02: Workflow in swarm — tracked as single atomic unit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_workflow_in_swarm_tracked_as_single_unit(workflow, hatchet_adapter):
    """SwarmTaskSignature with a single workflow signature tracks it as one atomic unit.

    Covers WFCPS-02: workflow signature participates in swarm as a single unit —
    len(swarm.tasks) == 1, not split per workflow step.
    """
    wf_sig = await mageflow.asign(workflow)

    swarm = await mageflow.aswarm(
        [wf_sig],
        task_name="test-workflow-swarm",
        model_validators=ContextMessage,
        is_swarm_closed=True,
    )

    assert isinstance(swarm, SwarmTaskSignature)
    assert len(swarm.tasks) == 1
    assert swarm.tasks[0] == wf_sig.key


@pytest.mark.asyncio
async def test_workflow_in_swarm_has_container_id(workflow, hatchet_adapter):
    """After adding to swarm, workflow signature has signature_container_id == swarm.key.

    Covers WFCPS-02: swarm.add_tasks() sets container_id on the workflow signature.
    """
    wf_sig = await mageflow.asign(workflow)

    swarm = await mageflow.aswarm(
        [wf_sig],
        task_name="test-workflow-swarm-container",
        model_validators=ContextMessage,
        is_swarm_closed=True,
    )

    # Retrieve fresh copy from Redis to verify persistence
    retrieved_wf_sig = await rapyer.afind_one(wf_sig.key)
    assert retrieved_wf_sig is not None
    assert retrieved_wf_sig.signature_container_id == swarm.key


@pytest.mark.asyncio
async def test_workflow_raw_object_in_swarm_tracked_as_single_unit(
    workflow, hatchet_adapter
):
    """aswarm([workflow_obj]) auto-resolves Workflow and tracks as single unit.

    Covers WFCPS-02 + WFCPS-03: raw Workflow object is resolved to a single
    TaskSignature and added to swarm as one atomic unit.
    """
    swarm = await mageflow.aswarm(
        [workflow],
        task_name="test-raw-workflow-swarm",
        model_validators=ContextMessage,
        is_swarm_closed=True,
    )

    assert isinstance(swarm, SwarmTaskSignature)
    assert len(swarm.tasks) == 1

    wf_task = await rapyer.afind_one(swarm.tasks[0])
    assert wf_task is not None
    assert isinstance(wf_task, TaskSignature)
    assert wf_task.task_name == workflow.name
