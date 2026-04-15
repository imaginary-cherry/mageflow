import pytest
from hatchet_sdk import Context

from mageflow.clients.hatchet.workflow import MageWorkflow
from tests.integration.hatchet.models import ContextMessage


@pytest.fixture
def mage_workflow(hatchet_mock):
    base_wf = hatchet_mock.workflow(name="test-wf", input_validator=ContextMessage)
    return MageWorkflow(base_wf)


def _add_user_success_hook(wf):
    @wf.on_success_task()
    async def user_on_success(input, ctx: Context):
        pass


def _add_user_failure_hook(wf):
    @wf.on_failure_task()
    async def user_on_failure(input, ctx: Context):
        pass


class TestInjectHooks:
    def test_no_user_callbacks_adds_both_hooks(self, mage_workflow):
        # Act
        mage_workflow.inject_hooks()

        # Assert
        assert mage_workflow._on_success_task is not None
        assert mage_workflow._on_failure_task is not None

    def test_user_provides_only_on_success(self, mage_workflow):
        # Arrange
        _add_user_success_hook(mage_workflow)
        user_success_task = mage_workflow._on_success_task

        # Act
        mage_workflow.inject_hooks()

        # Assert
        assert mage_workflow._on_success_task is user_success_task
        assert mage_workflow._on_failure_task is not None

    def test_user_provides_only_on_failure(self, mage_workflow):
        # Arrange
        _add_user_failure_hook(mage_workflow)
        user_failure_task = mage_workflow._on_failure_task

        # Act
        mage_workflow.inject_hooks()

        # Assert
        assert mage_workflow._on_success_task is not None
        assert mage_workflow._on_failure_task is user_failure_task

    def test_user_provides_both_callbacks(self, mage_workflow):
        # Arrange
        _add_user_success_hook(mage_workflow)
        _add_user_failure_hook(mage_workflow)
        user_success_task = mage_workflow._on_success_task
        user_failure_task = mage_workflow._on_failure_task

        # Act
        mage_workflow.inject_hooks()

        # Assert
        assert mage_workflow._on_success_task is user_success_task
        assert mage_workflow._on_failure_task is user_failure_task
