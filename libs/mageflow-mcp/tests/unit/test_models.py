"""Unit tests for mageflow_mcp.models — verify all five Pydantic response models serialize to valid JSON."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from thirdmagic.signature.status import SignatureStatus

from mageflow_mcp.models import (
    ContainerSummary,
    LogEntry,
    SignatureInfo,
    SubTaskInfo,
    TaskDefinitionInfo,
)


def test__signature_info__serializes_to_valid_json() -> None:
    """SignatureInfo with all fields should produce valid JSON with status as string."""
    sig = SignatureInfo(
        key="task:abc123",
        signature_type="TaskSignature",
        task_name="my_task",
        status=SignatureStatus.ACTIVE,
        creation_time=datetime(2026, 2, 23, 12, 0, 0, tzinfo=timezone.utc),
        worker_task_id="worker-task-001",
    )
    raw = sig.model_dump_json()
    data = json.loads(raw)
    assert isinstance(data, dict)
    assert data["key"] == "task:abc123"
    assert data["signature_type"] == "TaskSignature"
    assert data["task_name"] == "my_task"
    assert data["status"] == "active"
    assert data["worker_task_id"] == "worker-task-001"


def test__signature_info__optional_worker_task_id_defaults_to_none() -> None:
    """SignatureInfo created without worker_task_id should serialize it as null."""
    sig = SignatureInfo(
        key="task:def456",
        signature_type="ChainTaskSignature",
        task_name="chain_step",
        status=SignatureStatus.PENDING,
        creation_time=datetime(2026, 2, 23, 9, 0, 0, tzinfo=timezone.utc),
    )
    data = json.loads(sig.model_dump_json())
    assert data["worker_task_id"] is None


def test__container_summary__serializes_to_valid_json() -> None:
    """ContainerSummary should serialize all count fields to valid JSON."""
    summary = ContainerSummary(
        container_key="chain:container:xyz",
        signature_type="ChainTaskSignature",
        total=10,
        pending=3,
        active=2,
        done=4,
        failed=1,
        suspended=0,
        canceled=0,
    )
    raw = summary.model_dump_json()
    data = json.loads(raw)
    assert isinstance(data, dict)
    assert data["container_key"] == "chain:container:xyz"
    assert data["total"] == 10
    assert data["pending"] == 3
    assert data["active"] == 2
    assert data["done"] == 4
    assert data["failed"] == 1
    assert data["suspended"] == 0
    assert data["canceled"] == 0


def test__sub_task_info__serializes_to_valid_json() -> None:
    """SubTaskInfo minimal model should serialize to valid JSON."""
    sub = SubTaskInfo(
        key="task:sub:001",
        task_name="subtask_name",
        status=SignatureStatus.DONE,
    )
    raw = sub.model_dump_json()
    data = json.loads(raw)
    assert isinstance(data, dict)
    assert data["key"] == "task:sub:001"
    assert data["task_name"] == "subtask_name"
    assert data["status"] == "done"


def test__log_entry__serializes_to_valid_json() -> None:
    """LogEntry with optional timestamp should serialize to valid JSON."""
    entry_with_ts = LogEntry(
        line="Worker started processing task",
        timestamp=datetime(2026, 2, 23, 10, 30, 0, tzinfo=timezone.utc),
    )
    data_with = json.loads(entry_with_ts.model_dump_json())
    assert isinstance(data_with, dict)
    assert data_with["line"] == "Worker started processing task"
    assert data_with["timestamp"] is not None

    entry_no_ts = LogEntry(line="Another log line")
    data_no = json.loads(entry_no_ts.model_dump_json())
    assert data_no["timestamp"] is None


def test__task_definition_info__serializes_to_valid_json() -> None:
    """TaskDefinitionInfo with optional retries should serialize to valid JSON."""
    defn_with_retries = TaskDefinitionInfo(
        mageflow_task_name="my_mageflow_task",
        task_name="my_celery_task",
        retries=3,
    )
    data_with = json.loads(defn_with_retries.model_dump_json())
    assert isinstance(data_with, dict)
    assert data_with["mageflow_task_name"] == "my_mageflow_task"
    assert data_with["task_name"] == "my_celery_task"
    assert data_with["retries"] == 3

    defn_no_retries = TaskDefinitionInfo(
        mageflow_task_name="simple_task",
        task_name="simple_celery_task",
    )
    data_no = json.loads(defn_no_retries.model_dump_json())
    assert data_no["retries"] is None
