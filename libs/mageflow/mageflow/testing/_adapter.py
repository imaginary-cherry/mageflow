import dataclasses
from typing import Any

from pydantic import BaseModel, TypeAdapter, ValidationError
from thirdmagic.chain.model import ChainTaskSignature
from thirdmagic.clients.base import BaseClientAdapter
from thirdmagic.clients.lifecycle import BaseLifecycle
from thirdmagic.signature import Signature
from thirdmagic.swarm.model import SwarmTaskSignature
from thirdmagic.task import TaskSignature
from thirdmagic.task_def import MageflowTaskDefinition
from thirdmagic.utils import HatchetTaskType


@dataclasses.dataclass
class RecordedDispatch:
    dispatch_type: str
    signature_or_name: str
    input_data: Any
    kwargs: dict


@dataclasses.dataclass
class TaskDispatchRecord:
    task_name: str  # signature.task_name (human-readable)
    input_data: Any  # msg passed to acall_signature / await_signature
    kwargs: dict  # extra kwargs forwarded


@dataclasses.dataclass
class SwarmDispatchRecord:
    swarm_name: str  # swarm.task_name (human-readable)
    task_names: list[str]  # resolved sub-task names at dispatch time
    kwargs: dict


@dataclasses.dataclass
class ChainDispatchRecord:
    chain_name: str  # chain.task_name (e.g. "chain-task:first_task")
    results: Any  # results from acall_chain_done
    task_names: list[str]  # resolved sub-task names


SignatureDispatchType = TaskDispatchRecord | SwarmDispatchRecord | ChainDispatchRecord

# ------------------------------------------------------------------
# Matching helpers
# ------------------------------------------------------------------


def _to_dict(value: Any) -> dict:
    """
    Convert a pydantic BaseModel or dict to a plain dict.

    Returns {} for None. Raises TypeError for unconvertible types.
    """
    if value is None:
        return {}
    if isinstance(value, BaseModel):
        return value.model_dump(exclude_unset=True)
    if isinstance(value, dict):
        return value
    raise TypeError(
        f"Cannot convert {type(value).__name__!r} to dict for matching. "
        "Expected a pydantic BaseModel or dict."
    )


def _partial_match(actual_input: Any, expected: dict) -> bool:
    """
    Return True if all keys in `expected` match the corresponding keys in `actual_input`.

    If `expected` is empty, always returns True (no constraints).
    """
    if not expected:
        return True
    try:
        actual_dict = _to_dict(actual_input)
    except TypeError:
        return False
    return all(actual_dict.get(key) == val for key, val in expected.items())


def _exact_match(actual_input: Any, expected: dict) -> bool:
    """Return True if `actual_input` converted to dict equals `expected` exactly."""
    try:
        actual_dict = _to_dict(actual_input)
    except TypeError:
        return False
    return actual_dict == expected


def _format_diff(expected: dict, actual: dict) -> str:
    """Return a human-readable diff between expected and actual dicts."""
    lines = []
    all_keys = sorted(set(expected) | set(actual))
    for key in all_keys:
        in_expected = key in expected
        in_actual = key in actual
        if in_expected and in_actual:
            if expected[key] != actual[key]:
                lines.append(
                    f"  Expected {key}={expected[key]!r} but got {key}={actual[key]!r}"
                )
        elif in_expected and not in_actual:
            lines.append(f"  Expected {key}={expected[key]!r} but key was missing")
        elif in_actual and not in_expected:
            lines.append(f"  Unexpected key {key}={actual[key]!r}")
    return "\n".join(lines) if lines else "(no specific diff available)"


class _StubRunRef:
    workflow_run_id: str = "test-stub-run-id"

    async def aio_result(self) -> dict:
        return {}


class TestClientAdapter(BaseClientAdapter):
    def __init__(
        self,
        task_defs: dict[str, MageflowTaskDefinition] | None = None,
        local_execution: bool = False,
        hatchet_tasks: dict[str, Any] | None = None,
    ):
        self._dispatches: list[RecordedDispatch] = []
        self._typed_dispatches: list[SignatureDispatchType] = []
        self._task_defs: dict[str, MageflowTaskDefinition] = task_defs or {}
        self._local_execution: bool = local_execution
        self._hatchet_tasks: dict[str, Any] = hatchet_tasks or {}

    # ------------------------------------------------------------------
    # Helper: input validation
    # ------------------------------------------------------------------

    def _validate_input(self, task_name: str, msg: Any) -> None:
        task_def = self._task_defs.get(task_name)
        if task_def is None:
            return
        validator = self.extract_validator(task_def)
        if validator is BaseModel:
            return
        try:
            validator.model_validate(msg)
        except ValidationError as e:
            raise ValueError(
                f"Dispatch input validation failed for task '{task_name}': {e}"
            )

    # ------------------------------------------------------------------
    # BaseClientAdapter abstract methods
    # ------------------------------------------------------------------

    def extract_validator(self, client_task) -> type[BaseModel]:
        validator = getattr(client_task, "input_validator", None)
        if validator is None:
            return BaseModel
        if isinstance(validator, TypeAdapter):
            validator = validator._type
        return validator

    def extract_retries(self, client_task) -> int:
        return getattr(client_task, "retries", 0) or 0

    async def acall_signature(
        self,
        signature: "TaskSignature",
        msg: Any,
        set_return_field: bool,
        **kwargs,
    ):
        self._validate_input(signature.task_name, msg)
        self._dispatches.append(
            RecordedDispatch(
                dispatch_type="signature",
                signature_or_name=signature.task_name,
                input_data=msg,
                kwargs=kwargs,
            )
        )
        self._typed_dispatches.append(
            TaskDispatchRecord(
                task_name=signature.task_name,
                input_data=msg,
                kwargs=kwargs,
            )
        )
        if self._local_execution and signature.task_name in self._hatchet_tasks:
            task = self._hatchet_tasks[signature.task_name]
            return await task.aio_mock_run(msg)
        return _StubRunRef()

    async def await_signature(
        self,
        signature: "TaskSignature",
        msg: Any,
        set_return_field: bool,
        **kwargs,
    ):
        self._validate_input(signature.task_name, msg)
        self._dispatches.append(
            RecordedDispatch(
                dispatch_type="await_signature",
                signature_or_name=signature.task_name,
                input_data=msg,
                kwargs=kwargs,
            )
        )
        self._typed_dispatches.append(
            TaskDispatchRecord(
                task_name=signature.task_name,
                input_data=msg,
                kwargs=kwargs,
            )
        )
        if self._local_execution and signature.task_name in self._hatchet_tasks:
            task = self._hatchet_tasks[signature.task_name]
            return await task.aio_mock_run(msg)
        return {}

    async def acall_chain_done(self, results: Any, chain: "ChainTaskSignature"):
        self._dispatches.append(
            RecordedDispatch(
                dispatch_type="chain_done",
                signature_or_name=chain.key,
                input_data=results,
                kwargs={},
            )
        )
        try:
            sub_tasks = await chain.sub_tasks()
            task_names = [t.task_name for t in sub_tasks]
        except Exception:
            task_names = []
        self._typed_dispatches.append(
            ChainDispatchRecord(
                chain_name=chain.task_name,
                results=results,
                task_names=task_names,
            )
        )
        return _StubRunRef()

    async def acall_chain_error(
        self,
        original_msg: dict,
        error: BaseException,
        chain: "ChainTaskSignature",
        failed_task: "Signature",
    ):
        self._dispatches.append(
            RecordedDispatch(
                dispatch_type="chain_error",
                signature_or_name=chain.key,
                input_data={
                    "original_msg": original_msg,
                    "error": str(error),
                    "failed_task_key": failed_task.key,
                },
                kwargs={},
            )
        )
        return _StubRunRef()

    async def afill_swarm(
        self, swarm: "SwarmTaskSignature", max_tasks: int = None, **kwargs
    ):
        self._dispatches.append(
            RecordedDispatch(
                dispatch_type="swarm_fill",
                signature_or_name=swarm.key,
                input_data={"max_tasks": max_tasks},
                kwargs=kwargs,
            )
        )
        try:
            sub_tasks = await swarm.sub_tasks()
            task_names = [t.task_name for t in sub_tasks]
        except Exception:
            task_names = []
        self._typed_dispatches.append(
            SwarmDispatchRecord(
                swarm_name=swarm.task_name,
                task_names=task_names,
                kwargs=kwargs,
            )
        )
        return _StubRunRef()

    async def acall_swarm_item_done(
        self, results: Any, swarm: "SwarmTaskSignature", swarm_item: "Signature"
    ):
        self._dispatches.append(
            RecordedDispatch(
                dispatch_type="swarm_item_done",
                signature_or_name=swarm.key,
                input_data={"results": results, "swarm_item_key": swarm_item.key},
                kwargs={},
            )
        )
        return _StubRunRef()

    async def acall_swarm_item_error(
        self, error: BaseException, swarm: "SwarmTaskSignature", swarm_item: "Signature"
    ):
        self._dispatches.append(
            RecordedDispatch(
                dispatch_type="swarm_item_error",
                signature_or_name=swarm.key,
                input_data={"error": str(error), "swarm_item_key": swarm_item.key},
                kwargs={},
            )
        )
        return _StubRunRef()

    def should_task_retry(
        self,
        task_definition: MageflowTaskDefinition,
        attempt_num: int,
        e: BaseException,
    ) -> bool:
        return False

    def task_name(self, task: "HatchetTaskType") -> str:
        return task.name

    async def create_lifecycle(self, *args) -> BaseLifecycle:
        from mageflow.lifecycle.task import TaskLifecycle

        return TaskLifecycle()

    async def lifecycle_from_signature(self, *args) -> BaseLifecycle:
        return None

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    @property
    def dispatches(self) -> list[RecordedDispatch]:
        return list(self._dispatches)

    @property
    def task_dispatches(self) -> list[TaskDispatchRecord]:
        return [d for d in self._typed_dispatches if isinstance(d, TaskDispatchRecord)]

    @property
    def swarm_dispatches(self) -> list[SwarmDispatchRecord]:
        return [d for d in self._typed_dispatches if isinstance(d, SwarmDispatchRecord)]

    @property
    def chain_dispatches(self) -> list[ChainDispatchRecord]:
        return [d for d in self._typed_dispatches if isinstance(d, ChainDispatchRecord)]

    def clear(self) -> None:
        self._dispatches.clear()
        self._typed_dispatches.clear()

    # ------------------------------------------------------------------
    # Assertion methods
    # ------------------------------------------------------------------

    def assert_task_dispatched(
        self,
        task_name: str,
        expected_input: dict | None = None,
        exact: bool = False,
    ) -> TaskDispatchRecord:
        """Assert that a task with the given name was dispatched.

        Args:
            task_name: The human-readable task name to look for.
            expected_input: Optional dict of expected input data. When provided,
                checks that at least one dispatch with this task_name matches the
                input. By default uses partial matching (extra keys are ignored).
            exact: When True, uses exact matching (actual input must equal expected
                exactly, no extra keys allowed).

        Returns:
            The matching TaskDispatchRecord.

        Raises:
            AssertionError: If no dispatch with task_name exists, or if none of
                the dispatches match the expected_input.
        """
        name_matches = [d for d in self.task_dispatches if d.task_name == task_name]
        if not name_matches:
            dispatched_names = [d.task_name for d in self.task_dispatches]
            raise AssertionError(
                f"Task '{task_name}' was not dispatched. "
                f"Dispatched tasks: {dispatched_names}"
            )
        if expected_input is None:
            return name_matches[0]
        match_fn = _exact_match if exact else _partial_match
        for record in name_matches:
            if match_fn(record.input_data, expected_input):
                return record
        # None matched — show diff against first name-matched record
        first = name_matches[0]
        try:
            actual_dict = _to_dict(first.input_data)
        except TypeError:
            actual_dict = {}
        diff = _format_diff(expected_input, actual_dict)
        raise AssertionError(
            f"Task '{task_name}' was dispatched but input did not match.\n{diff}"
        )

    def assert_swarm_dispatched(
        self,
        swarm_name: str,
        expected_task_names: list[str] | None = None,
    ) -> SwarmDispatchRecord:
        """Assert that a swarm with the given name was dispatched.

        Args:
            swarm_name: The human-readable swarm name to look for.
            expected_task_names: Optional list of task names that must all appear
                in the swarm's resolved task_names (subset check).

        Returns:
            The matching SwarmDispatchRecord.

        Raises:
            AssertionError: If no swarm dispatch with swarm_name exists, or if
                none of the swarm dispatches contain all expected_task_names.
        """
        name_matches = [d for d in self.swarm_dispatches if d.swarm_name == swarm_name]
        if not name_matches:
            dispatched_names = [d.swarm_name for d in self.swarm_dispatches]
            raise AssertionError(
                f"Swarm '{swarm_name}' was not dispatched. "
                f"Dispatched swarms: {dispatched_names}"
            )
        if expected_task_names is None:
            return name_matches[0]
        for record in name_matches:
            if all(name in record.task_names for name in expected_task_names):
                return record
        first = name_matches[0]
        raise AssertionError(
            f"Swarm '{swarm_name}' was dispatched but task names did not match.\n"
            f"  Expected: {expected_task_names}\n"
            f"  Actual: {first.task_names}"
        )

    def assert_chain_dispatched(
        self,
        chain_name: str,
        expected_task_names: list[str] | None = None,
    ) -> ChainDispatchRecord:
        """Assert that a chain with the given name completed.

        Note: This asserts chain *completion* (when acall_chain_done fired), not
        chain initiation. The chain's individual task dispatches are also visible
        in task_dispatches.

        Args:
            chain_name: The human-readable chain name to look for.
            expected_task_names: Optional list of task names that must all appear
                in the chain's resolved task_names (subset check).

        Returns:
            The matching ChainDispatchRecord.

        Raises:
            AssertionError: If no chain dispatch with chain_name exists, or if
                none of the chain dispatches contain all expected_task_names.
        """
        name_matches = [d for d in self.chain_dispatches if d.chain_name == chain_name]
        if not name_matches:
            dispatched_names = [d.chain_name for d in self.chain_dispatches]
            raise AssertionError(
                f"Chain '{chain_name}' was not dispatched. "
                f"Dispatched chains: {dispatched_names}"
            )
        if expected_task_names is None:
            return name_matches[0]
        for record in name_matches:
            if all(name in record.task_names for name in expected_task_names):
                return record
        first = name_matches[0]
        raise AssertionError(
            f"Chain '{chain_name}' was dispatched but task names did not match.\n"
            f"  Expected: {expected_task_names}\n"
            f"  Actual: {first.task_names}"
        )

    def assert_nothing_dispatched(self) -> None:
        """Assert that no dispatches occurred at all.

        Raises:
            AssertionError: If any dispatches are recorded, listing each one.
        """
        if not self._typed_dispatches:
            return
        summary = []
        for record in self._typed_dispatches:
            if isinstance(record, TaskDispatchRecord):
                summary.append(f"TaskDispatchRecord({record.task_name})")
            elif isinstance(record, SwarmDispatchRecord):
                summary.append(f"SwarmDispatchRecord({record.swarm_name})")
            elif isinstance(record, ChainDispatchRecord):
                summary.append(f"ChainDispatchRecord({record.chain_name})")
            else:
                summary.append(repr(record))
        raise AssertionError(
            f"Expected no dispatches but {len(self._typed_dispatches)} occurred: "
            f"{summary}"
        )
