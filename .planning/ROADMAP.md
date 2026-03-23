# Roadmap: Mageflow

## Milestones

- ✅ **v1.0 MVP** — Phases 1-2 (shipped 2026-03-12)
- 🚧 **v1.1 Hatchet Workflow Signatures** — Phases 3-5 (in progress)

## Phases

<details>
<summary>✅ v1.0 MVP (Phases 1-2) — SHIPPED 2026-03-12</summary>

- [x] Phase 1: Package and Tests (4/4 plans) — completed 2026-03-12
- [x] Phase 2: CI Integration (1/1 plans) — completed 2026-03-12

See: `.planning/milestones/v1.0-ROADMAP.md` for full details.

</details>

### 🚧 v1.1 Hatchet Workflow Signatures (In Progress)

**Milestone Goal:** Add WorkflowSignature support that wraps full multi-step Hatchet workflows with mageflow's signature/callback/lifecycle system, matching Hatchet's native decorator API.

- [x] **Phase 3: Core Model, Test Infrastructure, and Integration Tests** - WorkflowSignature Redis model, adapter contract, TestClientAdapter extension, and mageflow integration tests
- [ ] **Phase 4: Decorators, Completion Hooks, and Dispatch** - @mf.workflow() proxy with @workflow.task() pass-through, on_success_task/on_failure_task wiring, and HatchetClientAdapter dispatch
- [ ] **Phase 5: Composition** - WorkflowSignature works inside chains and swarms via resolve_signatures()

## Phase Details

### Phase 3: Core Model, Test Infrastructure, and Integration Tests
**Goal**: Verify that Hatchet Workflow objects work transparently through mageflow's existing TaskSignature/sign()/adapter system — no new model classes, dispatch records, or assertion methods needed
**Depends on**: Phase 2 (v1.0 complete)
**Requirements**: WFMOD-01, WFMOD-02, WFMOD-03, WFTST-01, WFTST-02, WFTST-03
**Success Criteria** (what must be TRUE):
  1. User can call `sign(workflow_obj)` and get a `TaskSignature` instance that persists to Redis with success/error callbacks and status lifecycle
  2. Workflow objects are plain TaskSignatures — chain/swarm retrieval casts succeed without modification
  3. TestClientAdapter records standard TaskDispatchRecords when a workflow is dispatched
  4. User can call `assert_task_dispatched(workflow_name)` on the test client and get a pass/fail result
  5. Adapter methods (task_name, extract_validator) work correctly with Hatchet Workflow objects
  6. Unit tests validate workflow sign, dispatch, lifecycle transitions, and assertion paths
**Plans**: 2 plans

Plans:
- [ ] 03-01-PLAN.md — Adapter compatibility tests for Workflow objects
- [x] 03-02-PLAN.md — Sign-through, dispatch, and assertion tests for Workflow objects

### Phase 4: Decorators, Completion Hooks, and Dispatch
**Goal**: Users can define and dispatch a Hatchet multi-step workflow using @mf.workflow() with @workflow.task() for steps, with automatic success/error callback activation on completion or failure
**Depends on**: Phase 3
**Requirements**: WFDEC-01, WFDEC-02, WFDEC-03, WFCMP-01, WFCMP-02, WFCMP-03, WFDSP-01, WFDSP-02
**Success Criteria** (what must be TRUE):
  1. User can define a workflow with `@mf.workflow()` using identical parameters to Hatchet's native `hatchet.workflow()` — returns a Workflow object
  2. User can define steps with `@workflow.task()` including `parents=[...]` for DAG execution order — same API as native Hatchet
  3. Dispatching a WorkflowSignature via `acall()` triggers the Hatchet workflow run with the signature ID embedded in run metadata
  4. The success callback fires exactly once after all leaf steps complete, regardless of DAG shape (including parallel leaves)
  5. When a step fails, the error callback fires; if the user defined their own on_failure handler, both the user's handler and mageflow's error callback execute
**Plans**: 2 plans

Plans:
- [ ] 04-01-PLAN.md — workflow() decorator, task def recording, and dispatch path tests
- [ ] 04-02-PLAN.md — Completion hooks injection (on_success_task/on_failure_task) in worker()

### Phase 5: Composition
**Goal**: WorkflowSignature participates in chains and swarms exactly like TaskSignature, with no special-casing at the call site
**Depends on**: Phase 4
**Requirements**: WFCPS-01, WFCPS-02, WFCPS-03
**Success Criteria** (what must be TRUE):
  1. User can pass a WorkflowSignature as a step in a ChainTaskSignature and the chain proceeds correctly after the workflow completes
  2. User can include a WorkflowSignature as an item in a SwarmTaskSignature and swarm completion tracks the workflow, not individual steps
  3. `resolve_signatures()` automatically converts a raw Hatchet Workflow object into a WorkflowSignature without the user explicitly calling `sign_workflow()`
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 3 → 4 → 5

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Package and Tests | v1.0 | 4/4 | Complete | 2026-03-12 |
| 2. CI Integration | v1.0 | 1/1 | Complete | 2026-03-12 |
| 3. Core Model, Test Infrastructure, and Integration Tests | v1.1 | 2/2 | Complete | 2026-03-23 |
| 4. Decorators, Completion Hooks, and Dispatch | v1.1 | 0/2 | Not started | - |
| 5. Composition | v1.1 | 0/? | Not started | - |
