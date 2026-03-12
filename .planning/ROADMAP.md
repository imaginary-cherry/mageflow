# Roadmap: Mageflow E2E Testing Package

## Overview

Two phases deliver the complete project. Phase 1 creates the standalone `libs/mageflow-e2e/` package, wires the pytest plugin, and implements all dispatch and verification test scenarios. Phase 2 integrates the package into CI with dual-backend jobs (fakeredis and testcontainers), proving both paths are green.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Package and Tests** - Standalone e2e package with all dispatch and verification test scenarios (completed 2026-03-12)
- [ ] **Phase 2: CI Integration** - Dual-backend CI jobs running the full test suite

## Phase Details

### Phase 1: Package and Tests
**Goal**: A real user can clone the repo, run `uv sync`, and execute all dispatch and verification scenarios in `libs/mageflow-e2e/` against the fakeredis backend with zero manual configuration
**Depends on**: Nothing (first phase)
**Requirements**: PKG-01, PKG-02, PKG-03, PKG-04, PKG-05, TEST-01, TEST-02, TEST-03, TEST-04, TEST-05, TEST-06, TEST-07
**Success Criteria** (what must be TRUE):
  1. `pytest libs/mageflow-e2e/` runs without any conftest imports of mageflow internals and the `mageflow_client` fixture resolves automatically via the pytest11 entry point
  2. TaskSignature, ChainTaskSignature, and SwarmTaskSignature dispatches each have a passing test that uses only the public assertion API (`assert_task_dispatched`, `assert_swarm_dispatched`, `assert_nothing_dispatched`)
  3. Each test starts with a clean Redis state — no stale keys from previous tests — verified by `assert_nothing_dispatched` passing before any dispatch call
  4. `adapter.clear()` called mid-test resets dispatch records and subsequent `assert_nothing_dispatched` passes
  5. `@pytest.mark.mageflow(client=...)` marker override resolves a different client without error
**Plans:** 3/3 plans complete
Plans:
- [ ] 01-01-PLAN.md — Package scaffold, pyproject configs, simulated user app modules
- [ ] 01-02-PLAN.md — Task, chain, and swarm dispatch tests (TEST-01, TEST-02, TEST-03)
- [ ] 01-03-PLAN.md — Clean state and marker override tests (TEST-04, TEST-05, TEST-06, TEST-07)

### Phase 2: CI Integration
**Goal**: Both CI backend jobs are green and a PR cannot merge if either backend fails
**Depends on**: Phase 1
**Requirements**: CI-01, CI-02, CI-03
**Success Criteria** (what must be TRUE):
  1. CI runs a `e2e-fakeredis` job that executes `libs/mageflow-e2e/` tests with `MAGEFLOW_TESTING_BACKEND=fakeredis` and passes without Docker
  2. CI runs a `e2e-testcontainers` job that executes `libs/mageflow-e2e/` tests against a real `redis/redis-stack-server:7.2.0-v13` container and passes
  3. Both jobs are required checks — a failure in either blocks merge
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Package and Tests | 3/3 | Complete   | 2026-03-12 |
| 2. CI Integration | 0/TBD | Not started | - |
