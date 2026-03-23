---
phase: 04-decorators-completion-hooks-dispatch
plan: "01"
subsystem: api

tags: [hatchet, workflow, decorator, dispatch, testing]

# Dependency graph
requires:
  - phase: 03-core-model-test-infrastructure
    provides: HatchetClientAdapter, MageflowWorkflow, TestClientAdapter, sign/acall dispatch path

provides:
  - HatchetMageflow.workflow() method that proxies hatchet.workflow() and records MageflowTaskDefinition
  - WorkflowOptions TypedDict for Unpack-typed **kwargs compatibility
  - Tests for WFDEC-01, WFDEC-02, WFDEC-03 (decorator behavior)
  - Tests for WFDSP-01, WFDSP-02 (dispatch path and metadata embedding)

affects:
  - 04-02 (completion hooks — needs workflow() to be established)
  - future phases using mf.workflow() for DAG definitions

# Tech tracking
tech-stack:
  added: []
  patterns:
    - WorkflowOptions TypedDict with Unpack[...] for typed kwargs pass-through
    - mf.workflow() as thin proxy recording MageflowTaskDefinition with retries=None
    - TDD RED→GREEN for both decorator and dispatch coverage

key-files:
  created:
    - libs/mageflow/tests/unit/workflows/test_workflow_decorator.py
    - libs/mageflow/tests/unit/workflows/test_workflow_dispatch_path.py
  modified:
    - libs/mageflow/mageflow/clients/hatchet/mageflow.py

key-decisions:
  - "workflow() stores raw user-supplied input_validator (not unwrapped TypeAdapter) — the user passes the raw type, which is what goes in MageflowTaskDefinition"
  - "retries=None for all mf.workflow() registrations — no workflow-level retry concept; per locked decision"
  - "WorkflowOptions TypedDict added to satisfy existing compatibility test that checks all parent params are declared or in Unpack"
  - "No adapter.py changes needed — existing HatchetClientAdapter already handles Workflow dispatch transparently"

patterns-established:
  - "Workflow registration: mf.workflow() = proxy + record, @wf.task() = pure passthrough with zero mageflow wrapping"
  - "Dispatch proof: sign(workflow_obj) + acall() + assert_task_dispatched() is the canonical test pattern"

requirements-completed: [WFDEC-01, WFDEC-02, WFDEC-03, WFDSP-01, WFDSP-02]

# Metrics
duration: 20min
completed: 2026-03-23
---

# Phase 4 Plan 01: Decorators and Dispatch Summary

**HatchetMageflow.workflow() proxy method with MageflowTaskDefinition recording (retries=None) and 19 tests proving decorator behavior and dispatch path**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-03-23T17:06:05Z
- **Completed:** 2026-03-23T17:26:00Z
- **Tasks:** 2
- **Files modified:** 3 (1 implementation, 2 test files)

## Accomplishments

- Added `HatchetMageflow.workflow()` method that proxies `hatchet.workflow()` while recording a `MageflowTaskDefinition` with `retries=None` and the raw `input_validator`
- Added `WorkflowOptions` TypedDict with `Unpack` so the method signature is compatible with the existing parameter-sanity test suite
- Proved the full dispatch path: `sign(workflow_obj)` → `acall()` → `assert_task_dispatched()` works without any adapter changes
- 19 new tests covering WFDEC-01/02/03 and WFDSP-01/02; total suite 232 tests, all passing

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: Failing decorator tests** - `9a2037a` (test)
2. **Task 1 GREEN: HatchetMageflow.workflow() implementation** - `abcf733` (feat)
3. **Task 2: Dispatch path tests** - `3de7790` (test)

## Files Created/Modified

- `libs/mageflow/mageflow/clients/hatchet/mageflow.py` - Added `workflow()` method, `WorkflowOptions` TypedDict, `Workflow` + `TaskDefaults` imports
- `libs/mageflow/tests/unit/workflows/test_workflow_decorator.py` - 11 tests covering WFDEC-01/02/03
- `libs/mageflow/tests/unit/workflows/test_workflow_dispatch_path.py` - 7 tests covering WFDSP-01/02

## Decisions Made

- Stored the raw `input_validator` type directly (not extracting from hatchet's TypeAdapter wrapper) — the user supplies the raw type, which is what belongs in `MageflowTaskDefinition`
- Used `retries=None` unconditionally — Hatchet Workflows don't have a workflow-level retry concept; task-level retries are set per `@wf.task()`
- Added `WorkflowOptions` TypedDict to satisfy the existing compatibility sanity test (which checks all parent params are declared or in Unpack) — this is a Rule 2 auto-fix
- Did not call `extract_retries()` on workflow objects (would IndexError on empty workflows with no tasks)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added WorkflowOptions TypedDict for Unpack compatibility**
- **Found during:** Task 1 (after implementing workflow() with bare `**kwargs`)
- **Issue:** Existing `test_client_signature_compatibility.py` parameterizes over all overridden Hatchet methods and checks every parent param is accepted. Bare `**kwargs` without TypedDict annotation fails the check for `description` param.
- **Fix:** Added `WorkflowOptions` TypedDict containing all `Hatchet.workflow()` kwargs (description, on_events, on_crons, version, sticky, default_priority, concurrency, task_defaults, default_filters, default_additional_metadata). Updated method to use `**kwargs: Unpack[WorkflowOptions]`.
- **Files modified:** `libs/mageflow/mageflow/clients/hatchet/mageflow.py`
- **Verification:** `test_method_accepts_all_parent_parameters_sanity[workflow]` now passes; full suite 232 tests green
- **Committed in:** `abcf733` (feat Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 2 - missing critical compatibility)
**Impact on plan:** Required for existing test infrastructure correctness. No scope creep.

## Issues Encountered

- Task 2 tests passed immediately without any implementation needed — the plan explicitly anticipated this ("No changes to adapter.py needed — existing code satisfies dispatch requirements").

## Next Phase Readiness

- `mf.workflow()` is established and tested — Phase 4 Plan 02 (completion hooks) can build on this
- The `WorkflowOptions` TypedDict provides a stable type contract for future callers
- All 232 unit tests green

---
*Phase: 04-decorators-completion-hooks-dispatch*
*Completed: 2026-03-23*

## Self-Check: PASSED

- FOUND: `libs/mageflow/mageflow/clients/hatchet/mageflow.py`
- FOUND: `libs/mageflow/tests/unit/workflows/test_workflow_decorator.py`
- FOUND: `libs/mageflow/tests/unit/workflows/test_workflow_dispatch_path.py`
- FOUND: `.planning/phases/04-decorators-completion-hooks-dispatch/04-01-SUMMARY.md`
- Commits verified: 9a2037a, abcf733, 3de7790
- All 232 unit tests pass
