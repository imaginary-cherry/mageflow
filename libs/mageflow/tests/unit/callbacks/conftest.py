import asyncio
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock, AsyncMock

import pytest
import pytest_asyncio
from hatchet_sdk import Context
from thirdmagic.clients import BaseClientAdapter
from thirdmagic.consts import TASK_ID_PARAM_NAME
from thirdmagic.signature.status import SignatureStatus
from thirdmagic.task import TaskSignature
from thirdmagic.task_def import MageflowTaskDefinition

import mageflow
from mageflow.callbacks import handle_task_callback, AcceptParams
from tests.integration.hatchet.models import ContextMessage


@dataclass
class MockContextConfig:
    job_name: str = "test_task"
    attempt_number: int = 1
    workflow_id: str = "wf-123"
    task_id: str | None = None
    cancel_raises: bool = False


@dataclass
class CallTracker:
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)


def create_mock_hatchet_context(config: MockContextConfig = None):
    config = config or MockContextConfig()
    ctx = MagicMock(spec=Context)
    ctx.action = MagicMock()
    ctx.action.job_name = config.job_name
    ctx.attempt_number = config.attempt_number
    ctx.workflow_id = config.workflow_id
    ctx.log = MagicMock()

    metadata = {}
    if config.task_id is not None:
        metadata[TASK_ID_PARAM_NAME] = config.task_id
    ctx.additional_metadata = metadata

    if config.cancel_raises:
        ctx.aio_cancel = AsyncMock(side_effect=asyncio.CancelledError())
    else:
        ctx.aio_cancel = AsyncMock()

    return ctx


async def task_signature_factory(
    task_name: str = "test_task",
    retries: int | None = None,
    status: SignatureStatus = SignatureStatus.PENDING,
    success_callbacks: list[TaskSignature] = None,
    error_callbacks: list[TaskSignature] = None,
) -> tuple[TaskSignature, MageflowTaskDefinition]:
    task_model = MageflowTaskDefinition(
        mageflow_task_name=task_name,
        task_name=task_name,
        input_validator=ContextMessage,
        retries=retries,
    )
    await task_model.asave()

    signature = await mageflow.asign(
        task_name,
        model_validators=ContextMessage,
        success_callbacks=[cb.key for cb in (success_callbacks or [])],
        error_callbacks=[cb.key for cb in (error_callbacks or [])],
    )
    if status != SignatureStatus.PENDING:
        signature.task_status.status = status
        await signature.asave()

    return signature, task_model


def handler_factory(
    expected_params: AcceptParams = AcceptParams.NO_CTX,
    wrap_res: bool = True,
    send_signature: bool = False,
    return_value: Any = "success_result",
    raises: Exception | None = None,
):
    tracked_calls: list[CallTracker] = []

    @handle_task_callback(
        expected_params=expected_params,
        wrap_res=wrap_res,
        send_signature=send_signature,
    )
    async def handler(*args, **kwargs):
        tracked_calls.append(CallTracker(args=args, kwargs=kwargs))
        if raises:
            raise raises
        return return_value

    return handler, tracked_calls


@pytest_asyncio.fixture
async def callback_signature():
    return await mageflow.asign("callback_task", model_validators=ContextMessage)


@pytest_asyncio.fixture
async def error_callback_signature():
    return await mageflow.asign("error_callback_task", model_validators=ContextMessage)


@pytest.fixture(autouse=True)
def mock_adapter():
    adapter = AsyncMock(spec=BaseClientAdapter)
    TaskSignature.ClientAdapter = adapter
    yield adapter
