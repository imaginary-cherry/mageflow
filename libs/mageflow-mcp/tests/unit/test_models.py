import json
from datetime import datetime, timezone

from mageflow_mcp.models import (
    ContainerSummary,
    ErrorResponse,
    LogEntry,
    SignatureInfo,
    SubTaskInfo,
    TaskDefinitionInfo,
)
from thirdmagic.signature.status import SignatureStatus


def test__error_response__serializes_to_valid_json() -> None:
    """ErrorResponse should serialize all fields to valid JSON."""
    err = ErrorResponse(
        error="key_not_found",
        message="The requested key does not exist or has expired.",
        suggestion="Use list_signatures to browse available signature IDs.",
    )
    raw = err.model_dump_json()
    data = json.loads(raw)
    assert isinstance(data, dict)
    assert data["error"] == "key_not_found"
    assert data["message"] == "The requested key does not exist or has expired."
    assert (
        data["suggestion"] == "Use list_signatures to browse available signature IDs."
    )


def test__signature_info__serializes_to_valid_json() -> None:
    """SignatureInfo with all fields should produce valid JSON with status as string."""
    sig = SignatureInfo(
        key="task:abc123",
        signature_type="TaskSignature",
        task_name="my_task",
        status=SignatureStatus.ACTIVE,
        creation_time=datetime(2026, 2, 23, 12, 0, 0, tzinfo=timezone.utc),
        kwargs={"input": "hello"},
        worker_task_id="worker-task-001",
    )
    raw = sig.model_dump_json()
    data = json.loads(raw)
    assert isinstance(data, dict)
    assert data["key"] == "task:abc123"
    assert data["signature_type"] == "TaskSignature"
    assert data["task_name"] == "my_task"
    assert data["status"] == "active"
    assert data["kwargs"] == {"input": "hello"}
    assert data["worker_task_id"] == "worker-task-001"


def test__signature_info__optional_worker_task_id_defaults_to_none() -> None:
    """SignatureInfo created without worker_task_id should serialize it as null."""
    sig = SignatureInfo(
        key="task:def456",
        signature_type="ChainTaskSignature",
        task_name="chain_step",
        status=SignatureStatus.PENDING,
        creation_time=datetime(2026, 2, 23, 9, 0, 0, tzinfo=timezone.utc),
        kwargs={},
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


# ── Additional edge case tests ──────────────────────────────────────────


def test__error_response__with_empty_strings() -> None:
    """ErrorResponse should handle empty strings for all fields."""
    err = ErrorResponse(error="", message="", suggestion="")
    data = json.loads(err.model_dump_json())
    assert data["error"] == ""
    assert data["message"] == ""
    assert data["suggestion"] == ""


def test__error_response__with_special_characters() -> None:
    """ErrorResponse should properly serialize special characters."""
    err = ErrorResponse(
        error="key_not_found",
        message='Task "test:123" with \n newline and \t tab',
        suggestion="Use list_signatures() with 'status' filter",
    )
    data = json.loads(err.model_dump_json())
    assert '"test:123"' in data["message"]
    assert "newline" in data["message"]


def test__signature_info__with_empty_kwargs() -> None:
    """SignatureInfo should handle empty kwargs dict."""
    sig = SignatureInfo(
        key="task:empty",
        signature_type="TaskSignature",
        task_name="empty_task",
        status=SignatureStatus.PENDING,
        creation_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        kwargs={},
    )
    data = json.loads(sig.model_dump_json())
    assert data["kwargs"] == {}


def test__signature_info__with_complex_nested_kwargs() -> None:
    """SignatureInfo should serialize complex nested kwargs."""
    sig = SignatureInfo(
        key="task:complex",
        signature_type="TaskSignature",
        task_name="complex_task",
        status=SignatureStatus.ACTIVE,
        creation_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        kwargs={
            "nested": {"level1": {"level2": [1, 2, 3]}},
            "list": ["a", "b", "c"],
            "number": 42.5,
            "boolean": True,
            "null": None,
        },
    )
    data = json.loads(sig.model_dump_json())
    assert data["kwargs"]["nested"]["level1"]["level2"] == [1, 2, 3]
    assert data["kwargs"]["boolean"] is True
    assert data["kwargs"]["null"] is None


def test__signature_info__with_very_long_key() -> None:
    """SignatureInfo should handle very long key strings."""
    long_key = "TaskSignature:" + "x" * 500
    sig = SignatureInfo(
        key=long_key,
        signature_type="TaskSignature",
        task_name="test",
        status=SignatureStatus.PENDING,
        creation_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        kwargs={},
    )
    data = json.loads(sig.model_dump_json())
    assert len(data["key"]) > 500
    assert data["key"] == long_key


def test__container_summary__with_all_zero_counts() -> None:
    """ContainerSummary should handle all zero status counts."""
    summary = ContainerSummary(
        container_key="chain:empty",
        signature_type="ChainTaskSignature",
        total=0,
        pending=0,
        active=0,
        done=0,
        failed=0,
        suspended=0,
        canceled=0,
    )
    data = json.loads(summary.model_dump_json())
    assert data["total"] == 0
    assert sum([data[k] for k in ["pending", "active", "done", "failed", "suspended", "canceled"]]) == 0


def test__container_summary__with_very_large_counts() -> None:
    """ContainerSummary should handle very large task counts."""
    summary = ContainerSummary(
        container_key="chain:huge",
        signature_type="SwarmTaskSignature",
        total=1000000,
        pending=100000,
        active=200000,
        done=500000,
        failed=150000,
        suspended=25000,
        canceled=25000,
    )
    data = json.loads(summary.model_dump_json())
    assert data["total"] == 1000000
    assert data["done"] == 500000


def test__log_entry__with_all_optional_fields() -> None:
    """LogEntry should handle all optional fields populated."""
    entry = LogEntry(
        line="Test log line",
        timestamp=datetime(2026, 3, 7, 10, 30, 45, tzinfo=timezone.utc),
        level="INFO",
        sub_task_id="subtask:123",
    )
    data = json.loads(entry.model_dump_json())
    assert data["line"] == "Test log line"
    assert data["level"] == "INFO"
    assert data["sub_task_id"] == "subtask:123"
    assert data["timestamp"] is not None


def test__log_entry__with_multiline_content() -> None:
    """LogEntry should handle multiline log content."""
    entry = LogEntry(
        line="Line 1\nLine 2\nLine 3",
        level="ERROR",
    )
    data = json.loads(entry.model_dump_json())
    assert "Line 1" in data["line"]
    assert "Line 2" in data["line"]
    assert "Line 3" in data["line"]


def test__log_entry__with_unicode_characters() -> None:
    """LogEntry should handle unicode characters in log lines."""
    entry = LogEntry(
        line="Task completed successfully ✓ with émojis 🎉 and special chars: ñ, ü, ö",
    )
    data = json.loads(entry.model_dump_json())
    assert "✓" in data["line"]
    assert "🎉" in data["line"]
    assert "ñ" in data["line"]


def test__task_definition_info__with_zero_retries() -> None:
    """TaskDefinitionInfo should distinguish between None and 0 retries."""
    defn_zero_retries = TaskDefinitionInfo(
        mageflow_task_name="no_retry_task",
        task_name="NoRetryTask",
        retries=0,
    )
    data = json.loads(defn_zero_retries.model_dump_json())
    assert data["retries"] == 0
    assert data["retries"] is not None


def test__signature_info__all_status_types() -> None:
    """SignatureInfo should correctly serialize all status enum values."""
    statuses = [
        SignatureStatus.PENDING,
        SignatureStatus.ACTIVE,
        SignatureStatus.DONE,
        SignatureStatus.FAILED,
        SignatureStatus.SUSPENDED,
        SignatureStatus.CANCELED,
    ]
    expected_strings = ["pending", "active", "done", "failed", "suspended", "canceled"]

    for status, expected_str in zip(statuses, expected_strings):
        sig = SignatureInfo(
            key=f"task:{expected_str}",
            signature_type="TaskSignature",
            task_name=f"task_{expected_str}",
            status=status,
            creation_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
            kwargs={},
        )
        data = json.loads(sig.model_dump_json())
        assert data["status"] == expected_str


# ── Tests for SignatureInfo.from_sig class method ──────────────────────


def test__signature_info__from_sig_with_task_signature() -> None:
    """SignatureInfo.from_sig should correctly convert a TaskSignature."""
    from unittest.mock import MagicMock
    from thirdmagic.task import TaskSignature as ThirdmagicTaskSignature

    mock_sig = MagicMock(spec=ThirdmagicTaskSignature)
    mock_sig.key = "TaskSignature:abc123"
    mock_sig.task_name = "test_task"
    mock_sig.task_status.status = SignatureStatus.PENDING
    mock_sig.creation_time = datetime(2026, 3, 7, tzinfo=timezone.utc)
    mock_sig.kwargs = {"arg1": "value1"}
    mock_sig.worker_task_id = "worker-123"
    # Set the class name properly for type() to work
    type(mock_sig).__name__ = "TaskSignature"

    result = SignatureInfo.from_sig(mock_sig)

    assert result.key == "TaskSignature:abc123"
    assert result.signature_type == "TaskSignature"
    assert result.task_name == "test_task"
    assert result.status == SignatureStatus.PENDING
    assert result.kwargs == {"arg1": "value1"}
    assert result.worker_task_id == "worker-123"


def test__signature_info__from_sig_with_chain_signature() -> None:
    """SignatureInfo.from_sig should correctly convert a ChainTaskSignature."""
    from unittest.mock import MagicMock
    from thirdmagic.chain.model import ChainTaskSignature

    mock_sig = MagicMock(spec=ChainTaskSignature)
    mock_sig.key = "ChainTaskSignature:chain001"
    mock_sig.task_name = "test_chain"
    mock_sig.task_status.status = SignatureStatus.ACTIVE
    mock_sig.creation_time = datetime(2026, 3, 7, tzinfo=timezone.utc)
    mock_sig.kwargs = {"chain_arg": "value"}
    # Set the class name properly for type() to work
    type(mock_sig).__name__ = "ChainTaskSignature"

    result = SignatureInfo.from_sig(mock_sig)

    assert result.signature_type == "ChainTaskSignature"
    assert result.task_name == "test_chain"
    assert result.status == SignatureStatus.ACTIVE
    assert result.worker_task_id is None  # Chains don't have worker_task_id


def test__signature_info__from_sig_with_swarm_signature() -> None:
    """SignatureInfo.from_sig should correctly convert a SwarmTaskSignature."""
    from unittest.mock import MagicMock
    from thirdmagic.swarm.model import SwarmTaskSignature

    mock_sig = MagicMock(spec=SwarmTaskSignature)
    mock_sig.key = "SwarmTaskSignature:swarm001"
    mock_sig.task_name = "test_swarm"
    mock_sig.task_status.status = SignatureStatus.DONE
    mock_sig.creation_time = datetime(2026, 3, 7, tzinfo=timezone.utc)
    mock_sig.kwargs = {"items": [1, 2, 3]}
    # Set the class name properly for type() to work
    type(mock_sig).__name__ = "SwarmTaskSignature"

    result = SignatureInfo.from_sig(mock_sig)

    assert result.signature_type == "SwarmTaskSignature"
    assert result.task_name == "test_swarm"
    assert result.status == SignatureStatus.DONE
    assert result.worker_task_id is None  # Swarms don't have worker_task_id


def test__signature_info__from_sig_preserves_empty_kwargs() -> None:
    """SignatureInfo.from_sig should preserve empty kwargs dict."""
    from unittest.mock import MagicMock

    mock_sig = MagicMock()
    mock_sig.key = "TaskSignature:empty"
    mock_sig.task_name = "empty_task"
    mock_sig.task_status.status = SignatureStatus.PENDING
    mock_sig.creation_time = datetime(2026, 3, 7, tzinfo=timezone.utc)
    mock_sig.kwargs = {}
    mock_sig.worker_task_id = None
    type(mock_sig).__name__ = "TaskSignature"

    result = SignatureInfo.from_sig(mock_sig)

    assert result.kwargs == {}


def test__signature_info__from_sig_handles_complex_kwargs() -> None:
    """SignatureInfo.from_sig should handle complex nested kwargs."""
    from unittest.mock import MagicMock

    complex_kwargs = {
        "nested": {"level1": {"level2": {"level3": "deep"}}},
        "list_data": [1, 2, {"inner": "value"}],
        "mixed": [True, None, 42, "text"],
    }

    mock_sig = MagicMock()
    mock_sig.key = "TaskSignature:complex"
    mock_sig.task_name = "complex_task"
    mock_sig.task_status.status = SignatureStatus.ACTIVE
    mock_sig.creation_time = datetime(2026, 3, 7, tzinfo=timezone.utc)
    mock_sig.kwargs = complex_kwargs
    mock_sig.worker_task_id = "worker-complex"
    type(mock_sig).__name__ = "TaskSignature"

    result = SignatureInfo.from_sig(mock_sig)

    assert result.kwargs == complex_kwargs
    assert result.kwargs["nested"]["level1"]["level2"]["level3"] == "deep"