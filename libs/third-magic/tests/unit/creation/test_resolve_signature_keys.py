import pytest
from rapyer.fields import RapyerKey

import thirdmagic
from tests.unit.messages import ContextMessage
from thirdmagic.signature.creator import resolve_signatures
from thirdmagic.signature.model import TaskSignature


@pytest.fixture
def hatchet_tasks(hatchet_mock):
    tasks = []
    for i in range(3):

        @hatchet_mock.task(name=f"test_task_{i}", input_validator=ContextMessage)
        def task_fn(msg):
            return msg

        tasks.append(task_fn)
    return tasks


@pytest.mark.asyncio
async def test__resolve_signature_keys__all_task_signatures__returns_as_is():
    # Arrange
    sigs = [
        await thirdmagic.sign(f"task_{i}", model_validators=ContextMessage)
        for i in range(3)
    ]

    # Act
    result = await resolve_signatures(sigs)

    # Assert
    assert result == sigs


@pytest.mark.asyncio
async def test__resolve_signature_keys__all_string_keys__batch_fetches():
    # Arrange
    sigs = [
        await thirdmagic.sign(f"task_{i}", model_validators=ContextMessage)
        for i in range(3)
    ]
    keys = [sig.key for sig in sigs]

    # Act
    result = await resolve_signatures(keys)

    # Assert
    assert [r.key for r in result] == keys
    for original, resolved in zip(sigs, result):
        assert original.task_name == resolved.task_name


@pytest.mark.asyncio
async def test__resolve_signature_keys__all_hatchet_tasks__batch_creates(hatchet_tasks):
    # Act
    result = await resolve_signatures(hatchet_tasks)

    # Assert
    assert len(result) == 3
    for i, sig in enumerate(result):
        assert isinstance(sig, TaskSignature)
        assert sig.task_name == f"test_task_{i}"
        assert await TaskSignature.get_safe(sig.key) is not None


@pytest.mark.asyncio
async def test__resolve_signature_keys__mixed_types__preserves_order(hatchet_tasks):
    # Arrange
    existing_sig = await thirdmagic.sign(
        "existing_task", model_validators=ContextMessage
    )
    pre_saved = await thirdmagic.sign("pre_saved_task", model_validators=ContextMessage)
    hatchet_task = hatchet_tasks[0]

    inputs = [existing_sig, pre_saved.key, hatchet_task]

    # Act
    result = await resolve_signatures(inputs)

    # Assert
    assert len(result) == 3
    assert result[0] is existing_sig
    assert result[1].key == pre_saved.key
    assert result[2].task_name == "test_task_0"


@pytest.mark.asyncio
async def test__resolve_signature_keys__missing_string_keys__returns_none():
    # Arrange
    existing = await thirdmagic.sign("existing_task", model_validators=ContextMessage)
    missing_key = RapyerKey("TaskSignature:nonexistent_key")
    inputs = [existing.key, missing_key]

    # Act
    result = await resolve_signatures(inputs)

    # Assert
    assert result[0].key == existing.key
    assert result[1] is None


@pytest.mark.asyncio
async def test__resolve_signature_keys__empty_list__returns_empty():
    # Act
    result = await resolve_signatures([])

    # Assert
    assert result == []
