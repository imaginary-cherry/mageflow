import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hatchet_sdk import Context, Hatchet
from redis import Redis

from mageflow.callbacks import AcceptParams
from mageflow.client import HatchetMageflow
from tests.integration.hatchet.models import ContextMessage


@pytest.fixture
def mock_handle_task_callback():
    with patch("mageflow.clients.hatchet.mageflow.handle_task_callback") as mock_htc:
        mock_htc.return_value = lambda fn: fn
        yield mock_htc


@pytest.fixture
def mageflow_hatchet():
    hatchet = MagicMock(spec=Hatchet)
    hatchet._client = MagicMock()
    redis_client = MagicMock(spec=Redis)

    return HatchetMageflow(hatchet=hatchet, redis_client=redis_client)


@pytest.fixture
def mock_message():
    return ContextMessage(base_data={"message_param": "message_value"})


@pytest.fixture
def mock_ctx():
    ctx = MagicMock(spec=Context)
    ctx.step_run_id = "test_step_run_id"
    return ctx


@pytest.fixture
def mock_logger():
    return MagicMock()


@pytest.mark.asyncio
async def test_stagger_execution_applies_delay_within_range(
    monkeypatch,
    mageflow_hatchet,
    mock_message,
    mock_ctx,
):
    sleep_mock = AsyncMock()
    monkeypatch.setattr(asyncio, "sleep", sleep_mock)
    stagger_range = timedelta(seconds=5)

    @mageflow_hatchet.stagger_execution(stagger_range)
    async def test_func(message):
        return "result"

    await test_func(mock_message, mock_ctx)

    wait_time = sleep_mock.await_args[0][0]
    mock_ctx.refresh_timeout.assert_called_once_with(timedelta(seconds=wait_time))
    assert sleep_mock.await_count >= 1

    (sleep_seconds,), _ = sleep_mock.await_args
    assert 0 <= sleep_seconds <= stagger_range.total_seconds()


@pytest.mark.asyncio
async def test_stagger_execution_calls_func_with_ctx_when_func_wants_ctx(
    mageflow_hatchet,
    mock_message,
    mock_ctx,
):
    """Test that stagger_execution calls the function with ctx when it wants ctx."""
    # Arrange
    stagger_range = timedelta(seconds=0.1)
    received_args = []

    @mageflow_hatchet.stagger_execution(stagger_range)
    @mageflow_hatchet.with_ctx
    async def test_func(message, ctx):
        received_args.append((message, ctx))
        return "result"

    # Act
    await test_func(mock_message, mock_ctx)

    # Assert
    assert received_args == [(mock_message, mock_ctx)]


@pytest.mark.asyncio
async def test_stagger_execution_calls_func_without_ctx_when_func_does_not_want_ctx(
    mageflow_hatchet,
    mock_message,
    mock_ctx,
):
    """Test that stagger_execution calls the function without ctx when it doesn't want ctx."""
    # Arrange
    stagger_range = timedelta(seconds=0.1)
    received_args = []

    @mageflow_hatchet.stagger_execution(stagger_range)
    async def test_func(message):
        received_args.append(message)
        return "result"

    # Act
    await test_func(mock_message, mock_ctx)

    # Assert
    assert received_args == [mock_message]


def test_task_passes_is_idempotent_false(orch, mock_handle_task_callback):
    @orch.task(name="regular-task")
    async def regular(msg):
        pass

    mock_handle_task_callback.assert_called_once_with(
        AcceptParams.NO_CTX, send_signature=False, is_idempotent=False
    )


def test_durable_task_passes_is_idempotent_true(orch, mock_handle_task_callback):
    @orch.durable_task(name="durable-task")
    async def durable(msg):
        pass

    mock_handle_task_callback.assert_called_once_with(
        AcceptParams.NO_CTX, send_signature=False, is_idempotent=True
    )
