import inspect

import pytest
from hatchet_sdk import Hatchet

from mageflow.client import HatchetMageflow


def get_method_parameters(cls, method_name: str) -> dict[str, inspect.Parameter]:
    method = getattr(cls, method_name)
    sig = inspect.signature(method)
    return {name: param for name, param in sig.parameters.items() if name != "self"}


def get_overridden_methods(child_cls: type, parent_cls: type) -> list[str]:
    parent_methods = {
        name
        for name, method in inspect.getmembers(parent_cls, predicate=inspect.isfunction)
        if not name.startswith("_")
    }

    overridden = []
    for name, method in inspect.getmembers(child_cls, predicate=inspect.isfunction):
        if name.startswith("_"):
            continue
        if name not in parent_methods:
            continue
        if name in child_cls.__dict__:
            overridden.append(name)

    return overridden


OVERRIDDEN_METHODS = get_overridden_methods(HatchetMageflow, Hatchet)


@pytest.mark.parametrize(
    ["method_name"],
    [[method] for method in OVERRIDDEN_METHODS],
)
def test_method_accepts_all_parent_parameters_sanity(method_name: str):
    # Arrange
    parent_params = get_method_parameters(Hatchet, method_name)
    child_params = get_method_parameters(HatchetMageflow, method_name)

    # Act
    child_param_names = set(child_params.keys())
    has_var_keyword = any(
        p.kind == inspect.Parameter.VAR_KEYWORD for p in child_params.values()
    )

    # Assert
    for parent_param_name, parent_param in parent_params.items():
        if parent_param.kind == inspect.Parameter.VAR_KEYWORD:
            continue

        is_explicitly_defined = parent_param_name in child_param_names
        accepts_via_kwargs = has_var_keyword

        assert is_explicitly_defined or accepts_via_kwargs, (
            f"Parameter '{parent_param_name}' from Hatchet.{method_name}() "
            f"is not accepted by HatchetMageflow.{method_name}()"
        )
