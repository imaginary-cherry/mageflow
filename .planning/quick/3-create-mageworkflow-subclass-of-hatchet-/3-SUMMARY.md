---
phase: quick-3
plan: "01"
subsystem: mageflow-hatchet-client
tags: [refactor, workflow, hooks, encapsulation]
dependency_graph:
  requires: []
  provides: [MageWorkflow class with self-injecting lifecycle hooks]
  affects:
    - libs/mageflow/mageflow/clients/hatchet/workflow.py
    - libs/mageflow/mageflow/clients/hatchet/mageflow.py
    - libs/mageflow/tests/unit/workflows/test_completion_hooks.py
tech_stack:
  added: []
  patterns:
    - Subclass wrapping for encapsulated hook injection
    - TYPE_CHECKING guard for circular import avoidance
key_files:
  created: []
  modified:
    - libs/mageflow/mageflow/clients/hatchet/workflow.py
    - libs/mageflow/mageflow/clients/hatchet/mageflow.py
    - libs/mageflow/tests/unit/workflows/test_completion_hooks.py
decisions:
  - MageWorkflow.__init__ uses __dict__.update(base_wf.__dict__) to copy all state from the base Workflow returned by hatchet.workflow()
  - TYPE_CHECKING guard used for HatchetMageflow forward reference in workflow.py to avoid circular imports
  - _lifecycle_from_ctx on MageWorkflow delegates to self._mageflow._lifecycle_from_ctx(ctx), so patching type(mf)._lifecycle_from_ctx in tests still works correctly
  - patch.object(type(mf), "_lifecycle_from_ctx") in tests still targets HatchetMageflow, which MageWorkflow delegates to — no test restructuring needed for lifecycle patches
metrics:
  duration_minutes: 3
  completed_date: "2026-03-23"
  tasks_completed: 3
  files_modified: 3
---

# Quick Task 3: Create MageWorkflow Subclass of Hatchet Workflow — Summary

**One-liner:** Extracted on_success/on_failure hook injection from `HatchetMageflow._inject_workflow_hooks` into a new `MageWorkflow(Workflow)` subclass with a self-contained `_inject_hooks()` method.

## What Was Done

Refactored mageflow's lifecycle hook wiring so workflows are self-contained. Previously, `HatchetMageflow._inject_workflow_hooks(wf)` was called externally in `worker()` to mutate each passed workflow. Now, `MageWorkflow` encapsulates that logic internally.

## Tasks Completed

| Task | Description | Commit |
|------|-------------|--------|
| 1 | Add MageWorkflow class to workflow.py | 2c1aa36 |
| 2 | Refactor HatchetMageflow, update tests | 671a4ad |
| 3 | Full unit test suite — no regressions | (verification only) |

## Changes

### `libs/mageflow/mageflow/clients/hatchet/workflow.py`

Added `MageWorkflow(Workflow)` class before the existing `MageflowWorkflow`:
- `__init__(self, base_workflow, mageflow)` — copies base workflow state via `__dict__.update`, stores `_mageflow` ref
- `_lifecycle_from_ctx(ctx)` — delegates to `self._mageflow._lifecycle_from_ctx(ctx)`
- `_inject_hooks()` — contains the full on_success/on_failure composition logic (moved from `HatchetMageflow._inject_workflow_hooks`)
- Uses `from __future__ import annotations` + `TYPE_CHECKING` guard to avoid circular import with `mageflow.py`

`MageflowWorkflow` (dispatch serialization class) is completely unchanged.

### `libs/mageflow/mageflow/clients/hatchet/mageflow.py`

- Added import: `from mageflow.clients.hatchet.workflow import MageWorkflow`
- `workflow()` return type changed from `Workflow` to `MageWorkflow`; wraps the `base_wf` from `hatchet.workflow()` in `MageWorkflow(base_wf, mageflow=self)`
- `worker()` loop changed from `self._inject_workflow_hooks(wf)` to `if isinstance(wf, MageWorkflow): wf._inject_hooks()`
- Removed `_inject_workflow_hooks()` method entirely
- Removed unused `Workflow` from `hatchet_sdk.runnables.workflow` import

### `libs/mageflow/tests/unit/workflows/test_completion_hooks.py`

- All `mf._inject_workflow_hooks(test_workflow)` calls replaced with `test_workflow._inject_hooks()`
- `TestWorkerIntegration.test_worker_injects_hooks_before_super` updated: spy is now on `test_workflow._inject_hooks` (instance method monkey-patch), checking the workflow ends up in `injected` list
- Added `MageWorkflow` import
- All patches `patch.object(type(mf), "_lifecycle_from_ctx", ...)` remain unchanged — they target `HatchetMageflow._lifecycle_from_ctx` which MageWorkflow delegates to

## Test Results

- 254 unit tests passed, 0 failures, 8 warnings
- 28 client adapter tests passed
- No regressions from the refactoring

## Deviations from Plan

None — plan executed exactly as written. The recommended "SIMPLEST strategy" was used: `__dict__.update` to copy base workflow state into MageWorkflow.

## Self-Check: PASSED

- `MageWorkflow` class exists in `libs/mageflow/mageflow/clients/hatchet/workflow.py` with `_inject_hooks()` method
- `MageflowWorkflow` dispatch class unchanged
- `HatchetMageflow._inject_workflow_hooks` removed
- `HatchetMageflow.workflow()` returns `MageWorkflow`
- `HatchetMageflow.worker()` calls `wf._inject_hooks()` for `MageWorkflow` instances
- All unit tests pass: 254/254
