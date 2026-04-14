from unittest.mock import ANY, AsyncMock

import pytest
import pytest_asyncio
from hatchet_sdk.clients.admin import TriggerWorkflowOptions
from hatchet_sdk.runnables.types import EmptyModel
from thirdmagic.consts import TASK_ID_PARAM_NAME

import mageflow
from mageflow.clients.hatchet.workflow import MageflowWorkflow
from tests.integration.hatchet.models import CommandMessageWithResult, ContextMessage


@pytest.fixture
def mock_run_workflow(hatchet_mock):
    mock = AsyncMock()
    hatchet_mock._client.admin.aio_run_workflow = mock
    return mock


@pytest.fixture
def mock_run_workflow_with_result(mock_run_workflow):
    mock_run_workflow.return_value.aio_result = AsyncMock(return_value={"result": "ok"})
    return mock_run_workflow


class TestAioRunNoWait:
    @pytest_asyncio.fixture
    async def sig(self, orch, mock_task_def):
        return await mageflow.asign("test_task", model_validators=ContextMessage)

    @pytest.mark.asyncio
    async def test_serializes_basemodel_input(self, sig, mock_run_workflow):
        # Arrange
        msg = ContextMessage(base_data={"x": 1})
        expected_input = {"base_data": {"x": 1}, "more_context": {}, "test_ctx": {}}

        # Act
        await sig.aio_run_no_wait(msg)

        # Assert
        mock_run_workflow.assert_awaited_once_with(
            workflow_name="test_task", input=expected_input, options=ANY
        )

    @pytest.mark.asyncio
    async def test_with_signature_kwargs(self, orch, mock_task_def, mock_run_workflow):
        # Arrange
        sig = await mageflow.asign(
            "test_task", model_validators=ContextMessage, pipeline_id="abc"
        )
        msg = ContextMessage(base_data={"x": 1})
        expected_input = {
            "base_data": {"x": 1},
            "more_context": {},
            "test_ctx": {},
            "pipeline_id": "abc",
        }

        # Act
        await sig.aio_run_no_wait(msg)

        # Assert
        mock_run_workflow.assert_awaited_once_with(
            workflow_name="test_task", input=expected_input, options=ANY
        )

    @pytest.mark.asyncio
    async def test_none_msg_uses_empty_model(self, sig, mock_run_workflow):
        # Act
        await sig.aio_run_no_wait(None)

        # Assert
        mock_run_workflow.assert_awaited_once_with(
            workflow_name="test_task", input={}, options=ANY
        )

    @pytest.mark.asyncio
    async def test_injects_task_id_into_options(self, sig, mock_run_workflow):
        # Act
        await sig.aio_run_no_wait(ContextMessage())

        # Assert
        mock_run_workflow.assert_awaited_once()
        options = mock_run_workflow.call_args.kwargs["options"]
        assert options.additional_metadata[TASK_ID_PARAM_NAME] == sig.key

    @pytest.mark.asyncio
    async def test_preserves_explicit_options_metadata(self, sig, mock_run_workflow):
        # Arrange
        options = TriggerWorkflowOptions(additional_metadata={"custom": "val"})

        # Act
        await sig.aio_run_no_wait(ContextMessage(), options=options)

        # Assert
        mock_run_workflow.assert_awaited_once()
        actual_options = mock_run_workflow.call_args.kwargs["options"]
        assert actual_options.additional_metadata["custom"] == "val"
        assert actual_options.additional_metadata[TASK_ID_PARAM_NAME] == sig.key

    @pytest.mark.asyncio
    async def test_workflow_name_matches_task_name(self, sig, mock_run_workflow):
        # Act
        await sig.aio_run_no_wait(ContextMessage())

        # Assert
        mock_run_workflow.assert_awaited_once_with(
            workflow_name="test_task", input=ANY, options=ANY
        )


class TestAioRun:
    @pytest_asyncio.fixture
    async def sig(self, orch, mock_task_def):
        return await mageflow.asign("test_task", model_validators=ContextMessage)

    @pytest.mark.asyncio
    async def test_basic_dispatch(self, sig, mock_run_workflow_with_result):
        # Arrange
        msg = ContextMessage(base_data={"y": 2})
        expected_input = {"base_data": {"y": 2}, "more_context": {}, "test_ctx": {}}

        # Act
        result = await sig.aio_run(msg)

        # Assert
        mock_run_workflow_with_result.assert_awaited_once_with(
            workflow_name="test_task", input=expected_input, options=ANY
        )
        assert result == {"result": "ok"}

    @pytest.mark.asyncio
    async def test_none_msg(self, sig, mock_run_workflow_with_result):
        # Act
        await sig.aio_run(None)

        # Assert
        mock_run_workflow_with_result.assert_awaited_once_with(
            workflow_name="test_task", input={}, options=ANY
        )

    @pytest.mark.asyncio
    async def test_injects_task_id(self, sig, mock_run_workflow_with_result):
        # Act
        await sig.aio_run(ContextMessage())

        # Assert
        mock_run_workflow_with_result.assert_awaited_once()
        options = mock_run_workflow_with_result.call_args.kwargs["options"]
        assert options.additional_metadata[TASK_ID_PARAM_NAME] == sig.key


class TestAcallWithReturnField:
    @pytest.mark.asyncio
    async def test_wraps_input_under_return_field(
        self, orch, mock_task_def, mock_run_workflow
    ):
        # Arrange
        sig = await mageflow.asign(
            "test_task", model_validators=CommandMessageWithResult
        )
        msg = ContextMessage(base_data={"x": 1})
        expected_input = {
            "task_result": {"base_data": {"x": 1}, "test_ctx": {}, "more_context": {}}
        }

        # Act
        await sig.acall(msg, set_return_field=True)

        # Assert
        mock_run_workflow.assert_awaited_once()
        actual_input = mock_run_workflow.call_args.kwargs["input"]
        assert actual_input == expected_input

    @pytest.mark.asyncio
    async def test_return_field_with_kwargs(
        self, orch, mock_task_def, mock_run_workflow
    ):
        # Arrange
        sig = await mageflow.asign(
            "test_task", model_validators=CommandMessageWithResult, extra_k="extra_v"
        )
        msg = ContextMessage(base_data={"x": 1})
        expected_input = {
            "task_result": {"base_data": {"x": 1}, "test_ctx": {}, "more_context": {}},
            "extra_k": "extra_v",
        }

        # Act
        await sig.acall(msg, set_return_field=True)

        # Assert
        mock_run_workflow.assert_awaited_once()
        actual_input = mock_run_workflow.call_args.kwargs["input"]
        assert actual_input == expected_input


class TestSerializeInput:
    @pytest.fixture
    def hatchet_wf(self, hatchet_mock):
        return hatchet_mock.workflow(name="test_wf", input_validator=ContextMessage)

    def test_basemodel_no_return_field(self, hatchet_wf):
        # Arrange
        wf = MageflowWorkflow(hatchet_wf, {}, None)

        # Act
        result = wf._serialize_input(ContextMessage(base_data={"a": 1}))

        # Assert
        assert result == {"base_data": {"a": 1}, "test_ctx": {}, "more_context": {}}

    def test_basemodel_with_return_field(self, hatchet_wf):
        # Arrange
        wf = MageflowWorkflow(hatchet_wf, {}, "task_result")

        # Act
        result = wf._serialize_input(ContextMessage(base_data={"a": 1}))

        # Assert
        assert result == {
            "task_result": {"base_data": {"a": 1}, "test_ctx": {}, "more_context": {}}
        }

    def test_deep_merge_with_kwargs(self, hatchet_wf):
        # Arrange
        wf = MageflowWorkflow(
            hatchet_wf, {"extra": "v", "base_data": {"nested": True}}, None
        )

        # Act
        result = wf._serialize_input(ContextMessage(base_data={"a": 1}))

        # Assert
        assert result["base_data"] == {"a": 1, "nested": True}
        assert result["extra"] == "v"

    def test_dict_input(self, hatchet_wf):
        # Arrange
        wf = MageflowWorkflow(hatchet_wf, {"k2": "v2"}, None)

        # Act
        result = wf._serialize_input({"k1": "v1"})

        # Assert
        assert result == {"k1": "v1", "k2": "v2"}

    def test_empty_model(self, hatchet_wf):
        # Arrange
        wf = MageflowWorkflow(hatchet_wf, {}, None)

        # Act
        result = wf._serialize_input(EmptyModel())

        # Assert
        assert result == {}

    def test_return_field_and_kwargs_combined(self, hatchet_wf):
        # Arrange
        wf = MageflowWorkflow(hatchet_wf, {"meta": "data"}, "task_result")

        # Act
        result = wf._serialize_input(ContextMessage(base_data={"a": 1}))

        # Assert
        assert result == {
            "task_result": {
                "base_data": {"a": 1},
                "test_ctx": {},
                "more_context": {},
            },
            "meta": "data",
        }
