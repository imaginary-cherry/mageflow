from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from hatchet_sdk import Context
from thirdmagic.consts import TASK_ID_PARAM_NAME
from thirdmagic.signature import Signature
from thirdmagic.signature.status import SignatureStatus

import mageflow
from tests.integration.hatchet.models import ContextMessage


@pytest.fixture
def mage_workflow(orch):
    return orch.workflow(name="test-wf", input_validator=ContextMessage)


@pytest.fixture
def mock_activate_success_on_signature():
    with patch.object(
        Signature, "activate_success", new_callable=AsyncMock
    ) as mock:
        yield mock


@pytest.fixture
def mock_activate_error_on_signature():
    with patch.object(
        Signature, "activate_error", new_callable=AsyncMock
    ) as mock:
        yield mock


@pytest.fixture
def user_success_spy(mage_workflow):
    spy = AsyncMock(return_value=None)

    @mage_workflow.on_success_task()
    async def user_on_success(msg, ctx: Context):
        await spy(msg, ctx)

    return spy


@pytest.fixture
def user_failure_spy(mage_workflow):
    spy = AsyncMock(return_value=None)

    @mage_workflow.on_failure_task()
    async def user_on_failure(msg, ctx: Context):
        await spy(msg, ctx)

    return spy


@pytest_asyncio.fixture
async def live_task_signature(mock_task_def):
    """Create a real TaskSignature persisted in fakeredis."""
    signature = await mageflow.asign(
        "hook_idem_task", model_validators=ContextMessage
    )
    return signature


async def run_on_success(mage_workflow, msg, task_id):
    return await mage_workflow._on_success_task.aio_mock_run(
        input=msg,
        additional_metadata={TASK_ID_PARAM_NAME: task_id},
    )


async def run_on_failure(mage_workflow, msg, task_id):
    return await mage_workflow._on_failure_task.aio_mock_run(
        input=msg,
        additional_metadata={TASK_ID_PARAM_NAME: task_id},
    )


class TestOnSuccessHookIdempotent:
    @pytest.mark.asyncio
    async def test_on_success__signature_deleted__user_callback_still_runs(
        self,
        mage_workflow,
        adapter_with_lifecycle,
        user_success_spy,
        live_task_signature,
        mock_activate_success_on_signature,
    ):
        # Arrange: simulate "signature already processed and removed"
        task_id = live_task_signature.key
        await live_task_signature.adelete()
        msg = ContextMessage(base_data={"k": "v"})

        # Act
        await run_on_success(mage_workflow, msg, task_id)

        # Assert: user callback ran, no mageflow activation because lifecycle is vanilla
        user_success_spy.assert_awaited_once()
        call_msg, call_ctx = user_success_spy.call_args.args
        assert call_msg == msg
        mock_activate_success_on_signature.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_on_success__signature_done__user_callback_still_runs_and_activation_skipped(
        self,
        mage_workflow,
        adapter_with_lifecycle,
        user_success_spy,
        live_task_signature,
        mock_activate_success_on_signature,
    ):
        # Arrange: signature exists but is already marked DONE (second hook fire)
        await live_task_signature.task_status.aupdate(status=SignatureStatus.DONE)
        msg = ContextMessage()

        # Act
        await run_on_success(mage_workflow, msg, live_task_signature.key)

        # Assert: user callback ran, activate_success skipped due to is_done() guard
        user_success_spy.assert_awaited_once()
        mock_activate_success_on_signature.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_on_success__runs_twice__user_callback_runs_both_times_activation_once(
        self,
        mage_workflow,
        adapter_with_lifecycle,
        user_success_spy,
        live_task_signature,
        mock_activate_success_on_signature,
    ):
        # Arrange: active signature, hook fires twice in a row
        msg = ContextMessage()

        # Act
        await run_on_success(mage_workflow, msg, live_task_signature.key)
        await run_on_success(mage_workflow, msg, live_task_signature.key)

        # Assert: user callback ran on both invocations; mageflow activated once
        assert user_success_spy.await_count == 2
        assert mock_activate_success_on_signature.await_count == 1


class TestOnFailureHookIdempotent:
    @pytest.mark.asyncio
    async def test_on_failure__signature_deleted__user_callback_still_runs(
        self,
        mage_workflow,
        adapter_with_lifecycle,
        user_failure_spy,
        live_task_signature,
        mock_activate_error_on_signature,
    ):
        # Arrange: simulate "signature already processed and removed"
        task_id = live_task_signature.key
        await live_task_signature.adelete()
        msg = ContextMessage(base_data={"k": "v"})

        # Act
        await run_on_failure(mage_workflow, msg, task_id)

        # Assert: user callback ran, no mageflow activation because lifecycle is vanilla
        user_failure_spy.assert_awaited_once()
        call_msg, call_ctx = user_failure_spy.call_args.args
        assert call_msg == msg
        mock_activate_error_on_signature.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_on_failure__signature_failed__user_callback_still_runs_and_activation_skipped(
        self,
        mage_workflow,
        adapter_with_lifecycle,
        user_failure_spy,
        live_task_signature,
        mock_activate_error_on_signature,
    ):
        # Arrange: signature exists but is already marked FAILED (second hook fire)
        await live_task_signature.task_status.aupdate(status=SignatureStatus.FAILED)
        msg = ContextMessage()

        # Act
        await run_on_failure(mage_workflow, msg, live_task_signature.key)

        # Assert: user callback ran, activate_error skipped due to is_done() guard
        user_failure_spy.assert_awaited_once()
        mock_activate_error_on_signature.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_on_failure__runs_twice__user_callback_runs_both_times_activation_once(
        self,
        mage_workflow,
        adapter_with_lifecycle,
        user_failure_spy,
        live_task_signature,
        mock_activate_error_on_signature,
    ):
        # Arrange: active signature, hook fires twice in a row
        msg = ContextMessage()

        # Act
        await run_on_failure(mage_workflow, msg, live_task_signature.key)
        await run_on_failure(mage_workflow, msg, live_task_signature.key)

        # Assert: user callback ran on both invocations; mageflow activated once
        assert user_failure_spy.await_count == 2
        assert mock_activate_error_on_signature.await_count == 1
