"""
Tests for WFCMP-01, WFCMP-02, WFCMP-03:
- on_success_task injected and fires lifecycle.task_success() on workflow completion
- on_failure_task injected and fires lifecycle.task_failed() on workflow step failure
- User-defined on_failure/on_success handlers composed with mageflow hooks
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call
from hatchet_sdk import Context
from thirdmagic.consts import TASK_ID_PARAM_NAME

import mageflow
from mageflow.clients.hatchet.mageflow import HatchetMageflow


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_mock_ctx(task_key: str | None = "test-task-key", task_run_errors: dict | None = None):
    """Create a MagicMock Context with configured additional_metadata and task_run_errors."""
    ctx = MagicMock(spec=Context)
    ctx.additional_metadata = {TASK_ID_PARAM_NAME: task_key} if task_key else {}
    ctx.task_run_errors = task_run_errors or {"step-1": "some error"}
    return ctx


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mf(hatchet_mock, redis_client):
    """Return a HatchetMageflow instance."""
    return mageflow.Mageflow(hatchet_mock, redis_client)


@pytest.fixture
def test_workflow(mf):
    """Create a simple Workflow via mf.workflow()."""
    wf = mf.workflow(name="test-wf")

    @wf.task()
    async def my_task(input, ctx: Context):
        return {}

    return wf


# ---------------------------------------------------------------------------
# WFCMP-01: on_success_task injection
# ---------------------------------------------------------------------------

class TestOnSuccessInjection:
    def test_injects_on_success_task_when_none(self, mf, test_workflow):
        """Workflow with no user hooks gets on_success_task injected."""
        assert test_workflow._on_success_task is None, "Pre-condition: no success hook"

        mf._inject_workflow_hooks(test_workflow)

        assert test_workflow._on_success_task is not None

    @pytest.mark.asyncio
    async def test_injected_on_success_calls_task_success(self, mf, test_workflow):
        """Injected on_success_task calls lifecycle.task_success({}) when signature present."""
        mock_lifecycle = AsyncMock()
        mock_lifecycle.task_success = AsyncMock()

        with patch.object(
            type(mf), "_lifecycle_from_ctx", new_callable=AsyncMock, return_value=mock_lifecycle
        ):
            mf._inject_workflow_hooks(test_workflow)

            ctx = make_mock_ctx(task_key="sig-key-123")
            input_mock = MagicMock()
            await test_workflow._on_success_task.fn(input_mock, ctx)

        mock_lifecycle.task_success.assert_awaited_once_with({})

    @pytest.mark.asyncio
    async def test_on_success_noop_when_no_task_id(self, mf, test_workflow):
        """Injected hook is no-op when ctx has no TASK_ID_PARAM_NAME."""
        mock_lifecycle_from_ctx = AsyncMock(return_value=None)

        with patch.object(
            type(mf), "_lifecycle_from_ctx", mock_lifecycle_from_ctx
        ):
            mf._inject_workflow_hooks(test_workflow)

            ctx = make_mock_ctx(task_key=None)
            input_mock = MagicMock()
            result = await test_workflow._on_success_task.fn(input_mock, ctx)

        # lifecycle was fetched but returned None — no further calls
        assert result is None


# ---------------------------------------------------------------------------
# WFCMP-02: on_failure_task injection
# ---------------------------------------------------------------------------

class TestOnFailureInjection:
    def test_injects_on_failure_task_when_none(self, mf, test_workflow):
        """Workflow with no user hooks gets on_failure_task injected."""
        assert test_workflow._on_failure_task is None, "Pre-condition: no failure hook"

        mf._inject_workflow_hooks(test_workflow)

        assert test_workflow._on_failure_task is not None

    @pytest.mark.asyncio
    async def test_injected_on_failure_calls_task_failed(self, mf, test_workflow):
        """Injected on_failure_task calls lifecycle.task_failed with errors dict."""
        mock_lifecycle = AsyncMock()
        mock_lifecycle.task_failed = AsyncMock()
        errors = {"step-1": "some error message"}

        with patch.object(
            type(mf), "_lifecycle_from_ctx", new_callable=AsyncMock, return_value=mock_lifecycle
        ):
            mf._inject_workflow_hooks(test_workflow)

            ctx = make_mock_ctx(task_key="sig-key-123", task_run_errors=errors)
            input_mock = MagicMock()
            await test_workflow._on_failure_task.fn(input_mock, ctx)

        mock_lifecycle.task_failed.assert_awaited_once()
        call_args = mock_lifecycle.task_failed.call_args
        assert call_args[0][0] == errors  # first positional arg: errors dict

    @pytest.mark.asyncio
    async def test_on_failure_noop_when_no_task_id(self, mf, test_workflow):
        """Injected failure hook is no-op when ctx has no TASK_ID_PARAM_NAME."""
        mock_lifecycle_from_ctx = AsyncMock(return_value=None)

        with patch.object(
            type(mf), "_lifecycle_from_ctx", mock_lifecycle_from_ctx
        ):
            mf._inject_workflow_hooks(test_workflow)

            ctx = make_mock_ctx(task_key=None)
            input_mock = MagicMock()
            result = await test_workflow._on_failure_task.fn(input_mock, ctx)

        assert result is None


# ---------------------------------------------------------------------------
# WFCMP-03: Composing with user-defined handlers
# ---------------------------------------------------------------------------

class TestUserHandlerComposition:
    @pytest.mark.asyncio
    async def test_wraps_existing_on_failure_fn_both_execute(self, mf, test_workflow):
        """When user defines on_failure_task, both mageflow and user callbacks execute."""
        user_fn_called = []

        @test_workflow.on_failure_task()
        async def user_failure_handler(input, ctx: Context):
            user_fn_called.append("user")

        mock_lifecycle = AsyncMock()
        mock_lifecycle.task_failed = AsyncMock()

        with patch.object(
            type(mf), "_lifecycle_from_ctx", new_callable=AsyncMock, return_value=mock_lifecycle
        ):
            mf._inject_workflow_hooks(test_workflow)

            ctx = make_mock_ctx(task_key="sig-key-456")
            input_mock = MagicMock()
            await test_workflow._on_failure_task.fn(input_mock, ctx)

        # Both must have been called
        mock_lifecycle.task_failed.assert_awaited_once()
        assert user_fn_called == ["user"]

    @pytest.mark.asyncio
    async def test_wraps_existing_on_success_fn_both_execute(self, mf, test_workflow):
        """When user defines on_success_task, both mageflow and user callbacks execute."""
        user_fn_called = []

        @test_workflow.on_success_task()
        async def user_success_handler(input, ctx: Context):
            user_fn_called.append("user")

        mock_lifecycle = AsyncMock()
        mock_lifecycle.task_success = AsyncMock()

        with patch.object(
            type(mf), "_lifecycle_from_ctx", new_callable=AsyncMock, return_value=mock_lifecycle
        ):
            mf._inject_workflow_hooks(test_workflow)

            ctx = make_mock_ctx(task_key="sig-key-789")
            input_mock = MagicMock()
            await test_workflow._on_success_task.fn(input_mock, ctx)

        # Both must have been called
        mock_lifecycle.task_success.assert_awaited_once()
        assert user_fn_called == ["user"]

    @pytest.mark.asyncio
    async def test_user_on_failure_still_called_when_no_signature(self, mf, test_workflow):
        """User's on_failure_task is still called even when there's no mageflow signature."""
        user_fn_called = []

        @test_workflow.on_failure_task()
        async def user_failure_handler(input, ctx: Context):
            user_fn_called.append("user")

        with patch.object(
            type(mf), "_lifecycle_from_ctx", new_callable=AsyncMock, return_value=None
        ):
            mf._inject_workflow_hooks(test_workflow)

            ctx = make_mock_ctx(task_key=None)
            input_mock = MagicMock()
            await test_workflow._on_failure_task.fn(input_mock, ctx)

        assert user_fn_called == ["user"]

    @pytest.mark.asyncio
    async def test_user_on_success_still_called_when_no_signature(self, mf, test_workflow):
        """User's on_success_task is still called even when there's no mageflow signature."""
        user_fn_called = []

        @test_workflow.on_success_task()
        async def user_success_handler(input, ctx: Context):
            user_fn_called.append("user")

        with patch.object(
            type(mf), "_lifecycle_from_ctx", new_callable=AsyncMock, return_value=None
        ):
            mf._inject_workflow_hooks(test_workflow)

            ctx = make_mock_ctx(task_key=None)
            input_mock = MagicMock()
            await test_workflow._on_success_task.fn(input_mock, ctx)

        assert user_fn_called == ["user"]


# ---------------------------------------------------------------------------
# Worker integration
# ---------------------------------------------------------------------------

class TestWorkerIntegration:
    def test_worker_injects_hooks_before_super(self, mf, test_workflow):
        """worker() calls _inject_workflow_hooks for each workflow before super().worker()."""
        injected = []

        original_inject = mf._inject_workflow_hooks
        def spy_inject(wf):
            injected.append(wf)
            # Don't actually inject (would need real Hatchet connection)

        mf._inject_workflow_hooks = spy_inject

        with patch.object(HatchetMageflow, "worker", wraps=mf.worker) as worker_spy, \
             patch("mageflow.clients.hatchet.mageflow.HatchetMageflow.init_mageflow_hatchet_tasks", return_value=[]):
            # Call super().worker() would fail without real hatchet — patch it
            with patch("hatchet_sdk.Hatchet.worker", return_value=MagicMock()):
                mf.worker("test-worker", workflows=[test_workflow])

        # The test workflow should have been passed to _inject_workflow_hooks
        assert test_workflow in injected


# ---------------------------------------------------------------------------
# _lifecycle_from_ctx
# ---------------------------------------------------------------------------

class TestLifecycleFromCtx:
    @pytest.mark.asyncio
    async def test_returns_none_when_no_task_id(self, mf):
        """_lifecycle_from_ctx returns None when TASK_ID_PARAM_NAME not in metadata."""
        ctx = make_mock_ctx(task_key=None)
        result = await mf._lifecycle_from_ctx(ctx)
        assert result is None

    @pytest.mark.asyncio
    async def test_calls_lifecycle_from_signature_when_task_id_present(self, mf):
        """_lifecycle_from_ctx delegates to Signature.ClientAdapter.lifecycle_from_signature."""
        ctx = make_mock_ctx(task_key="sig-key-abc")
        mock_lifecycle = AsyncMock()

        # Verify the method exists on HatchetMageflow
        assert hasattr(mf, "_lifecycle_from_ctx"), "HatchetMageflow must have _lifecycle_from_ctx"

        # Test the delegation via adapter mock
        fake_adapter = AsyncMock()
        fake_adapter.lifecycle_from_signature = AsyncMock(return_value=mock_lifecycle)

        from thirdmagic.signature import Signature
        original_adapter = Signature.ClientAdapter
        try:
            Signature.ClientAdapter = fake_adapter
            result = await mf._lifecycle_from_ctx(ctx)
        finally:
            Signature.ClientAdapter = original_adapter

        fake_adapter.lifecycle_from_signature.assert_awaited_once()
        assert result is mock_lifecycle
