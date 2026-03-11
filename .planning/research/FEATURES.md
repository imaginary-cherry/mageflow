# Feature Landscape

**Domain:** E2E test package for a Python task orchestration library (mageflow)
**Researched:** 2026-03-12
**Confidence:** HIGH — derived directly from codebase analysis and established pytest plugin conventions

---

## Context

This feature map is for `libs/mageflow-e2e/` — a **standalone package** that imports mageflow
as an external dependency and validates the public testing API from a real user's perspective.
The existing `mageflow.testing` module is already built and already tested internally in
`libs/mageflow/tests/testing/`. The E2E package is the missing layer that proves the *install
and configure* experience works end-to-end, including pyproject.toml-based backend switching.

The distinction is critical for complexity estimates: every API feature here is **using** the
existing API, not extending it. Complexity reflects integration difficulty, not implementation
difficulty.

---

## Table Stakes

Features users (and CI) expect. Missing = the E2E package does not serve its purpose.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| TaskSignature dispatch + `assert_task_dispatched` | Core single-task verification path; the most basic API users reach for | Low | Already tested internally; E2E just calls it from outside |
| ChainTaskSignature dispatch + `assert_task_dispatched` on first task | Chains are a primary composition primitive; users need confidence it dispatches the first task correctly | Low | Chain `.acall()` dispatches first task, not the chain container — this distinction must be explicit in E2E tests |
| SwarmTaskSignature dispatch + `assert_swarm_dispatched` | Swarms are the parallel execution primitive; second most common user pattern | Low | Swarm `.acall()` calls `afill_swarm` internally |
| `assert_nothing_dispatched` clean-state check | Users need to verify clean state before/after; table stakes for fixture isolation | Low | Already implemented; just needs to appear in E2E test suite |
| `mageflow_client` fixture provided via pytest plugin entry point | The entire value of the pytest plugin is auto-injected fixtures; if this doesn't work after `pip install mageflow`, nothing works | Medium | Tests whether `[project.entry-points.pytest11]` wiring survives an external install |
| Fixture auto-wires `TestClientAdapter` as `Signature.ClientAdapter` | If the adapter swap does not happen automatically, all dispatch recording breaks silently | Medium | Plugin fixture must replace and restore `Signature.ClientAdapter` around each test |
| Per-test Redis flush via `_mageflow_flush_redis` | Without per-test flush, records from prior tests leak into later assertions; essential for test isolation | Low | Auto-used by the existing fixture chain; E2E package inherits it via the plugin |
| pyproject.toml `[tool.mageflow.testing] backend` config is read | The entire "no env var needed" design depends on this being read from the consumer's own pyproject.toml | Medium | `_read_testing_config` walks from `rootdir`; E2E package must have its own pyproject.toml for this to work |
| `backend = "fakeredis"` config runs without Docker | CI must be able to run the fast path without Docker on every PR | Low | Uses `fakeredis.aioredis.FakeRedis`; no Docker dependency |
| `backend = "testcontainers"` config runs real Redis | CI must prove the testcontainers path also works; catches fakeredis/real-Redis divergence | Medium | Requires Docker; `AsyncRedisContainer` with `redis/redis-stack-server:7.2.0-v13` image |
| CI runs both backends via two pyproject configs | Two CI jobs must confirm both backends are green independently | Medium | Two separate pyproject files (or matrix) in the E2E package CI job |
| Partial input matching in task assertions | `assert_task_dispatched("name", {"key": val})` is the default assertion style; without this tests are brittle | Low | Already implemented in `TestClientAdapter`; E2E must exercise it |
| Exact input matching opt-in (`exact=True`) | Users need deterministic full-payload verification for security-sensitive dispatches | Low | Already implemented; just needs coverage in E2E |
| Error message clarity when assert fails | If `AssertionError` message doesn't list what *was* dispatched, debugging is painful | Low | Already implemented via `_format_diff`; E2E tests should verify error messages are useful |

---

## Differentiators

Features that make the E2E package more than a mechanical smoke test — they provide real user confidence.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Tests written as "user story" scenarios (not API surface tests) | Internal tests already cover assertion API edge cases; E2E tests should read as documentation for new users — "here is how you test your mageflow app" | Low | Naming convention: `test_user_dispatches_task_and_verifies.py`, docstrings explain the *why* |
| `[tool.mageflow.testing] client` path tested via a real client fixture | Verifies the dotted-path import mechanism works from an external package; this is the "bring your own client" path that users follow | Medium | Requires a small `myapp/` module inside the E2E package that defines a real `HatchetMageflow` client |
| Mixed dispatch tests (task + swarm + chain in one test) | Confirms that the typed views (`task_dispatches`, `swarm_dispatches`, `chain_dispatches`) filter correctly when multiple types are dispatched | Low | Mirrors real user code where a single action triggers a task then a swarm |
| `adapter.clear()` tested between dispatch sequences | Users managing long test methods need to reset mid-test; confirming `.clear()` fully resets both `_dispatches` and `_typed_dispatches` builds trust | Low | Simple to test; high documentation value |
| `@pytest.mark.mageflow(client=...)` marker override tested | Power users override the client per-test with a marker; E2E should prove this works from outside the mageflow package | Medium | Requires a second fixture path in the E2E conftest |
| `local_execution=False` verified as default (dispatch-only, no task execution) | Critical to document and verify that E2E tests do NOT execute task logic — they only verify dispatch intent | Low | Prevents confusion about what the testing API actually guarantees |
| Assertion failure messages tested as part of E2E | Validates that when a test fails in user code, the error message is actionable (lists dispatched names, shows diff) | Low | `pytest.raises(AssertionError, match=...)` pattern |

---

## Anti-Features

Features to explicitly NOT build in the E2E package.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Full round-trip callback execution (task actually runs) | Requires a live Hatchet cluster, Docker, and worker process — outside the scope of the testing API which validates dispatch intent only | Stay in dispatch+verify scope; document clearly that `local_execution=False` (default) means task logic is never executed |
| Testing the `local_execution=True` code path in E2E | Local execution is an advanced mode with its own complexity (mock run, hatchet_tasks dict) and is already tested internally | Leave local execution coverage in `libs/mageflow/tests/testing/`; E2E only uses the default dispatch-recording path |
| Performance / load testing | Not what the testing API is for; adds Docker, timing sensitivity, and flakiness | Build a separate benchmark suite if needed |
| Coverage measurement of mageflow's internals from E2E | E2E tests run against the installed package, not source; coverage of internals belongs in the mageflow unit/integration tests | Let CI coverage run from within `libs/mageflow/` as it already does |
| New assertion API surface (e.g., `assert_task_dispatched_n_times`) | E2E package consumes the API as-is; extending it belongs in mageflow, not in the E2E consumer | If a gap is found during E2E implementation, file it as a feature request against mageflow |
| Multiple Python version matrix in E2E CI | The mageflow unit tests already cover py311/312/313 × hatchet matrix; E2E adds backend dimension (fakeredis/testcontainers), not Python version dimension | Run E2E against a single Python version (3.13) per backend |
| Third-party mock libraries (pytest-mock, responses) | The testing API does not require HTTP mocking or patching; unittest.mock is sufficient for the one `@pytest.mark.mageflow` marker test | Use stdlib `unittest.mock` only if needed |
| Custom conftest fixtures that re-implement plugin fixtures | The whole point of the E2E package is to prove the *plugin fixtures* work; re-implementing them in conftest would bypass the thing being tested | The E2E conftest should be minimal — just `[tool.mageflow.testing]` in pyproject.toml and the plugin entry point does the rest |

---

## Feature Dependencies

```
pyproject.toml `[tool.mageflow.testing] backend` config read
    → backend = "fakeredis" (no Docker)
    → backend = "testcontainers" (Docker, real Redis)

pytest plugin entry point installed (pip install mageflow)
    → `mageflow_client` fixture auto-discovered
        → TestClientAdapter wired as Signature.ClientAdapter
            → TaskSignature dispatch + assert_task_dispatched
            → ChainTaskSignature dispatch + assert_task_dispatched (first task)
            → SwarmTaskSignature dispatch + assert_swarm_dispatched
            → assert_nothing_dispatched (clean state)
            → adapter.clear()

[tool.mageflow.testing] client path
    → `_load_client` imports real HatchetMageflow instance
        → MageflowTaskDefinition registered in Redis
            → input validation on dispatch (when validator != BaseModel)
            → @pytest.mark.mageflow(client=...) marker override
```

Key ordering constraint: the `_mageflow_redis_client` and `_mageflow_init_rapyer` fixtures must
be active before `mageflow_client` — the plugin fixture chain enforces this, but the E2E
package's pyproject.toml must correctly reference the backend so `_mageflow_redis_container`
initializes the right Redis client.

---

## MVP Recommendation

Prioritize:

1. **Separate package skeleton** (`libs/mageflow-e2e/`) with its own `pyproject.toml` referencing
   `mageflow` as an external dependency — this is the structural prerequisite for all other tests.

2. **TaskSignature + SwarmTaskSignature + ChainTaskSignature dispatch tests** — the three core
   dispatch paths, written as user-story scenarios (not edge case explorations). These are the
   high-confidence tests that say "the testing API works end-to-end."

3. **Dual CI job** — two `testing-e2e` CI jobs parameterized on `backend = "fakeredis"` and
   `backend = "testcontainers"` using two separate pyproject config files. This is the core
   CI value: both backends green = testing API is installable and usable.

4. **`assert_nothing_dispatched` and `adapter.clear()` tests** — minimal but critical for
   documenting fixture isolation guarantees.

Defer:

- `@pytest.mark.mageflow(client=...)` marker override: adds a real client fixture dependency
  that requires extra setup (HatchetMageflow without a live Hatchet server); can be a Phase 2
  addition once basic dispatch tests are stable.

- Assertion error message tests: valuable, but secondary to proving the happy path works from
  an external package.

---

## What Already Exists (Do Not Rebuild)

The following features are already implemented in `mageflow.testing` and already tested
in `libs/mageflow/tests/testing/`. The E2E package **uses** them, it does not implement them:

- `TestClientAdapter` with all assertion methods
- `mageflow_client` pytest fixture (plugin.py)
- Dual backend Redis fixtures (`_redis.py`)
- pyproject.toml config reader (`_config.py`)
- Partial/exact input matching logic
- `_format_diff` error messages
- `adapter.clear()`, `dispatches`, `task_dispatches`, `swarm_dispatches`, `chain_dispatches`

---

## Sources

- `libs/mageflow/mageflow/testing/_adapter.py` — TestClientAdapter full implementation (HIGH confidence)
- `libs/mageflow/mageflow/testing/plugin.py` — pytest plugin fixture wiring (HIGH confidence)
- `libs/mageflow/mageflow/testing/_redis.py` — dual backend Redis fixture logic (HIGH confidence)
- `libs/mageflow/mageflow/testing/_config.py` — pyproject.toml reader and client loader (HIGH confidence)
- `libs/mageflow/tests/testing/test_integration_user_workflow.py` — existing user workflow tests (HIGH confidence)
- `libs/mageflow/tox.ini` — existing tox envs for testing-fakeredis / testing-testcontainers (HIGH confidence)
- `.github/workflows/ci.yml` — existing `testing-tests` CI job with backend matrix (HIGH confidence)
- `.planning/PROJECT.md` — project requirements and out-of-scope definition (HIGH confidence)
- `.planning/codebase/TESTING.md` — test patterns and organization conventions (HIGH confidence)
