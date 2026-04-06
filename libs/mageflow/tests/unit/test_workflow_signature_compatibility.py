import pytest
from hatchet_sdk.runnables.workflow import Workflow

from mageflow.clients.hatchet.workflow import MageWorkflow
from tests.unit.signature_compat_helpers import (
    assert_child_accepts_all_parent_params,
    get_overridden_methods,
)

OVERRIDDEN_METHODS = get_overridden_methods(MageWorkflow, Workflow)


@pytest.mark.parametrize(
    ["method_name"],
    [[method] for method in OVERRIDDEN_METHODS],
)
def test_method_accepts_all_parent_parameters_sanity(method_name: str):
    assert_child_accepts_all_parent_params(Workflow, MageWorkflow, method_name)
