import pytest

from orchestrator import TaskSignature
from orchestrator.hatchet.config import orchestrator_config
from tests.unit.hatchet.conftest import assert_redis_keys_do_not_contain_sub_task_ids


@pytest.mark.asyncio
async def test__await_task__stored_in_redis__sanity(redis_client, hatchet_mock):
    # Arrange
    orchestrator_config.redis_client = redis_client

    @hatchet_mock.task(name="test_task")
    def test_task(msg):
        return msg

    # Act
    task = await TaskSignature.from_task(test_task)

    # Assert
    assert await redis_client.exists(task.id)


@pytest.mark.asyncio
async def test__signature_create_save_load__input_output_same__sanity(
    redis_client, hatchet_mock
):
    # Arrange
    orchestrator_config.redis_client = redis_client

    @hatchet_mock.task(name="test_task")
    def test_task(msg):
        return msg

    workflow_params = {"param1": "value1", "param2": "value2"}
    kwargs = {"arg1": "test", "arg2": 123}

    # Act
    original_signature = await TaskSignature.from_task(
        test_task, workflow_params=workflow_params, **kwargs
    )
    loaded_signature = await TaskSignature.from_id(original_signature.id)

    # Assert
    assert original_signature == loaded_signature


@pytest.mark.asyncio
async def test__from_signature__create_signature_from_existing__all_data_same_except_pk__sanity(
    redis_client, hatchet_mock
):
    # Arrange
    orchestrator_config.redis_client = redis_client

    @hatchet_mock.task(name="test_task")
    def test_task(msg):
        return msg

    workflow_params = {"param1": "value1", "param2": "value2"}
    kwargs = {"arg1": "test", "arg2": 123}
    success_callbacks = ["callback1", "callback2"]
    error_callbacks = ["error_callback1"]

    original_signature = await TaskSignature.from_task(
        test_task,
        workflow_params=workflow_params,
        success_callbacks=success_callbacks,
        error_callbacks=error_callbacks,
        **kwargs
    )

    # Act
    new_signature = TaskSignature.from_signature(original_signature)

    # Assert
    original_data = original_signature.model_dump(exclude={"pk"})
    new_data = new_signature.model_dump(exclude={"pk"})
    assert original_data == new_data
    assert new_signature.pk != original_signature.pk


@pytest.mark.asyncio
async def test__add_callbacks__signature_deleted__returns_false_not_found_error(
    redis_client, hatchet_mock
):
    # Arrange
    orchestrator_config.redis_client = redis_client

    @hatchet_mock.task(name="test_task")
    def test_task(msg):
        return msg

    @hatchet_mock.task(name="callback_task")
    def callback_task(msg):
        return msg

    signature = await TaskSignature.from_task(test_task)
    callback_signature = await TaskSignature.from_task(callback_task)
    await signature.remove()

    # Mock the update method to raise NotFoundError simulating a deleted signature
    # Act
    result = await signature.add_callbacks(success=[callback_signature])

    # Assert
    assert result is False
    await assert_redis_keys_do_not_contain_sub_task_ids(redis_client, [signature.id])
