---
phase: 04-decorators-completion-hooks-dispatch
plan: "02"
subsystem: api

tags: [hatchet, workflow, lifecycle, completion-hooks, on_success_task, on_failure_task, testing]

# Dependency graph
requires:
  - phase: 04-01
    provides: HatchetMageflow.workflow() proxy, WorkflowOptions TypedDict

provides:
  - HatchetMageflow._inject_workflow_hooks() — injects on_success/on_failure into Workflow objects
  - HatchetMageflow._lifecycle_from_ctx() — resolves SignatureLifecycle from Hatchet Context metadata
  - Updated worker() — injects hooks for all workflows before super().worker() serialization
  - Tests for WFCMP-01, WFCMP-02, WFCMP-03 (13 tests)

affects:
  - Any code calling HatchetMageflow.worker() — hooks are now automatically injected
  - Workflows registered via mf.workflow() will have lifecycle callbacks wired at worker() time

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Task.fn replacement for composing user and mageflow lifecycle callbacks
    - functools.wraps on composed hook functions for correct name/metadata propagation
    - _lifecycle_from_ctx() as a thin resolver that returns None for vanilla runs (no-op guard)

key-files:
  created:
    - libs/mageflow/tests/unit/workflows/test_completion_hooks.py
  modified:
    - libs/mageflow/mageflow/clients/hatchet/mageflow.py

key-decisions:
  - "Task.fn (not Task._fn) is the correct attribute — hatchet-sdk stores it as fn in __init__"
  - "On injection when no user hook: use @workflow.on_success_task() decorator (cleanest path, lets Hatchet own the Task object)"
  - "On injection when user hook exists: replace Task.fn with composed wrapper (mageflow first, then user)"
  - "worker() adds workflows = workflows or [] guard before iterating — handles None default correctly"
  - "lifecycle.task_success({}) called with empty dict — workflow has no structured output to pass at hook level"
  - "lifecycle.task_failed(errors, Exception(str(errors))) — creates Exception from errors string, matches task_failed signature"

# Metrics
duration: 15min
completed: 2026-03-23
---

# Phase 4 Plan 02: Completion Hook Injection Summary

**Lifecycle callback injection via on_success_task/on_failure_task in worker() — mageflow hooks compose with user handlers via Task.fn replacement**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-03-23T17:13:12Z
- **Completed:** 2026-03-23
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files modified:** 2 (1 implementation, 1 test file)

## Accomplishments

- Added `_lifecycle_from_ctx()` to `HatchetMageflow`: looks up `TASK_ID_PARAM_NAME` from `ctx.additional_metadata`, delegates to `Signature.ClientAdapter.lifecycle_from_signature()`, returns `None` for vanilla runs
- Added `_inject_workflow_hooks()` to `HatchetMageflow`:
  - No user hook: registers new `on_success_task` / `on_failure_task` via Hatchet's decorator API
  - User hook present: composes by replacing `Task.fn` — mageflow callback runs first, then user's original handler
  - Vanilla runs (no `TASK_ID_PARAM_NAME`) are graceful no-ops
- Updated `worker()`: adds `workflows = workflows or []` guard, then iterates and calls `_inject_workflow_hooks(wf)` for each workflow before `super().worker()`
- 13 new tests covering WFCMP-01, WFCMP-02, WFCMP-03; full suite 245 tests, all passing

## Task Commits

1. **Task 1 RED: Failing completion hook tests** - `8b2be88` (test)
2. **Task 1 GREEN: _inject_workflow_hooks, _lifecycle_from_ctx, worker()** - `92a2733` (feat)

## Files Created/Modified

- `libs/mageflow/mageflow/clients/hatchet/mageflow.py` — Added `_lifecycle_from_ctx()`, `_inject_workflow_hooks()`, updated `worker()`, imported `TASK_ID_PARAM_NAME`
- `libs/mageflow/tests/unit/workflows/test_completion_hooks.py` — 13 tests covering all hook scenarios

## Decisions Made

- Used `Task.fn` (not `Task._fn`) — discovered during GREEN phase that hatchet-sdk stores it as `fn` in `Task.__init__`. This was discovered by running tests and inspecting the `Task` source. The plan's interface doc said `_fn` but the actual attribute is `fn`. Auto-fixed.
- Chose `lifecycle.task_success({})` with empty dict — workflow-level hooks have no structured per-task output; empty dict is the correct sentinel for "completed without specific result"
- `lifecycle.task_failed(errors, Exception(str(errors)))` — wraps the errors dict as an Exception string to satisfy the `task_failed(message, error)` signature from `BaseLifecycle`
- `functools.wraps(lambda input, ctx: None)` used for the newly-injected (non-wrapping) case — provides a consistent function signature while avoiding name conflicts

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Task.fn vs Task._fn attribute name**
- **Found during:** Task 1 GREEN (first test run after implementation)
- **Issue:** Plan's interface doc referenced `task._fn` but hatchet-sdk 1.23.4 stores the function as `task.fn` (assigned as `self.fn = _fn` in `Task.__init__`)
- **Fix:** Updated all references in both implementation (`mageflow.py`) and tests (`test_completion_hooks.py`) from `._fn` to `.fn`
- **Files modified:** `libs/mageflow/mageflow/clients/hatchet/mageflow.py`, `libs/mageflow/tests/unit/workflows/test_completion_hooks.py`
- **Commit:** `92a2733`

**2. [Rule 1 - Bug] Test used mageflow.Mageflow as class but it's a factory function**
- **Found during:** Task 1 GREEN (test `test_calls_lifecycle_from_signature_when_task_id_present`)
- **Issue:** Test tried `patch.object(mageflow.Mageflow, "_lifecycle_from_ctx", ...)` but `mageflow.Mageflow` is a factory function, not a class
- **Fix:** Removed unnecessary `patch.object` call; the real delegation test already works by patching `Signature.ClientAdapter` directly
- **Files modified:** `libs/mageflow/tests/unit/workflows/test_completion_hooks.py`
- **Commit:** `92a2733`

---

**Total deviations:** 2 auto-fixed (Rule 1 - discovered-during-implementation bugs)
**Impact on plan:** No scope change. Both were straightforward corrections to the interface documentation.

## Next Phase Readiness

- WFCMP-01, WFCMP-02, WFCMP-03 requirements fully satisfied
- Any workflow registered via `mf.workflow()` and passed to `mf.worker()` will have mageflow lifecycle callbacks automatically wired
- All 245 unit tests green

---
*Phase: 04-decorators-completion-hooks-dispatch*
*Completed: 2026-03-23*

## Self-Check: PASSED

- FOUND: `libs/mageflow/mageflow/clients/hatchet/mageflow.py`
- FOUND: `libs/mageflow/tests/unit/workflows/test_completion_hooks.py`
- FOUND: `.planning/phases/04-decorators-completion-hooks-dispatch/04-02-SUMMARY.md`
- Commits verified: 8b2be88 (RED), 92a2733 (GREEN)
- All 245 unit tests pass
