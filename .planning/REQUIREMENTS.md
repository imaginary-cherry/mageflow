# Requirements: Mageflow

**Defined:** 2026-03-23
**Core Value:** Enable composable, callback-driven task orchestration on top of Hatchet

## v1.1 Requirements

Requirements for Hatchet Workflow Signatures milestone. Each maps to roadmap phases.

### Core Model

- [x] **WFMOD-01**: User can create a WorkflowSignature from a Hatchet Workflow object via `sign_workflow()`
- [x] **WFMOD-02**: WorkflowSignature persists to Redis with success/error callbacks, status lifecycle, and TTL
- [x] **WFMOD-03**: WorkflowSignature subclasses TaskSignature so chain/swarm retrieval casts work correctly

### Decorators

- [x] **WFDEC-01**: User can define a workflow with `@mf.workflow()` using the same parameters as Hatchet's `hatchet.workflow()`
- [x] **WFDEC-02**: User can define workflow steps with `@workflow.task()` using the same parameters as native Hatchet (mageflow's workflow object passes through to Hatchet's task decorator)
- [x] **WFDEC-03**: Steps can declare parent dependencies via `parents=[...]` for DAG execution order

### Completion & Error Handling

- [x] **WFCMP-01**: Success callbacks activate exactly once when all workflow leaf steps complete via `on_success_task`
- [x] **WFCMP-02**: Error callbacks activate when any workflow step fails via `on_failure_task`
- [x] **WFCMP-03**: If user defines their own `on_failure` handler, mageflow wraps it — both mageflow's error callback and user's handler execute

### Dispatch

- [x] **WFDSP-01**: User can dispatch a WorkflowSignature via `acall()` which triggers the Hatchet workflow run
- [x] **WFDSP-02**: Workflow run carries signature ID in metadata so completion/error hooks can resolve the signature

### Composition

- [ ] **WFCPS-01**: User can include a WorkflowSignature as a step in a ChainTaskSignature
- [ ] **WFCPS-02**: User can include a WorkflowSignature as an item in a SwarmTaskSignature
- [ ] **WFCPS-03**: `resolve_signatures()` converts Hatchet Workflow objects to WorkflowSignature automatically

### Testing

- [x] **WFTST-01**: TestClientAdapter records workflow dispatches as WorkflowDispatchRecord
- [x] **WFTST-02**: User can verify workflow dispatch via `assert_task_dispatched()` (standard TaskDispatchRecord path)
- [x] **WFTST-03**: Mageflow integration tests validate workflow dispatch and assertion paths

## Future Requirements

### v1.x (after v1.1 stabilizes)

- **WFMCP-01**: WorkflowSignature exposed in mageflow-mcp server for AI agent dispatch
- **WFSKP-01**: Per-step `was_skipped()` handling in success callback for conditional branches

### v2+

- **WFSUS-01**: Mid-run workflow suspension/resumption (requires Hatchet native pause)
- **WFOBS-01**: Per-step intermediate callbacks for observability dashboards

## Out of Scope

| Feature | Reason |
|---------|--------|
| Per-step mageflow callbacks on intermediate steps | Multiplies Redis operations by step count; workflow output is the leaf output |
| Automatic workflow cancellation on `suspend()` | Hatchet cancel is irreversible; no pause primitive exists |
| Multiple `on_failure_task` handlers | Hatchet SDK raises ValueError; single slot is a hard constraint |
| Serializing all step return values in Redis | Use Hatchet's own run storage; Redis holds only final combined leaf output |
| Dynamic step registration after workflow definition | Breaks static topology analysis; use SwarmTaskSignature for dynamic work |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| WFMOD-01 | Phase 3 | Complete |
| WFMOD-02 | Phase 3 | Complete |
| WFMOD-03 | Phase 3 | Complete |
| WFTST-01 | Phase 3 | Complete |
| WFTST-02 | Phase 3 | Complete |
| WFDEC-01 | Phase 4 | Complete |
| WFDEC-02 | Phase 4 | Complete |
| WFDEC-03 | Phase 4 | Complete |
| WFCMP-01 | Phase 4 | Complete |
| WFCMP-02 | Phase 4 | Complete |
| WFCMP-03 | Phase 4 | Complete |
| WFDSP-01 | Phase 4 | Complete |
| WFDSP-02 | Phase 4 | Complete |
| WFCPS-01 | Phase 5 | Pending |
| WFCPS-02 | Phase 5 | Pending |
| WFCPS-03 | Phase 5 | Pending |
| WFTST-03 | Phase 3 | Complete |

**Coverage:**
- v1.1 requirements: 17 total
- Mapped to phases: 17
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-23*
*Last updated: 2026-03-23 — Traceability aligned to phases 3-6*
