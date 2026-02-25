import inspect
import typing

import pytest
from hatchet_sdk import Hatchet

from mageflow.client import HatchetMageflow


def get_method_parameters(cls, method_name: str) -> dict[str, inspect.Parameter]:
    method = getattr(cls, method_name)
    sig = inspect.signature(method)
    return {name: param for name, param in sig.parameters.items() if name != "self"}


def get_unpack_typed_dict(params: dict[str, inspect.Parameter]) -> type | None:
    var_kw = next(
        (p for p in params.values() if p.kind == inspect.Parameter.VAR_KEYWORD), None
    )
    if var_kw is None or var_kw.annotation is inspect.Parameter.empty:
        return None
    args = typing.get_args(var_kw.annotation)
    return args[0] if args else None


def get_overridden_methods(child_cls: type, parent_cls: type) -> list[str]:
    parent_methods = {
        name
        for name, method in inspect.getmembers(parent_cls, predicate=inspect.isfunction)
        if not name.startswith("_")
    }

    return [
        name
        for name, method in inspect.getmembers(child_cls, predicate=inspect.isfunction)
        if not name.startswith("_")
        and name in parent_methods
        and name in child_cls.__dict__
    ]


def _has_typevar(annotation) -> bool:
    if isinstance(annotation, typing.TypeVar):
        return True
    return any(_has_typevar(arg) for arg in typing.get_args(annotation))


SKIP_KINDS = {inspect.Parameter.VAR_KEYWORD, inspect.Parameter.VAR_POSITIONAL}

OVERRIDDEN_METHODS = get_overridden_methods(HatchetMageflow, Hatchet)


@pytest.mark.parametrize(
    ["method_name"],
    [[method] for method in OVERRIDDEN_METHODS],
)
def test_method_accepts_all_parent_parameters_sanity(method_name: str):
    # Arrange
    parent_params = get_method_parameters(Hatchet, method_name)
    parent_hints = typing.get_type_hints(getattr(Hatchet, method_name))
    child_params = get_method_parameters(HatchetMageflow, method_name)
    unpack_td = get_unpack_typed_dict(child_params)
    unpack_keys = set(typing.get_type_hints(unpack_td).keys()) if unpack_td else set()
    unpack_hints = typing.get_type_hints(unpack_td) if unpack_td else {}

    # Act / Assert
    for parent_param_name, parent_param in parent_params.items():
        if parent_param.kind in SKIP_KINDS:
            continue

        is_explicitly_defined = parent_param_name in child_params
        is_in_unpack = parent_param_name in unpack_keys

        assert is_explicitly_defined or is_in_unpack, (
            f"Parameter '{parent_param_name}' from Hatchet.{method_name}() "
            f"is not accepted by HatchetMageflow.{method_name}()"
        )

        if is_explicitly_defined:
            child_param = child_params[parent_param_name]
            assert child_param.default == parent_param.default, (
                f"Parameter '{parent_param_name}' in HatchetMageflow.{method_name}() "
                f"has default {child_param.default!r}, expected {parent_param.default!r}"
            )
            assert child_param.kind == parent_param.kind, (
                f"Parameter '{parent_param_name}' in HatchetMageflow.{method_name}() "
                f"has kind {child_param.kind.name}, expected {parent_param.kind.name}"
            )
        else:
            parent_hint = parent_hints.get(parent_param_name)
            unpack_hint = unpack_hints.get(parent_param_name)
            if parent_hint is not None and not _has_typevar(parent_hint):
                assert unpack_hint == parent_hint, (
                    f"Parameter '{parent_param_name}' in Unpack TypedDict for "
                    f"HatchetMageflow.{method_name}() has type {unpack_hint}, "
                    f"expected {parent_hint}"
                )
