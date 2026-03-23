"""Tests for HatchetMageflow.workflow() decorator method.

Covers WFDEC-01, WFDEC-02, WFDEC-03:
  WFDEC-01: mf.workflow(name=...) returns a native Hatchet Workflow object
  WFDEC-02: A MageflowTaskDefinition is recorded in mf._task_defs with correct fields
  WFDEC-03: @workflow.task() and @workflow.task(parents=[...]) work as pure passthrough
"""

import pytest
from hatchet_sdk import ClientConfig, Hatchet
from hatchet_sdk.runnables.workflow import Workflow
from pydantic import BaseModel

import mageflow
from mageflow.clients.hatchet.mageflow import HatchetMageflow
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
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def hatchet():
    return _make_hatchet()


@pytest.fixture
def mf(hatchet, redis_client):
    """HatchetMageflow instance backed by a real Hatchet (fake JWT) and fake Redis."""
    return HatchetMageflow(hatchet, redis_client)


# ---------------------------------------------------------------------------
# WFDEC-01: Returns a native Hatchet Workflow object
# ---------------------------------------------------------------------------


def test_workflow_returns_workflow_instance(mf):
    """mf.workflow(name=...) returns a Hatchet Workflow object (WFDEC-01)."""
    wf = mf.workflow(name="my-wf")
    assert isinstance(wf, Workflow)


def test_workflow_with_input_validator_returns_workflow_instance(mf):
    """mf.workflow(name=..., input_validator=MyModel) returns a Workflow (WFDEC-01)."""
    wf = mf.workflow(name="typed-wf", input_validator=ContextMessage)
    assert isinstance(wf, Workflow)


# ---------------------------------------------------------------------------
# WFDEC-02: MageflowTaskDefinition recorded in _task_defs
# ---------------------------------------------------------------------------


def test_workflow_records_task_def(mf):
    """mf.workflow() appends a MageflowTaskDefinition to mf._task_defs (WFDEC-02)."""
    assert len(mf._task_defs) == 0
    mf.workflow(name="my-wf")
    assert len(mf._task_defs) == 1


def test_workflow_task_def_has_correct_task_name(mf):
    """Recorded MageflowTaskDefinition.task_name matches the workflow name (WFDEC-02)."""
    mf.workflow(name="order-pipeline")
    task_def = mf._task_defs[0]
    assert task_def.task_name == "order-pipeline"
    assert task_def.mageflow_task_name == "order-pipeline"


def test_workflow_task_def_retries_is_none(mf):
    """Recorded MageflowTaskDefinition.retries is None — no workflow-level retries (WFDEC-02)."""
    mf.workflow(name="my-wf")
    task_def = mf._task_defs[0]
    assert task_def.retries is None


def test_workflow_task_def_stores_input_validator(mf):
    """Recorded MageflowTaskDefinition.input_validator matches the user-supplied type (WFDEC-02)."""
    mf.workflow(name="typed-wf", input_validator=ContextMessage)
    task_def = mf._task_defs[0]
    assert task_def.input_validator is ContextMessage


def test_workflow_task_def_input_validator_none_when_not_supplied(mf):
    """input_validator is None when not provided to mf.workflow() (WFDEC-02)."""
    mf.workflow(name="no-validator-wf")
    task_def = mf._task_defs[0]
    assert task_def.input_validator is None


def test_workflow_multiple_registrations(mf):
    """Multiple mf.workflow() calls each append a separate MageflowTaskDefinition."""
    mf.workflow(name="wf-alpha")
    mf.workflow(name="wf-beta", input_validator=ContextMessage)
    assert len(mf._task_defs) == 2
    names = {td.task_name for td in mf._task_defs}
    assert names == {"wf-alpha", "wf-beta"}


# ---------------------------------------------------------------------------
# WFDEC-03: @workflow.task() is pure passthrough — no mageflow wrapping
# ---------------------------------------------------------------------------


def test_workflow_task_decorator_creates_task(mf):
    """@workflow.task() on the returned Workflow registers a step (WFDEC-03)."""
    wf = mf.workflow(name="step-wf", input_validator=ContextMessage)

    @wf.task()
    async def step1(input: ContextMessage):
        return {}

    assert len(wf.tasks) == 1


def test_workflow_task_with_parents_creates_dag(mf):
    """@workflow.task(parents=[step1]) sets DAG dependency — step2.parents contains step1 (WFDEC-03)."""
    wf = mf.workflow(name="dag-wf", input_validator=ContextMessage)

    @wf.task()
    async def step1(input: ContextMessage):
        return {}

    @wf.task(parents=[step1])
    async def step2(input: ContextMessage):
        return {}

    assert len(wf.tasks) == 2
    # step2 has step1 as a parent
    step2_task = next(t for t in wf.tasks if t.name == "step2")
    assert step1 in step2_task.parents


def test_workflow_passthrough_kwargs(mf):
    """workflow() passes extra kwargs (e.g., on_events) to hatchet.workflow() without error (WFDEC-03)."""
    wf = mf.workflow(name="event-driven-wf", input_validator=ContextMessage, on_events=["my.event"])
    assert isinstance(wf, Workflow)
