---
gsd_state_version: 1.0
milestone: v1.1
milestone_name: Hatchet Workflow Signatures
status: planning
stopped_at: Completed 04-decorators-completion-hooks-dispatch/04-02-PLAN.md
last_updated: "2026-03-23T17:17:05.794Z"
last_activity: 2026-03-23 — Roadmap created, phases 3-6 defined for v1.1
progress:
  total_phases: 3
  completed_phases: 2
  total_plans: 4
  completed_plans: 4
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-23)

**Core value:** Enable composable, callback-driven task orchestration on top of Hatchet
**Current focus:** Phase 3 — Core Model and Test Infrastructure

## Current Position

Phase: 3 of 6 (Core Model and Test Infrastructure)
Plan: — (not yet planned)
Status: Ready to plan
Last activity: 2026-03-23 — Roadmap created, phases 3-6 defined for v1.1

Progress: [░░░░░░░░░░] 0%

## Performance Metrics

**Velocity (v1.0 baseline):**
- Total plans completed: 5
- Total execution time: ~3.5 hours
- Timeline: 3 days (2026-03-10 → 2026-03-12)

**By Phase (v1.0):**

| Phase | Plans | Duration |
|-------|-------|----------|
| 1. Package and Tests | 4 | ~30 min |
| 2. CI Integration | 1 | ~3 hours |

*v1.1 metrics will be tracked as phases complete*

| Phase | Plan | Duration (min) | Tasks | Files |
|-------|------|----------------|-------|-------|
| Phase 03 | P01 | 10 | 1 | 1 |
| Phase 03 | P02 | 10 | 2 | 2 |
| Phase 04-decorators-completion-hooks-dispatch P01 | 20 | 2 tasks | 3 files |
| Phase 04-decorators-completion-hooks-dispatch P02 | 15 | 1 tasks | 2 files |

## Accumulated Context

### Decisions

See PROJECT.md Key Decisions table for full list.

Key v1.1 decisions locked in during research:
- WorkflowSignature subclasses TaskSignature (not Signature) to preserve chain/swarm retrieval cast validity
- on_success_task used for completion detection (not leaf-step wrapping) — fires exactly once for any DAG shape
- on_failure_task composed with user's handler (not replaced) — single Hatchet slot constraint
- WorkflowDispatchRecord created in Phase 3 (not Phase 6) to avoid false test confidence
- [Phase 03]: No new adapter code needed — existing HatchetClientAdapter methods already work with Workflow objects
- [Phase 03]: Bare Workflow with no tasks raises IndexError in extract_retries — documented as test, not fixed (deferred per CONTEXT.md)
- [Phase 03]: Workflow without input_validator returns EmptyModel from extract_validator (not None) — documented accurately in test
- [Phase 03 P02]: Used hatchet_adapter fixture pattern to set/restore Signature.ClientAdapter for workflow sign tests — avoids cross-test pollution
- [Phase 03 P02]: test_workflow_dispatch.py uses session-scoped mageflow plugin fixtures with loop_scope=session
- [Phase 04-decorators-completion-hooks-dispatch]: workflow() stores raw user-supplied input_validator with retries=None; WorkflowOptions TypedDict added for Unpack compatibility; no adapter changes needed for dispatch
- [Phase 04-decorators-completion-hooks-dispatch]: Task.fn (not Task._fn) is the correct hatchet-sdk attribute for Task's wrapped function
- [Phase 04-decorators-completion-hooks-dispatch]: _inject_workflow_hooks() uses decorator API for new hooks, Task.fn replacement for composing with user handlers

### Pending Todos

None.

### Blockers/Concerns

None — research complete at HIGH confidence. All SDK APIs verified against hatchet-sdk 1.23.4 source.

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 1 | Fix testing tests after move to unit.tests | 2026-03-17 | 35dc958 | quick/1-fix-testing-tests-after-move-to-unit-tes/ |
| 2 | Refactor mageflow-e2e to use real Hatchet and Redis init | 2026-03-17 | 9b137b6 | quick/2-refactor-mageflow-e2e-to-use-real-redis-/ |

## Session Continuity

Last session: 2026-03-23T17:17:05.792Z
Stopped at: Completed 04-decorators-completion-hooks-dispatch/04-02-PLAN.md
Resume file: None
