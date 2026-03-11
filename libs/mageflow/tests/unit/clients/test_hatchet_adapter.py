from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from hatchet_sdk import Context, NonRetryableException
from hatchet_sdk.clients.admin import TriggerWorkflowOptions
from thirdmagic.consts import TASK_ID_PARAM_NAME
from thirdmagic.swarm.model import SwarmConfig
from thirdmagic.task_def import MageflowTaskDefinition

import mageflow
from mageflow.chain.messages import ChainCallbackMessage, ChainErrorMessage
from mageflow.clients.hatchet.adapter import HatchetClientAdapter
from mageflow.clients.hatchet.workflow import MageflowWorkflow
from mageflow.swarm.messages import (
    FillSwarmMessage,
    SwarmErrorMessage,
    SwarmResultsMessage,
)
from tests.integration.hatchet.models import CommandMessageWithResult, ContextMessage


@pytest.fixture
def adapter(hatchet_mock):
    return HatchetClientAdapter(hatchet_mock)


@pytest.fixture
def mock_run_workflow(hatchet_mock):
    mock = AsyncMock()
    hatchet_mock._client.admin.aio_run_workflow = mock
    return mock


@pytest.fixture
def mock_hatchet():
    mock = MagicMock()
    mock.stubs.task.return_value.aio_run_no_wait = AsyncMock()
    return mock


@pytest.fixture
def mock_adapter(mock_hatchet):
    return HatchetClientAdapter(mock_hatchet)


@pytest.fixture
def captured_workflows(mock_run_workflow):
    instances = []
    original_init = MageflowWorkflow.__init__

    def capturing_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        instances.append(self)

    with patch.object(MageflowWorkflow, "__init__", capturing_init):
        yield instances


def test_serialize_input_deep_merge_nested_dicts(hatchet_mock):
    # Arrange
    workflow = hatchet_mock.workflow(name="test_wf", input_validator=ContextMessage)
    wf = MageflowWorkflow(workflow, {"a": {"c": 2}}, None)

    # Act
    result = wf._serialize_input({"a": {"b": 1}})

    # Assert
    assert result == {"a": {"b": 1, "c": 2}}


# --- acall_signature ---


@pytest.mark.asyncio
async def test_acall_signature_workflow_has_correct_params(
    adapter, captured_workflows, mock_task_def
):
    # Arrange
    sig = await mageflow.asign("test_task", model_validators=ContextMessage)

    # Act
    await adapter.acall_signature(
        sig, ContextMessage(), set_return_field=True, extra_k="extra_v"
    )

    # Assert
    wf = captured_workflows[0]
    assert wf._mageflow_workflow_params == {"extra_k": "extra_v"}


@pytest.mark.asyncio
async def test_acall_signature_set_return_field_true(
    adapter, captured_workflows, mock_task_def
):
    # Arrange
    sig = await mageflow.asign("test_task", model_validators=CommandMessageWithResult)

    # Act
    await adapter.acall_signature(sig, ContextMessage(), set_return_field=True)

    # Assert
    wf = captured_workflows[0]
    assert wf._return_value_field == "task_result"


@pytest.mark.asyncio
async def test_acall_signature_called_with_msg_and_options(
    adapter, mock_run_workflow, mock_task_def
):
    # Arrange
    sig = await mageflow.asign("test_task", model_validators=ContextMessage)
    msg = ContextMessage(base_data={"x": 1})

    # Act
    await adapter.acall_signature(sig, msg, set_return_field=False)

    # Assert
    call_kwargs = mock_run_workflow.call_args.kwargs
    assert call_kwargs["input"]["base_data"] == {"x": 1}
    assert TASK_ID_PARAM_NAME in call_kwargs["options"].additional_metadata


@pytest.mark.asyncio
async def test_acall_signature_msg_none_replaced_with_empty_model(
    adapter, mock_run_workflow, mock_task_def
):
    # Arrange
    sig = await mageflow.asign("test_task", model_validators=ContextMessage)

    # Act
    await adapter.acall_signature(sig, None, set_return_field=False)

    # Assert
    serialized = mock_run_workflow.call_args.kwargs["input"]
    assert serialized == {}


# --- await_signature ---


@pytest.fixture
def mock_aio_run():
    with patch.object(MageflowWorkflow, "aio_run", new_callable=AsyncMock) as mock:
        yield mock


@pytest.mark.asyncio
async def test_await_signature_workflow_has_correct_params(
    adapter, captured_workflows, mock_aio_run, mock_task_def
):
    # Arrange
    sig = await mageflow.asign("test_task", model_validators=ContextMessage)

    # Act
    await adapter.await_signature(
        sig, ContextMessage(), set_return_field=True, extra_k="extra_v"
    )

    # Assert
    wf = captured_workflows[0]
    assert wf._mageflow_workflow_params == {"extra_k": "extra_v"}


@pytest.mark.asyncio
async def test_await_signature_set_return_field_true(
    adapter, captured_workflows, mock_aio_run, mock_task_def
):
    # Arrange
    sig = await mageflow.asign("test_task", model_validators=CommandMessageWithResult)

    # Act
    await adapter.await_signature(sig, ContextMessage(), set_return_field=True)

    # Assert
    wf = captured_workflows[0]
    assert wf._return_value_field == "task_result"


@pytest.mark.asyncio
async def test_await_signature_called_with_msg_and_options(
    adapter, mock_aio_run, mock_task_def
):
    # Arrange
    sig = await mageflow.asign("test_task", model_validators=ContextMessage)
    msg = ContextMessage(base_data={"x": 1})

    # Act
    await adapter.await_signature(sig, msg, set_return_field=False)

    # Assert
    call_args, call_kwargs = mock_aio_run.call_args
    serialized_msg = call_args[0]
    options = call_args[1]
    assert serialized_msg.base_data == {"x": 1}
    assert TASK_ID_PARAM_NAME in options.additional_metadata


@pytest.mark.asyncio
async def test_await_signature_msg_none_replaced_with_empty_model(
    adapter, mock_aio_run, mock_task_def
):
    # Arrange
    sig = await mageflow.asign("test_task", model_validators=ContextMessage)

    # Act
    await adapter.await_signature(sig, None, set_return_field=False)

    # Assert
    call_args, _ = mock_aio_run.call_args
    serialized_msg = call_args[0]
    assert serialized_msg.__class__.__name__ == "EmptyModel"


# --- acall_chain_done ---


@pytest.mark.asyncio
async def test_acall_chain_done_serialized_input(
    mock_adapter, mock_hatchet, mock_task_def
):
    # Arrange
    tasks = [
        await mageflow.asign(f"chain_task_{i}", model_validators=ContextMessage)
        for i in range(2)
    ]
    chain = await mageflow.achain([t.key for t in tasks])
    results = {"result_key": "result_val"}

    # Act
    await mock_adapter.acall_chain_done(results, chain)

    # Assert
    mock_hatchet.stubs.task.return_value.aio_run_no_wait.assert_awaited_once_with(
        ChainCallbackMessage(chain_results=results, chain_task_id=chain.key)
    )


# --- acall_chain_error ---


@pytest.mark.asyncio
async def test_acall_chain_error_serialized_input(
    mock_adapter, mock_hatchet, mock_task_def
):
    # Arrange
    tasks = [
        await mageflow.asign(f"chain_err_{i}", model_validators=ContextMessage)
        for i in range(2)
    ]
    chain = await mageflow.achain([t.key for t in tasks])
    error = ValueError("boom")
    original_msg = {"orig": "msg"}

    # Act
    await mock_adapter.acall_chain_error(original_msg, error, chain, tasks[0])

    # Assert
    mock_hatchet.stubs.task.return_value.aio_run_no_wait.assert_awaited_once_with(
        ChainErrorMessage(
            chain_task_id=chain.key,
            error="boom",
            original_msg=original_msg,
            error_task_key=tasks[0].key,
        )
    )


# --- afill_swarm ---


@pytest_asyncio.fixture
async def swarm_sig(mock_task_def):
    return await mageflow.aswarm(
        "test_swarm",
        model_validators=ContextMessage,
        config=SwarmConfig(max_concurrency=2),
    )


@pytest.mark.asyncio
async def test_afill_swarm_message_fields(mock_adapter, mock_hatchet, swarm_sig):
    # Arrange
    swarm = swarm_sig

    # Act
    await mock_adapter.afill_swarm(swarm, max_tasks=5)

    # Assert
    mock_hatchet.stubs.task.return_value.aio_run_no_wait.assert_awaited_once_with(
        FillSwarmMessage(swarm_task_id=swarm.key, max_tasks=5)
    )


@pytest.mark.asyncio
async def test_afill_swarm_forwards_options(mock_adapter, mock_hatchet, swarm_sig):
    # Arrange
    options = TriggerWorkflowOptions(additional_metadata={"custom": "opt"})

    # Act
    await mock_adapter.afill_swarm(swarm_sig, options=options)

    # Assert
    mock_hatchet.stubs.task.return_value.aio_run_no_wait.assert_awaited_once_with(
        FillSwarmMessage(swarm_task_id=swarm_sig.key, max_tasks=None),
        options=options,
    )


# --- acall_swarm_item_done ---


@pytest.mark.asyncio
async def test_acall_swarm_item_done_message_fields(
    mock_adapter, mock_hatchet, swarm_sig, mock_task_def
):
    # Arrange
    item = await mageflow.asign("swarm_item", model_validators=ContextMessage)
    results = [1, 2, 3]

    # Act
    await mock_adapter.acall_swarm_item_done(results, swarm_sig, item)

    # Assert
    mock_hatchet.stubs.task.return_value.aio_run_no_wait.assert_awaited_once_with(
        SwarmResultsMessage(
            swarm_task_id=swarm_sig.key,
            swarm_item_id=item.key,
            mageflow_results=results,
        )
    )


# --- acall_swarm_item_error ---


@pytest.mark.asyncio
async def test_acall_swarm_item_error_message_fields(
    mock_adapter, mock_hatchet, swarm_sig, mock_task_def
):
    # Arrange
    item = await mageflow.asign("swarm_item", model_validators=ContextMessage)
    error = RuntimeError("oops")

    # Act
    await mock_adapter.acall_swarm_item_error(error, swarm_sig, item)

    # Assert
    mock_hatchet.stubs.task.return_value.aio_run_no_wait.assert_awaited_once_with(
        SwarmErrorMessage(
            swarm_task_id=swarm_sig.key,
            swarm_item_id=item.key,
            error="oops",
        )
    )


# --- extract_validator ---


@pytest.fixture
def hatchet_task(hatchet_mock):
    @hatchet_mock.task(name="my_workflow", input_validator=ContextMessage, retries=5)
    async def my_task(input: ContextMessage, ctx: Context):
        pass

    return my_task


def test_extract_validator_returns_inner_type(adapter, hatchet_task):
    # Act
    result = adapter.extract_validator(hatchet_task)

    # Assert
    assert result is ContextMessage


# --- extract_retries ---


def test_extract_retries_returns_task_retries(adapter, hatchet_task):
    # Act
    result = adapter.extract_retries(hatchet_task)

    # Assert
    assert result == 5


# --- should_task_retry ---


@pytest.mark.parametrize(
    ["retries", "attempt_num", "exception_class", "expected"],
    [
        (3, 1, ValueError, True),
        (3, 4, ValueError, False),
        (3, 1, NonRetryableException, False),
        (None, 1, ValueError, False),
        (0, 1, ValueError, False),
    ],
    ids=[
        "normal-retry",
        "exhausted",
        "non-retryable",
        "no-retries-configured",
        "zero-retries",
    ],
)
def test_should_task_retry(adapter, retries, attempt_num, exception_class, expected):
    # Arrange
    task_def = MageflowTaskDefinition(
        mageflow_task_name="t", task_name="t", retries=retries
    )
    exc = exception_class("err")

    # Act
    result = adapter.should_task_retry(task_def, attempt_num, exc)

    # Assert
    assert result is expected


# --- task_name ---


def test_task_name_returns_task_name(adapter, hatchet_task):
    # Act
    result = adapter.task_name(hatchet_task)

    # Assert
    assert result == "my_workflow"
