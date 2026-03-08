import pytest

from tests.unit.assertions import assert_tasks_changed_status
from tests.unit.change_status.assertions import assert_resume_signature
from thirdmagic.task import SignatureStatus, TaskSignature


@pytest.mark.asyncio
async def test__safe_change_status__signature_deleted_from_redis__raises_error__edge_case(
    hatchet_mock, redis_client, hatchet_client_adapter
):
    # Arrange
    @hatchet_mock.task(name="test_task")
    def test_task(msg):
        return msg

    signature = await TaskSignature.from_task(test_task)
    task_id = signature.key

    # Delete signature from Redis directly
    await redis_client.delete(signature.key)

    # Act & Assert
    await TaskSignature.safe_change_status(task_id, SignatureStatus.ACTIVE)
    keys = await redis_client.keys()
    assert len(keys) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ["initial_status", "last_status"],
    [
        [SignatureStatus.SUSPENDED, SignatureStatus.ACTIVE],
        [SignatureStatus.SUSPENDED, SignatureStatus.PENDING],
        [SignatureStatus.CANCELED, SignatureStatus.ACTIVE],
        [SignatureStatus.CANCELED, SignatureStatus.PENDING],
    ],
)
async def test_signature_resume_with_various_statuses_sanity(
    hatchet_client_adapter,
    hatchet_mock,
    initial_status,
    last_status,
):
    # Arrange
    @hatchet_mock.task(name="test_task")
    def test_task(msg):
        return msg

    hatchet_client_adapter.extract_validator.return_value = None
    signature = await TaskSignature.from_task(test_task)
    signature.task_status.status = initial_status
    signature.task_status.last_status = last_status
    await signature.asave()

    # Act
    await signature.resume()

    # Assert
    if last_status == SignatureStatus.ACTIVE:
        assert_resume_signature(signature, hatchet_client_adapter)
        last_status = SignatureStatus.PENDING
    else:
        hatchet_client_adapter.assert_not_called()
    await assert_tasks_changed_status([signature.key], last_status, initial_status)
