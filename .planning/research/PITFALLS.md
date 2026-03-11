# Domain Pitfalls

**Domain:** E2E test package for a Python task-orchestration library (mageflow)
**Researched:** 2026-03-12
**Confidence:** HIGH — derived directly from codebase inspection, existing test failures, and known patterns in the CONCERNS.md and TESTING.md source files.

---

## Critical Pitfalls

Mistakes that cause rewrites, silent test passes, or undetectable regressions.

---

### Pitfall 1: Plugin Fires in the Wrong Package's rootdir

**What goes wrong:**
`_config.py::_find_pyproject()` resolves `pyproject.toml` from `request.config.rootdir`,
then falls back to `Path.cwd()`. When the E2E package runs pytest from
`libs/mageflow-e2e/`, rootdir is determined by pytest's ini-file search, NOT by
where `pytest` was invoked. If the E2E package's `pyproject.toml` has no
`[tool.pytest.ini_options]` section, pytest walks up and may anchor rootdir to the
monorepo root, reading the wrong `[tool.mageflow.testing]` block (from
`libs/mageflow/pyproject.toml` or the workspace root). The backend would be resolved
from mageflow's own config instead of the E2E package's config, making the CI
backend-switching mechanism silently broken.

**Why it happens:**
pytest rootdir discovery uses the first `pyproject.toml`, `setup.cfg`, or `tox.ini`
it finds walking up from the collected paths. Without an explicit `[tool.pytest.ini_options]`
anchor, the monorepo root wins.

**Consequences:**
- CI backend matrix says "fakeredis" but tests run with testcontainers (or vice versa)
- Tests pass both runs regardless of backend, masking dual-backend coverage
- Impossible to debug from test output alone

**Prevention:**
Add `[tool.pytest.ini_options]` with at least `testpaths = ["tests"]` to
`libs/mageflow-e2e/pyproject.toml`. This forces pytest to anchor rootdir to the
E2E package directory, making `_find_pyproject()` resolve the correct file.

**Detection (warning signs):**
- `pytest --co -q` from `libs/mageflow-e2e/` shows a rootdir that is not
  `libs/mageflow-e2e/`
- Backend selection in test output never changes across CI matrix runs
- Both `fakeredis` and `testcontainers` CI jobs take the same elapsed time

**Phase:** Phase 1 (package scaffold and CI wiring)

---

### Pitfall 2: Pytest Plugin Auto-Loaded into E2E Package's Own Test Runner

**What goes wrong:**
`mageflow` registers `mageflow.testing.plugin` via `[project.entry-points.pytest11]`.
When the E2E package installs mageflow as a dependency and runs pytest, the plugin
loads automatically — which is the desired behaviour. However, if the E2E package
also vendors or re-exports any conftest that re-imports plugin fixtures (`_mageflow_redis_client`,
`_mageflow_flush_redis`, etc.) for test-internal reasons, pytest will discover
those fixtures TWICE: once from the plugin and once from the conftest. This causes
`ScopeMismatch` errors or fixture shadowing where the conftest copy silently wins.

**Why it happens:**
The existing `libs/mageflow/tests/testing/conftest.py` explicitly re-exports
private fixtures from `_redis.py` at module level for pytest discovery.
Copying that pattern into the E2E package's conftest while the plugin is also
active creates duplicate fixture registrations.

**Consequences:**
- `ScopeMismatch: You tried to access the function scoped fixture ... with a session scoped request object`
- The wrong fixture (function-scoped conftest copy vs. session-scoped plugin fixture) wins non-deterministically
- Tests pass locally (where plugin may not be installed in dev mode) but fail in CI

**Prevention:**
The E2E package's conftest must contain NO fixture definitions for any fixture
already provided by the plugin. Only write conftest fixtures that are E2E-specific
(e.g., a `mageflow_client` override using a custom client path). Validate by running
`pytest --fixtures | grep _mageflow` from the E2E directory and confirming each
fixture appears exactly once.

**Detection (warning signs):**
- `pytest --fixtures` shows duplicate fixture names with different scope lines
- `ScopeMismatch` errors on `_mageflow_redis_client` or `_mageflow_init_rapyer`
- Tests pass when run individually but fail when the full suite runs

**Phase:** Phase 1 (package scaffold)

---

### Pitfall 3: Session-Scoped Redis is Not Flushed Between Tests — Signatures Bleed Across Tests

**What goes wrong:**
The plugin uses `_mageflow_redis_client` at `scope="session"` and
`_mageflow_flush_redis` at `scope="function"`. However, `_mageflow_flush_redis`
runs `flushdb()` AFTER the test (teardown), not before. If a prior test crashes
mid-run without yielding, the flush never happens, and the next test inherits
stale Redis state: keys from prior `mageflow.asign()`, `mageflow.aswarm()`,
or `mageflow.achain()` calls remain.

In E2E tests, signatures are created with human-readable names (e.g., `"process-order"`).
If a prior test created a `TaskSignature` with that name but crashed before cleanup,
the next test's `await mageflow.asign("process-order", ...)` may resolve against
the stale key in Redis, producing a different signature object than expected.
The dispatch assertion then passes against stale data, not the fresh dispatch.

**Why it happens:**
`_mageflow_flush_redis` uses `yield` with no try/finally: flush happens in teardown
only. A hard abort (KeyboardInterrupt, test worker crash) skips teardown.

**Consequences:**
- Non-deterministic test failures that only appear after prior test failures
- `assert record.task_name == "process-order"` passes against a stale record
- Impossible to reproduce from a clean run

**Prevention:**
Add a pre-test flush in the E2E conftest's `mageflow_client` fixture or add
`autouse=True` async fixture that calls `await redis_client.flushdb()` in setup
(before yield), not just in teardown. Pre-test flush is the safe pattern.

Example:
```python
@pytest_asyncio.fixture(autouse=True, scope="function", loop_scope="session")
async def _flush_before_test(_mageflow_redis_client):
    await _mageflow_redis_client.flushdb()
    yield
```

**Detection (warning signs):**
- Tests fail only when run in full suite order, pass in isolation
- Assertion error says "Task X was dispatched" when it should not be
- Running `pytest --randomly-seed=0` produces different failures than without

**Phase:** Phase 1 (fixture setup)

---

### Pitfall 4: `Signature.ClientAdapter` Global Mutation Is Not Thread/Coroutine Safe

**What goes wrong:**
`plugin.py` patches `Signature.ClientAdapter` (a class-level attribute) to the
`TestClientAdapter` instance and restores it in a finally block. This is a global
mutation. In the E2E package, tests use `loop_scope="session"` which shares a
single asyncio event loop across all tests. If two async tests run concurrently
(e.g., if `asyncio.gather` is used inside a test, or if a future version of
pytest-asyncio enables concurrent test execution), one test's adapter patch
overwrites another's, and dispatch records end up in the wrong adapter instance.

In the current single-test-at-a-time model this does not cause failures, but it
is an invisible fragility that will manifest with any parallelism.

**Why it happens:**
`Signature.ClientAdapter` is a class-level attribute acting as a process-global
singleton. The patch/restore pattern works only when tests are strictly sequential.

**Consequences:**
- With `pytest-xdist` workers, every worker races to set the global adapter
- With `asyncio.gather` inside a test, nested dispatches go to the outer test's adapter
- Silent data mixing: assertions pass against another test's dispatches

**Prevention:**
- Never use `pytest-xdist` with the testing package without explicitly excluding the
  E2E tests or using `--dist=no`
- Do not use `asyncio.gather` in test bodies with multiple dispatch operations unless
  you verify the adapter is thread-local or the test is single-adapter
- Document this constraint explicitly in the E2E package README or conftest header
- Future mitigation: use context-var-based adapter lookup instead of class attribute

**Detection (warning signs):**
- `len(mageflow_client.task_dispatches)` is unexpectedly high (received another test's records)
- Assertion for "my-task" finds a record but `record.task_name` is from a different test
- Failures only appear when running with `-n auto` or `pytest-xdist`

**Phase:** Phase 1 (fixture setup); document constraint explicitly

---

### Pitfall 5: `assert_chain_dispatched` Tests Against Chain Completion, Not Chain Initiation

**What goes wrong:**
The comment in `_adapter.py` line 457 states this explicitly: "This asserts chain
*completion* (when `acall_chain_done` fired), not chain initiation." In E2E tests,
calling `chain_sig.acall(...)` dispatches the FIRST task in the chain, not the chain
callback. `assert_chain_dispatched("order-pipeline")` will then fail because no
`ChainDispatchRecord` was added — only a `TaskDispatchRecord` for `"validate-order"`.

The existing integration test (`test_dispatch_chain_and_verify`) in
`test_integration_user_workflow.py` correctly avoids this by only asserting
`assert_task_dispatched("validate-order")` after `chain_sig.acall(...)`. But this
is a non-obvious trap for anyone writing new E2E chain tests.

**Why it happens:**
`acall_chain_done` is a callback hook, not a direct dispatch path. The chain's
callback is only triggered when the last chain task completes — which requires a
live worker and real Hatchet execution, both out of scope for E2E dispatch tests.

**Consequences:**
- `assert_chain_dispatched("order-pipeline")` always raises `AssertionError: Chain 'order-pipeline' was not dispatched`
- Test author interprets this as a bug in the testing API rather than a misunderstanding of the abstraction
- Time wasted debugging correct code

**Prevention:**
For chain dispatch E2E tests, use `assert_task_dispatched` for the first task in
the chain. Reserve `assert_chain_dispatched` only for tests that exercise the
full callback flow (out of E2E scope). Add a comment at the top of the chain test
file explaining the distinction.

**Detection (warning signs):**
- `AssertionError: Chain '...' was not dispatched. Dispatched chains: []` even
  though the chain was called
- `mageflow_client.chain_dispatches` is empty after `chain_sig.acall(...)`
- But `mageflow_client.task_dispatches` contains the first chain task

**Phase:** Phase 1 (test authoring)

---

## Moderate Pitfalls

---

### Pitfall 6: testcontainers Backend Fails in CI Without Docker Socket

**What goes wrong:**
The `testcontainers` backend requires Docker to be available. In CI environments
that use rootless Docker, Docker-in-Docker, or Podman, the `AsyncRedisContainer`
may fail to start with a cryptic `DockerException: Error while fetching server API
version`. The CI matrix runs both `fakeredis` and `testcontainers` backends, so
only the `testcontainers` job fails, which could be misdiagnosed as a test bug.

**Prevention:**
In the CI job for `testcontainers` backend, add a Docker availability check step
before running tests:
```yaml
- name: Verify Docker
  run: docker info
```
This surfaces the infrastructure issue before pytest starts, rather than inside a
pytest fixture traceback.

**Detection (warning signs):**
- CI `testcontainers` job fails with `DockerException` or `ConnectionRefusedError`
  in fixture setup, not in a test body
- `fakeredis` CI job passes cleanly

**Phase:** Phase 2 (CI integration)

---

### Pitfall 7: pyproject.toml Backend Config Not Read Because Package Is Installed, Not Run From Source

**What goes wrong:**
`_find_pyproject()` looks for `pyproject.toml` at `rootdir` (from pytest) then
falls back to `Path.cwd()`. When the E2E package is installed with `pip install .`
(not `pip install -e .`), there is no `pyproject.toml` in the installed package
tree — the file stays in the source directory. If pytest is run from a directory
other than `libs/mageflow-e2e/` (e.g., the repo root), `Path.cwd()` won't find
the E2E package's `pyproject.toml`. The `backend` key is never read, defaulting
to `testcontainers` even for the `fakeredis` matrix job.

**Prevention:**
Always install the E2E package in editable mode (`pip install -e .`) in CI so
that `rootdir` resolves to `libs/mageflow-e2e/`. Alternatively, set
`MAGEFLOW_TESTING_BACKEND` as an environment variable in the CI job
(the env var takes priority over pyproject.toml per `_get_backend()`). Using the
env var is the more explicit and robust CI approach.

**Detection (warning signs):**
- `testcontainers` backend is used even in the `fakeredis` CI job
- Removing Docker from the runner causes the `fakeredis` job to fail

**Phase:** Phase 2 (CI integration)

---

### Pitfall 8: Task Name Collisions Across Tests Due to Shared Redis Without Namespace Isolation

**What goes wrong:**
All tests share a single Redis database (session-scoped client). `mageflow.asign("process-order", ...)`
creates a key in that database. If two different tests create a signature with
the same `task_name` string, the second `asign()` call may find or update the first
test's existing key (depending on rapyer's `ainsert`/`afind_one` semantics).
The signature returned will be the same Redis key, meaning both tests share a
`TaskSignature` object. When the first test's adapter is restored
(`Signature.ClientAdapter = original_adapter`), dispatches from the second test
go to the wrong adapter.

**Prevention:**
Use unique task names in each test, including the test method name as a suffix:
```python
sig = await mageflow.asign(f"process-order-{uuid.uuid4().hex[:8]}", ...)
```
Or rely on the flush-before-test pattern (Pitfall 3) to prevent cross-test key leakage.

**Detection (warning signs):**
- `assert len(mageflow_client.task_dispatches) == 1` fails with count 2+
- A record appears for a task name that was never dispatched in the current test

**Phase:** Phase 1 (test authoring)

---

### Pitfall 9: E2E Package pyproject.toml Installs mageflow Without the `testing` Extra

**What goes wrong:**
The `mageflow.testing` module and its pytest plugin are available only when
`mageflow[testing]` is installed (the `testing` optional-dependencies group
provides `testcontainers`, `pytest`, `pytest-asyncio`, and `fakeredis`). If the
E2E package's `pyproject.toml` lists `mageflow` (without `[testing]`) as a
dependency, the plugin will not be installed. Pytest will silently skip the
`mageflow_client` fixture because the entry point was never registered, and
tests will fail with `fixture 'mageflow_client' not found`.

**Prevention:**
List `mageflow[testing]` (bracket notation) as a dependency in the E2E package's
`pyproject.toml`. Verify plugin registration with:
```bash
pytest --co -q 2>&1 | grep mageflow
```
This should show the plugin being loaded.

**Detection (warning signs):**
- `fixture 'mageflow_client' not found` error on every test
- `pytest --fixtures` does not list `mageflow_client` or `_mageflow_redis_client`

**Phase:** Phase 1 (package scaffold)

---

## Minor Pitfalls

---

### Pitfall 10: `loop_scope="session"` Requires All Async Fixtures in the Chain to Be Session-Scoped

**What goes wrong:**
`mageflow_client` is declared `scope="function"` with `loop_scope="session"`.
If any async fixture it depends on is declared `scope="session"` WITHOUT
`loop_scope="session"`, pytest-asyncio 1.2+ will raise a scope mismatch warning
or error. The E2E package's conftest must mirror the scope declarations from the
plugin exactly, or it will get confusing errors about event loop cleanup.

**Prevention:**
Every `@pytest_asyncio.fixture` that is `scope="session"` must include
`loop_scope="session"`. Copy the scope declarations from `plugin.py` and `_redis.py`
verbatim. Do not mix scopes.

**Detection (warning signs):**
- `ScopeMismatch` errors mentioning event loop or `loop_scope`
- `DeprecationWarning: There is no current event loop` during fixture setup

**Phase:** Phase 1 (fixture setup)

---

### Pitfall 11: `assert_swarm_dispatched` Does a Subset Check, Not an Exact Check — Empty Swarms Pass Silently

**What goes wrong:**
`assert_swarm_dispatched("my-swarm", expected_task_names=["resize-image"])` passes
even if the swarm has 10 tasks — it is a subset check. If a bug causes extra tasks
to be added to the swarm, the assertion does not catch it. Conversely, if the
`try/except` in `afill_swarm` falls back to `task_names = []` (see `_adapter.py`
lines 277-279), the assertion also passes when `expected_task_names` is `None`
because name-only matching succeeded. An empty `task_names` list is a real bug
(sub-tasks not resolved from Redis) but is invisible to a name-only assertion.

**Prevention:**
Always provide `expected_task_names` when asserting swarm dispatches in E2E tests.
Additionally assert `len(record.task_names) == N` to catch both empty lists and
unexpected extras:
```python
record = mageflow_client.assert_swarm_dispatched(
    "image-processing",
    expected_task_names=["resize-image", "compress-image"],
)
assert len(record.task_names) == 2  # exact count guard
```

**Detection (warning signs):**
- `record.task_names == []` after a successful `assert_swarm_dispatched`
- Tests pass with empty swarms when tasks should have been resolved

**Phase:** Phase 1 (test authoring)

---

### Pitfall 12: `_mageflow_redis_container` Fixture Is session-Scoped — testcontainers Container Stays Up for Entire Suite

**What goes wrong:**
With `scope="session"`, the Redis container starts once and never restarts between
tests. This is correct for performance but means a Redis crash or OOM during the
session kills all remaining tests with opaque connection errors. On GitHub Actions
with a 7 GB memory limit, a large E2E suite that creates many signatures without
cleanup can cause Redis to exhaust memory mid-session.

**Prevention:**
Keep the E2E test suite small (under 30 tests, each creating under 10 signatures).
Add post-test cleanup via the flush fixture (Pitfall 3 prevention). Do not run
load or stress scenarios in the E2E package.

**Detection (warning signs):**
- `ConnectionRefusedError` or `redis.exceptions.ConnectionError` midway through the suite
- Container health check fails after the 10th test

**Phase:** Phase 2 (CI integration)

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Package scaffold (`libs/mageflow-e2e/pyproject.toml`) | Missing `[tool.pytest.ini_options]` causes rootdir to anchor at monorepo root (Pitfall 1) | Add minimal pytest ini section anchoring rootdir |
| Package scaffold | `mageflow` without `[testing]` extra (Pitfall 9) | Use `mageflow[testing]` in dependencies |
| Fixture setup (conftest.py) | Re-exporting plugin fixtures causes duplicates (Pitfall 2) | Conftest imports nothing from `_redis.py`; plugin provides all fixtures |
| Fixture setup | No pre-test flush allows stale Redis keys (Pitfall 3) | Add autouse fixture that flushes before yield |
| Test authoring — chain tests | `assert_chain_dispatched` called after `acall()` (Pitfall 5) | Use `assert_task_dispatched` for first chain task |
| Test authoring — swarm tests | Name-only swarm assertion hides empty task lists (Pitfall 11) | Always assert `len(record.task_names) == N` |
| Test authoring — task naming | Shared task names bleed across tests (Pitfall 8) | Use unique names or rely on pre-test flush |
| CI wiring — backend switching | testcontainers backend without env var backup (Pitfall 7) | Set `MAGEFLOW_TESTING_BACKEND` env var in CI job |
| CI wiring — Docker availability | testcontainers job fails silently at fixture layer (Pitfall 6) | Add `docker info` pre-check step |
| Parallelism / future work | Global `Signature.ClientAdapter` mutation breaks under xdist (Pitfall 4) | Never add `pytest-xdist` to E2E package; document constraint |

---

## Sources

All findings derived from direct codebase inspection (MEDIUM-HIGH confidence):

- `/Users/yedidyakfir/Documents/Research/mageflow/libs/mageflow/mageflow/testing/_adapter.py` — adapter implementation and assertion logic
- `/Users/yedidyakfir/Documents/Research/mageflow/libs/mageflow/mageflow/testing/plugin.py` — pytest plugin, fixture scopes, ClientAdapter patching
- `/Users/yedidyakfir/Documents/Research/mageflow/libs/mageflow/mageflow/testing/_redis.py` — Redis fixture scopes and flush timing
- `/Users/yedidyakfir/Documents/Research/mageflow/libs/mageflow/mageflow/testing/_config.py` — pyproject.toml config loading and rootdir resolution
- `/Users/yedidyakfir/Documents/Research/mageflow/libs/mageflow/pyproject.toml` — entry-point registration, optional extras
- `/Users/yedidyakfir/Documents/Research/mageflow/libs/mageflow/tests/testing/test_integration_user_workflow.py` — reference E2E workflow patterns
- `/Users/yedidyakfir/Documents/Research/mageflow/.planning/codebase/CONCERNS.md` — known bugs, fragile areas, test coverage gaps
- `/Users/yedidyakfir/Documents/Research/mageflow/.planning/codebase/TESTING.md` — existing test patterns and backend configuration
- `/Users/yedidyakfir/Documents/Research/mageflow/libs/mageflow/tox.ini` — tox envs and backend env var usage
- `/Users/yedidyakfir/Documents/Research/mageflow/.github/workflows/ci.yml` — CI matrix structure
