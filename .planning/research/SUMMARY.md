# Project Research Summary

**Project:** mageflow-e2e — E2E test package for mageflow public API
**Domain:** Standalone Python test package (external consumer validation)
**Researched:** 2026-03-12
**Confidence:** HIGH

## Executive Summary

This project creates `libs/mageflow-e2e/`, a standalone Python package that imports `mageflow` as an external dependency and validates its public testing API from a real downstream user's perspective. The key insight from research is that the `mageflow.testing` module is already fully implemented and internally tested — the E2E package is not building features, it is proving the *install and configure* experience works end-to-end, including pytest plugin auto-discovery, pyproject.toml-based backend switching, and dual-backend Redis coverage. Every design decision must maintain the strict external-user boundary: no imports from private `mageflow.testing._*` modules, no conftest fixtures that shadow plugin fixtures, no direct patching of `Signature.ClientAdapter`.

The recommended approach is a minimal package scaffold (`pyproject.toml` with `mageflow[testing]` dependency and `[tool.mageflow.testing]` config, a `myapp/client.py` simulating a user application, and a lean `tests/` directory) combined with two CI jobs parameterized on the `MAGEFLOW_TESTING_BACKEND` env var. Tests should be written as user-story scenarios, not edge-case explorations, to serve as living documentation for new mageflow users. All complexity in this project is integration complexity — wiring the package correctly — not implementation complexity.

The primary risks are configuration and scoping traps: pytest rootdir anchoring at the monorepo root instead of `libs/mageflow-e2e/` (silently breaking backend switching), duplicate fixture registration if any conftest re-exports plugin fixtures, and stale Redis state from post-test-only flush timing. All three are preventable with one-time setup decisions and are well-understood from the existing codebase. The `assert_chain_dispatched` vs `assert_task_dispatched` chain API distinction is the most likely test-authoring mistake and needs explicit documentation in the test files.

---

## Key Findings

### Recommended Stack

All versions are verified directly from `uv.lock` and existing `pyproject.toml` files in the repo — no guessing required. The E2E package uses the same toolchain as the rest of the monorepo: hatchling as build backend, pytest 9 with pytest-asyncio 1.x in `asyncio_mode = "auto"`, and both fakeredis and testcontainers backends pinned to the same ranges as `mageflow`'s own `testing` extra. The only non-obvious requirement is `redis/redis-stack-server:7.2.0-v13` for the testcontainers backend (plain `redis:7` lacks the RedisJSON module that rapyer requires).

**Core technologies:**
- pytest `>=9.0.2,<10.0.0`: test runner — standard across all libs, mageflow plugin targets this range
- pytest-asyncio `>=1.2.0,<2.0.0`: async fixture support — `loop_scope="session"` required for session-scoped Redis lifecycle
- fakeredis `>=2.34.0,<3.0.0` with `[json,lua]` extras: in-memory Redis — fast path, no Docker, required for local dev and fast CI
- testcontainers `>=4.14.0,<5.0.0` with `[redis]`: real Redis via Docker — parity testing, mandatory for production-confidence CI
- mageflow installed with `[testing]` extra from workspace: system under test — must include `[testing]` extra or the pytest11 entry point is not registered
- hatchling: build backend — consistent with all three existing libs

**Key version constraints:**
- `asyncio_mode = "auto"` + `asyncio_default_fixture_loop_scope = "session"` required in `[tool.pytest.ini_options]`
- Redis image must be `redis/redis-stack-server:7.2.0-v13`, not plain `redis:7`
- `mageflow[testing]` (bracket notation), not plain `mageflow`

### Expected Features

Research confirms a clear two-tier MVP: the core dispatch+verify loop, and the CI backend matrix. Everything else is secondary or explicitly deferred.

**Must have (table stakes):**
- TaskSignature dispatch + `assert_task_dispatched` — core single-task verification path; the most basic user workflow
- SwarmTaskSignature dispatch + `assert_swarm_dispatched` — parallel execution primitive; second most common pattern
- ChainTaskSignature dispatch + `assert_task_dispatched` on first task — chain initiation test (not `assert_chain_dispatched`, which requires live Hatchet execution)
- `assert_nothing_dispatched` clean-state check — essential for documenting fixture isolation guarantees
- `mageflow_client` fixture auto-wired via pytest11 entry point — the entire value proposition of the plugin; if this doesn't work after install, nothing works
- Per-test Redis flush — test isolation prerequisite; inherited from plugin's `_mageflow_flush_redis` fixture
- pyproject.toml `[tool.mageflow.testing] backend` config read correctly — the no-env-var design depends on this
- Dual CI jobs for fakeredis and testcontainers backends — the core CI deliverable

**Should have (differentiators):**
- Tests written as user-story scenarios with explanatory docstrings — serves as onboarding documentation for new mageflow users
- Partial input matching + exact matching (`exact=True`) exercised in tests — proves the assertion API is usable end-to-end
- `adapter.clear()` tested mid-test — documents reset contract for users managing long test methods
- Mixed dispatch tests (task + swarm + chain in one test) — proves typed dispatch views filter correctly

**Defer to v2+:**
- `@pytest.mark.mageflow(client=...)` marker override — adds real client fixture dependency; stable after basic dispatch tests are green
- Assertion error message quality tests — valuable but secondary to proving the happy path
- `local_execution=True` mode — already tested internally; keep out of E2E scope

**Explicitly out of scope (anti-features):**
- Full round-trip callback execution (requires live Hatchet cluster)
- Performance/load testing
- Multiple Python version matrix (mageflow unit tests already cover py311/312/313)
- Custom conftest that re-implements plugin fixtures

### Architecture Approach

The architecture is driven by a single constraint: act exactly as a downstream user of mageflow would. This means the package never imports from `mageflow.testing._*` private modules, never re-exports plugin fixtures in conftest, and configures everything through the public `[tool.mageflow.testing]` pyproject.toml key. The `myapp/` sub-package simulates the user's application by holding a `HatchetMageflow` instance with registered task definitions — this is what the plugin loads via the `client = "myapp.client:mageflow_client"` config key.

**Major components:**
1. `libs/mageflow-e2e/pyproject.toml` — declares `mageflow[testing]` dependency, anchors pytest rootdir, configures testing backend; this file is the primary interface between the E2E package and the mageflow plugin
2. `libs/mageflow-e2e/myapp/client.py` — simulated user application; holds `HatchetMageflow` instance with task definitions; loaded by plugin via `_load_client()`
3. `libs/mageflow-e2e/tests/test_*.py` — user-story test scenarios; use only `mageflow_client` fixture and public assertion API; no imports from mageflow internals
4. CI backend matrix (env var `MAGEFLOW_TESTING_BACKEND`) — two jobs (fakeredis, testcontainers) that independently validate the full install+configure+test path
5. `mageflow.testing.plugin` (external, auto-loaded) — wires `TestClientAdapter`, manages Redis lifecycle, restores `Signature.ClientAdapter` after each test; the E2E package trusts this entirely

### Critical Pitfalls

1. **pytest rootdir anchors at monorepo root instead of `libs/mageflow-e2e/`** — add `[tool.pytest.ini_options]` with `testpaths = ["tests"]` to force rootdir anchor; without this, `_find_pyproject()` reads the wrong backend config silently
2. **Duplicate fixture registration from conftest re-exporting plugin fixtures** — keep conftest empty or minimal; any fixture already in the plugin must not appear in conftest; validate with `pytest --fixtures | grep _mageflow`
3. **No pre-test Redis flush allows stale keys from crashed prior tests** — add autouse `scope="function"` fixture that calls `await redis_client.flushdb()` before yield, not just after
4. **`assert_chain_dispatched` called after `chain_sig.acall()`** — `acall()` dispatches the first chain task, not the chain container; use `assert_task_dispatched` for chain initiation tests; `assert_chain_dispatched` requires live Hatchet worker execution
5. **`mageflow` installed without `[testing]` extra** — entry point is not registered; `mageflow_client` fixture not found; always use `mageflow[testing]` in dependencies

---

## Implications for Roadmap

### Phase 1: Package Scaffold and Fixture Wiring

**Rationale:** All tests depend on the package structure being correct. The rootdir pitfall, entry-point registration, and conftest isolation are foundational — getting them wrong makes every subsequent test invalid without obvious error messages.

**Delivers:** A runnable `libs/mageflow-e2e/` package with the pytest plugin loading correctly, Redis backend initializing, and a single smoke test passing on both backends.

**Addresses:** Table-stakes features — `mageflow_client` fixture auto-discovery, `[tool.mageflow.testing] backend` config read, per-test Redis flush.

**Avoids:**
- Pitfall 1 (rootdir): `[tool.pytest.ini_options]` anchor in pyproject.toml
- Pitfall 2 (duplicate fixtures): empty conftest
- Pitfall 3 (stale Redis): pre-test flush autouse fixture
- Pitfall 9 (missing extra): `mageflow[testing]` dependency
- Pitfall 10 (loop_scope): correct `asyncio_default_fixture_loop_scope = "session"` config

**Stack elements:** hatchling, pytest 9, pytest-asyncio 1.x, fakeredis (initial backend), uv workspace integration

### Phase 2: Core Dispatch Test Scenarios

**Rationale:** Once the scaffold is correct, the three dispatch paths (task, swarm, chain) and clean-state verification are the minimum E2E coverage that proves the testing API is usable.

**Delivers:** User-story test scenarios for TaskSignature, SwarmTaskSignature, ChainTaskSignature dispatch, and `assert_nothing_dispatched` — written with explanatory docstrings that serve as onboarding documentation.

**Addresses:** All table-stakes dispatch features, partial/exact input matching, `adapter.clear()` mid-test reset.

**Avoids:**
- Pitfall 5 (chain assertion): use `assert_task_dispatched` for first chain task, not `assert_chain_dispatched`
- Pitfall 8 (task name collisions): unique task names per test or pre-test flush reliance
- Pitfall 11 (empty swarm silent pass): always assert `len(record.task_names) == N` after `assert_swarm_dispatched`

**Stack elements:** thirdmagic signatures (TaskSignature, ChainTaskSignature, SwarmTaskSignature), pydantic BaseModel for input validation, `myapp/client.py` with registered task definitions

### Phase 3: CI Integration (Dual Backend Matrix)

**Rationale:** The CI matrix is the primary deliverable of this project — proving both backends are green is the signal that the install+configure+test experience works for a real user.

**Delivers:** Two CI jobs (`e2e-fakeredis` and `e2e-testcontainers`) in the GitHub Actions workflow, both green. The `MAGEFLOW_TESTING_BACKEND` env var approach is simpler and more robust than dual pyproject files for CI.

**Addresses:** Dual CI backend coverage, testcontainers real-Redis validation.

**Avoids:**
- Pitfall 6 (Docker not available): `docker info` pre-check step before tests
- Pitfall 7 (pyproject.toml not found in CI): use `MAGEFLOW_TESTING_BACKEND` env var in CI job (takes precedence over pyproject.toml per `_get_backend()`)
- Pitfall 12 (Redis OOM mid-session): keep suite under 30 tests with pre-test flush

**Stack elements:** testcontainers with `redis/redis-stack-server:7.2.0-v13`, GitHub Actions matrix, `MAGEFLOW_TESTING_BACKEND` env var

### Phase 4: Extended Scenarios (Deferred)

**Rationale:** Once the core loop is stable and CI is green, additional coverage (marker override, error message quality, mixed-type dispatch) adds confidence without blocking the primary goal.

**Delivers:** `@pytest.mark.mageflow(client=...)` marker override test, assertion error message quality tests, mixed-dispatch scenario (task + swarm + chain in one test).

**Addresses:** Differentiator features from FEATURES.md.

**Avoids:**
- Pitfall 4 (global adapter mutation): never add `pytest-xdist`; document constraint in conftest header

### Phase Ordering Rationale

- Phase 1 before Phase 2: the rootdir and fixture pitfalls are invisible — tests appear to run but validate the wrong thing; scaffolding must be verified first
- Phase 2 before Phase 3: need at least one working test before adding the CI complexity of backend switching
- Phase 3 is effectively CI work on top of Phase 2 tests — minimal new test authoring, mostly YAML and env var wiring
- Phase 4 is additive and does not block any other phase; defer without risk

### Research Flags

Phases with standard patterns (skip research-phase, all patterns are well-documented in the existing codebase):
- **Phase 1:** Package scaffold pattern is established from three existing libs; pyproject.toml structure is directly derivable from `libs/mageflow/pyproject.toml`
- **Phase 2:** Test authoring patterns are exemplified in `test_integration_user_workflow.py`; no novel API to research
- **Phase 3:** CI pattern is established in `.github/workflows/ci.yml`; env var backend switching is already implemented in `_redis.py`
- **Phase 4:** Marker override is already supported by the plugin; implementation is straightforward once Phase 1-3 are stable

No phase needs a `research-phase` step — all patterns and APIs are resolved from the existing codebase with HIGH confidence.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All versions verified from `uv.lock` and `pyproject.toml`; no guessing |
| Features | HIGH | Derived from full codebase inspection; existing `test_integration_user_workflow.py` shows the exact patterns |
| Architecture | HIGH | Package boundary constraint is explicit; component responsibilities are directly derivable from plugin source |
| Pitfalls | HIGH | Derived from direct codebase inspection of `_redis.py`, `_config.py`, `plugin.py`, and known bugs in CONCERNS.md |

**Overall confidence:** HIGH

### Gaps to Address

- **`myapp/client.py` HatchetMageflow instantiation without live Hatchet server:** The client object is used only for task definition extraction (not actual workflow execution), but the constructor may require connection config. This needs validation during Phase 1 implementation — if the constructor connects eagerly, a mock or lazy-init pattern is needed. Check `HatchetMageflow.__init__` before writing `myapp/client.py`.
- **Entry point registration in uv workspace (editable install):** Pytest11 entry points are registered at install time. With uv workspace editable installs, entry point registration behavior may differ from a standard `pip install -e .`. Verify with `pytest --co -q 2>&1 | grep mageflow` immediately after `uv sync` in Phase 1.
- **`_mageflow_flush_redis` fixture access from E2E conftest for pre-test flush:** The pre-test flush autouse fixture (Pitfall 3 prevention) needs `_mageflow_redis_client`, which is a private plugin fixture. Accessing it from the E2E conftest without importing from `_redis.py` requires that pytest fixture injection still works via name. Verify this is the case before relying on it.

---

## Sources

### Primary (HIGH confidence)
- `libs/mageflow/mageflow/testing/_adapter.py` — full TestClientAdapter implementation and assertion logic
- `libs/mageflow/mageflow/testing/plugin.py` — pytest plugin fixture wiring, ClientAdapter patching
- `libs/mageflow/mageflow/testing/_redis.py` — Redis fixture lifecycle, env var vs pyproject.toml backend selection
- `libs/mageflow/mageflow/testing/_config.py` — pyproject.toml reading, rootdir resolution
- `libs/mageflow/pyproject.toml` — entry point declaration, `testing` optional-dependencies group
- `libs/mageflow/tox.ini` — testing-fakeredis / testing-testcontainers env pattern
- `libs/mageflow/tests/testing/test_integration_user_workflow.py` — reference E2E workflow patterns
- `libs/mageflow/tests/testing/conftest.py` — internal test pattern that E2E must NOT mirror
- `uv.lock` — exact resolved versions for all packages
- `.planning/PROJECT.md` — project scope, constraints, out-of-scope definition
- `.planning/codebase/CONCERNS.md` — known bugs, fragile areas
- `.planning/codebase/TESTING.md` — test patterns and backend configuration
- `.github/workflows/ci.yml` — CI matrix structure

### Secondary (MEDIUM confidence)
- `.planning/research/STACK.md`, `FEATURES.md`, `ARCHITECTURE.md`, `PITFALLS.md` — synthesized research files (this document is their integration)

---
*Research completed: 2026-03-12*
*Ready for roadmap: yes*
