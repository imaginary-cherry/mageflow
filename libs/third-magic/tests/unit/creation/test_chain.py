from dataclasses import dataclass, field

import pytest
import rapyer

import thirdmagic
from tests.unit.messages import ContextMessage
from thirdmagic.chain import ChainTaskSignature
from thirdmagic.task import TaskSignature


@dataclass
class TaskConfig:
    name: str
    task_kwargs: dict = field(default_factory=dict)
    success_callbacks: list[str] = field(default_factory=list)
    error_callbacks: list[str] = field(default_factory=list)


@pytest.mark.asyncio
async def test__chain_signature_create_save_load__input_output_same__sanity(
    hatchet_mock,
):
    # Arrange
    @hatchet_mock.task(name="test_task_1")
    def test_task_1(msg):
        return msg

    @hatchet_mock.task(name="test_task_2")
    def test_task_2(msg):
        return msg

    # Create individual task signatures
    task1_signature = await thirdmagic.sign(test_task_1, arg1="value1")
    task2_signature = await thirdmagic.sign(test_task_2, arg2="value2")

    kwargs = {"arg1": "test", "arg2": 123}
    tasks = [task1_signature.key, task2_signature.key]

    # Act
    original_chain_signature = ChainTaskSignature(
        task_name="test_chain_task",
        kwargs=kwargs,
        tasks=tasks,
    )
    await original_chain_signature.asave()
    loaded_chain_signature = await rapyer.aget(original_chain_signature.key)

    # Assert
    assert original_chain_signature == loaded_chain_signature


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "task_configs",
    [
        [
            TaskConfig(name="simple_task_0", task_kwargs={"arg": "value_0"}),
            TaskConfig(name="another_task_1", task_kwargs={"param": "param_value_1"}),
        ],
        [
            TaskConfig(name="simple_task_0", task_kwargs={"arg": "value_0"}),
            TaskConfig(name="another_task_1", task_kwargs={"param": "param_value_1"}),
            TaskConfig(name="third_task_2", task_kwargs={"data": "data_value_2"}),
        ],
        [
            TaskConfig(name="existing_success_callback"),
            TaskConfig(name="existing_error_callback"),
            TaskConfig(
                name="task_with_callbacks_0",
                task_kwargs={"callback_arg": "callback_value_0"},
                success_callbacks=["existing_success_task.key"],
                error_callbacks=["existing_error_task.key"],
            ),
        ],
    ],
)
async def test_chain_creation_with_various_task_types_loads_correctly_from_redis_sanity(
    task_configs: list[TaskConfig],
):
    # Arrange
    tasks = []
    for config in task_configs:
        task_signature = await thirdmagic.sign(
            config.name,
            model_validators=ContextMessage,
            success_callbacks=config.success_callbacks,
            error_callbacks=config.error_callbacks,
            **config.task_kwargs,
        )
        tasks.append(task_signature)

    # Act
    chain_signature = await thirdmagic.chain([task.key for task in tasks])

    # Assert
    loaded_chain = await ChainTaskSignature.aget(chain_signature.key)
    assert isinstance(loaded_chain, ChainTaskSignature)
    assert loaded_chain.tasks == [task.key for task in tasks]

    for task in tasks:
        loaded_task = await TaskSignature.aget(task.key)
        assert loaded_task.key == task.key
        assert loaded_task.task_name == task.task_name
        assert loaded_task.signature_container_id == chain_signature.key

        task_success = set(task.success_callbacks)
        loaded_success = set(loaded_task.success_callbacks)
        assert task_success == loaded_success

        task_errors = set(task.error_callbacks)
        loaded_errors = set(loaded_task.error_callbacks)
        assert task_errors == loaded_errors


@pytest.mark.asyncio
async def test_chain_success_callbacks_tasks_linked_via_container_sanity():
    # Arrange
    task1 = await thirdmagic.sign(
        "first_task",
        model_validators=ContextMessage,
        arg1="value1",
    )

    task2 = await thirdmagic.sign(
        "second_task",
        model_validators=ContextMessage,
        arg2="value2",
    )

    task3 = await thirdmagic.sign(
        "third_task",
        model_validators=ContextMessage,
        arg3="value3",
    )

    # Act
    chain_signature = await thirdmagic.chain([task1.key, task2.key, task3.key])

    # Assert
    reloaded_task1 = await TaskSignature.aget(task1.key)
    reloaded_task2 = await TaskSignature.aget(task2.key)
    reloaded_task3 = await TaskSignature.aget(task3.key)

    assert reloaded_task1.signature_container_id == chain_signature.key
    assert reloaded_task2.signature_container_id == chain_signature.key
    assert reloaded_task3.signature_container_id == chain_signature.key

    loaded_chain = await ChainTaskSignature.aget(chain_signature.key)
    assert isinstance(loaded_chain, ChainTaskSignature)
    assert loaded_chain.tasks == [task1.key, task2.key, task3.key]


@pytest.mark.asyncio
async def test_chain_error_handling_via_container_sanity():
    # Arrange
    task1 = await thirdmagic.sign(
        "first_task",
        model_validators=ContextMessage,
        arg1="value1",
    )

    task2 = await thirdmagic.sign(
        "second_task",
        model_validators=ContextMessage,
        arg2="value2",
    )

    # Act
    chain_signature = await thirdmagic.chain([task1.key, task2.key])

    # Assert
    reloaded_task1 = await TaskSignature.aget(task1.key)
    reloaded_task2 = await TaskSignature.aget(task2.key)

    assert reloaded_task1.signature_container_id == chain_signature.key
    assert reloaded_task2.signature_container_id == chain_signature.key


@pytest.mark.asyncio
async def test_chain_with_existing_callbacks_preserves_them_edge_case():
    # Arrange
    # Create existing callback tasks
    existing_success = await thirdmagic.sign(
        "existing_success",
        model_validators=ContextMessage,
    )

    existing_error = await thirdmagic.sign(
        "existing_error",
        model_validators=ContextMessage,
    )

    # Create task with existing callbacks
    task_with_callbacks = await thirdmagic.sign(
        "task_with_existing_callbacks",
        success_callbacks=[existing_success.key],
        error_callbacks=[existing_error.key],
        model_validators=ContextMessage,
        arg="value",
    )

    simple_task = await thirdmagic.sign(
        "simple_task",
        model_validators=ContextMessage,
        param="param_value",
    )

    # Act
    chain_signature = await thirdmagic.chain([task_with_callbacks.key, simple_task.key])

    # Assert
    reloaded_task = await TaskSignature.aget(task_with_callbacks.key)

    assert len(reloaded_task.success_callbacks) == 1
    assert existing_success.key in reloaded_task.success_callbacks
    assert len(reloaded_task.error_callbacks) == 1
    assert existing_error.key in reloaded_task.error_callbacks
    assert reloaded_task.signature_container_id == chain_signature.key
