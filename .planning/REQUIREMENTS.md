# Requirements: Mageflow E2E Testing Package

**Defined:** 2025-03-12
**Core Value:** Prove that the mageflow testing API works correctly from an external user's perspective with both Redis backends

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Package Setup

- [x] **PKG-01**: Standalone package at `libs/mageflow-e2e/` with own pyproject.toml, importing mageflow as external dependency
- [x] **PKG-02**: Simulated user app module (`myapp/client.py`) with HatchetMageflow instance and registered task definitions
- [x] **PKG-03**: `[tool.mageflow.testing]` config in pyproject.toml with `client` import path and `backend` setting
- [x] **PKG-04**: Two pyproject config files for CI backend switching (one with `backend = "fakeredis"`, one with `backend = "testcontainers"`)
- [x] **PKG-05**: Pytest plugin auto-discovers `mageflow_client` fixture via entry point (no manual conftest imports)

### Test Scenarios

- [ ] **TEST-01**: TaskSignature dispatch and `assert_task_dispatched` verification with partial input matching
- [ ] **TEST-02**: ChainTaskSignature dispatch and first-task dispatch verification
- [ ] **TEST-03**: SwarmTaskSignature dispatch and `assert_swarm_dispatched` verification with expected task names
- [ ] **TEST-04**: Clean state assertion via `assert_nothing_dispatched` before dispatch
- [ ] **TEST-05**: Redis is clean at the start of each test (no stale keys from previous tests)
- [ ] **TEST-06**: `adapter.clear()` mid-test reset works correctly
- [ ] **TEST-07**: `@pytest.mark.mageflow(client=...)` marker override tested from external package

### CI Integration

- [ ] **CI-01**: CI job runs E2E tests with `backend = "fakeredis"` (no Docker required)
- [ ] **CI-02**: CI job runs E2E tests with `backend = "testcontainers"` (real Redis via Docker)
- [ ] **CI-03**: Both backend jobs must pass for CI to be green

## v2 Requirements

### Extended Scenarios

- **EXT-01**: Assertion error message quality tests (verify helpful error messages on failure)
- **EXT-02**: Exact input matching (`exact=True`) test scenarios
- **EXT-03**: Mixed dispatch tests (task + swarm + chain in one test, verify typed views filter correctly)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Full round-trip callback execution | Testing API validates dispatch intent only, not task execution |
| `local_execution=True` code path | Already tested internally in libs/mageflow/tests/testing/ |
| Performance/load testing | Not the purpose of these E2E tests |
| Multiple Python version matrix | mageflow unit tests already cover py311/312/313; E2E adds backend dimension only |
| New assertion API surface | E2E consumes API as-is; extensions belong in mageflow package |
| pytest-xdist parallelism | Signature.ClientAdapter is a process global; parallel test execution unsafe |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| PKG-01 | Phase 1 | Complete |
| PKG-02 | Phase 1 | Complete |
| PKG-03 | Phase 1 | Complete |
| PKG-04 | Phase 1 | Complete |
| PKG-05 | Phase 1 | Complete |
| TEST-01 | Phase 1 | Pending |
| TEST-02 | Phase 1 | Pending |
| TEST-03 | Phase 1 | Pending |
| TEST-04 | Phase 1 | Pending |
| TEST-05 | Phase 1 | Pending |
| TEST-06 | Phase 1 | Pending |
| TEST-07 | Phase 1 | Pending |
| CI-01 | Phase 2 | Pending |
| CI-02 | Phase 2 | Pending |
| CI-03 | Phase 2 | Pending |

**Coverage:**
- v1 requirements: 15 total
- Mapped to phases: 15
- Unmapped: 0 ✓

---
*Requirements defined: 2025-03-12*
*Last updated: 2026-03-12 after roadmap creation*
