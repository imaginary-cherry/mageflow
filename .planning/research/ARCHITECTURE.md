# Architecture Patterns

**Domain:** E2E test package for a Python task orchestration library
**Researched:** 2026-03-12

## Recommended Architecture

The `mageflow-e2e` package is a **user-simulation package**, not a traditional test suite. Its architectural contract is: "act exactly as a downstream user of mageflow would." This means the package must treat mageflow as an installed external library, configure everything through the public API, and never reach into mageflow internals. Every design decision flows from that constraint.

```
libs/mageflow-e2e/
├── pyproject.toml                  # declares mageflow as dependency, configures [tool.mageflow.testing]
├── pyproject-fakeredis.toml        # CI variant: backend = "fakeredis"
├── pyproject-testcontainers.toml   # CI variant: backend = "testcontainers"
├── tox.ini                         # or pytest.ini — test runner config
├── myapp/
│   ├── __init__.py
│   └── client.py                   # HatchetMageflow instance for [tool.mageflow.testing].client
└── tests/
    ├── conftest.py                  # empty or project-level overrides only
    ├── test_task_dispatch.py
    ├── test_chain_dispatch.py
    └── test_swarm_dispatch.py
```

The `myapp/` package is the simulated user application. It defines the `HatchetMageflow` client instance that the pytest plugin loads via `[tool.mageflow.testing] client = "myapp.client:mageflow_client"`. Tests use only `mageflow_client` fixture and the public assertion API.

### Component Boundaries

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| `pyproject.toml` (primary) | Declares mageflow dependency, configures testing backend | Consumed by pytest plugin via `_read_testing_config()` |
| `pyproject-fakeredis.toml` | CI variant — overrides `backend = "fakeredis"` | Passed to pytest as `--override-ini` or copied over primary |
| `pyproject-testcontainers.toml` | CI variant — overrides `backend = "testcontainers"` | Same |
| `myapp/client.py` | Holds a `HatchetMageflow` instance with task defs registered | Loaded by pytest plugin via `_load_client()` |
| `tests/test_*.py` | Test functions using `mageflow_client` fixture | Receives `TestClientAdapter` from plugin |
| `mageflow.testing.plugin` (external) | Auto-discovers fixtures via pytest11 entry point | Reads pyproject.toml, creates `TestClientAdapter`, manages Redis lifecycle |
| `mageflow.testing._redis` (external) | Manages Redis fixture lifecycle (container or fakeredis) | Driven by `backend` key from pyproject.toml |

No component in `mageflow-e2e` imports from `mageflow.testing` directly. The pytest plugin is auto-loaded by pytest via the entry point registered in mageflow's pyproject.toml. This is the key boundary: the E2E package is a consumer, not a collaborator.

### Data Flow

**Configuration resolution (session start):**

```
libs/mageflow-e2e/pyproject.toml
  [tool.mageflow.testing]
  backend = "fakeredis"
  client = "myapp.client:mageflow_client"
         |
         v
pytest plugin: _mageflow_testing_config fixture (session scope)
  _read_testing_config(rootdir) → reads pyproject.toml → returns dict
         |
         v (backend key)                  (client key)
_mageflow_redis_container            _load_client("myapp.client:mageflow_client")
  "fakeredis" → FakeRedis                  → importlib loads myapp.client
  "testcontainers" → Docker Redis          → reads ._task_defs from instance
         |                                        |
         v                                        v
_mageflow_redis_client                  MageflowTaskDefinition.ainsert() per task_def
         |                                        |
         +----------------+-----------------------+
                          v
               mageflow_client fixture
               creates TestClientAdapter(task_defs=..., local_execution=...)
               injects as Signature.ClientAdapter (global swap)
                          |
                          v
               test function receives adapter
               creates signatures → calls acall() → records dispatches
               asserts via assert_task_dispatched / assert_swarm_dispatched / assert_chain_dispatched
                          |
                          v (teardown)
               Signature.ClientAdapter restored to original
               Redis flushed via _mageflow_flush_redis
```

**CI backend switching flow:**

```
CI matrix: backend in [fakeredis, testcontainers]
         |
         v (two approaches, pick one — see below)

Approach A — env var override (simpler):
  tox setenv: MAGEFLOW_TESTING_BACKEND = fakeredis
  _get_backend() in _redis.py checks env var first → bypasses pyproject.toml
  No duplicate pyproject files needed

Approach B — dual pyproject files (explicit, matches PROJECT.md intent):
  CI step copies pyproject-fakeredis.toml → pyproject.toml before running pytest
  Plugin reads pyproject.toml → gets backend value
  CI step copies pyproject-testcontainers.toml → pyproject.toml for second run
```

The existing codebase already supports both approaches. `_get_backend()` checks `MAGEFLOW_TESTING_BACKEND` env var first, then falls back to pyproject.toml. The env var approach is simpler for CI; dual pyproject files validate the pyproject.toml config path specifically.

### Build Order (Component Dependencies)

```
1. myapp/client.py
   - Depends on: mageflow installed (external dep)
   - Must exist before any test can run
   - Needs at least one task definition registered on the client

2. pyproject.toml (primary)
   - Depends on: myapp package importable
   - Sets: client path, backend, optional local_execution
   - Must be syntactically valid TOML before pytest discovers it

3. pyproject-fakeredis.toml + pyproject-testcontainers.toml
   - Depends on: primary pyproject.toml structure
   - These are CI-only variants, not needed for local dev

4. tests/test_*.py
   - Depends on: mageflow_client fixture (provided by plugin automatically)
   - Depends on: myapp signatures being importable from test scope

5. tox.ini / CI job
   - Depends on: all above
   - Orchestrates backend switching via env var or file copy
```

## Patterns to Follow

### Pattern 1: Auto-injected fixtures via pytest entry point
**What:** mageflow registers `mageflow = "mageflow.testing.plugin"` under `[project.entry-points.pytest11]`. Pytest loads this as a plugin for any project that has mageflow installed. Fixtures like `mageflow_client` are available to all tests automatically — no conftest import needed.
**When:** Any test file in mageflow-e2e that requests `mageflow_client` will get it.
**Example:**
```python
# tests/test_task_dispatch.py — no imports from mageflow.testing needed
async def test_dispatch_task(mageflow_client):
    task_sig = await mageflow.asign("my-task", model_validators=BaseModel)
    await task_sig.acall({"key": "value"})
    mageflow_client.assert_task_dispatched("my-task", {"key": "value"})
```

### Pattern 2: Client registration in user application module
**What:** The simulated user application has a module (`myapp/client.py`) that creates a `HatchetMageflow` instance and decorates tasks on it. The plugin loads this instance to extract task definitions for input validation.
**When:** Required when the test needs input validation or local execution mode.
**Example:**
```python
# myapp/client.py
from mageflow import Mageflow

mageflow_client = Mageflow()  # or HatchetMageflow directly

@mageflow_client.task()
async def process_order(context, input: OrderInput) -> dict:
    ...
```
```toml
# pyproject.toml
[tool.mageflow.testing]
client = "myapp.client:mageflow_client"
backend = "fakeredis"
```

### Pattern 3: Backend isolation via env var
**What:** CI sets `MAGEFLOW_TESTING_BACKEND=fakeredis` or `testcontainers` as environment variable. The plugin reads this before pyproject.toml, so no file manipulation is needed between CI runs.
**When:** CI matrix with multiple backends. Simpler than dual pyproject files.
**Example (tox.ini):**
```ini
[testenv:e2e-fakeredis]
setenv = MAGEFLOW_TESTING_BACKEND = fakeredis
commands = pytest tests/

[testenv:e2e-testcontainers]
setenv = MAGEFLOW_TESTING_BACKEND = testcontainers
commands = pytest tests/
```

### Pattern 4: Per-test adapter reset (function scope)
**What:** `mageflow_client` fixture is function-scoped. Redis is flushed after each test via `_mageflow_flush_redis`. The `TestClientAdapter` is created fresh per test. This guarantees test isolation even though the Redis client and container are session-scoped.
**When:** All tests. Do not use session or module scope for `mageflow_client`.

## Anti-Patterns to Avoid

### Anti-Pattern 1: Importing mageflow.testing internals
**What:** Test files or conftest.py importing from `mageflow.testing._adapter`, `mageflow.testing._redis`, etc.
**Why bad:** The leading underscore signals private API. A real user would not import these. Importing them defeats the purpose of E2E validation — you would be bypassing the public entry point.
**Instead:** Use only `mageflow_client` fixture (injected by plugin) and the public assertion API on it.

### Anti-Pattern 2: Registering fixtures manually in conftest.py
**What:** Defining `_mageflow_redis_container`, `_mageflow_init_rapyer`, etc. in conftest.py by re-importing from `mageflow.testing._redis`.
**Why bad:** This is how `libs/mageflow/tests/testing/conftest.py` does it — because that is a test of the testing internals, not an external consumer. In mageflow-e2e, the plugin handles fixture registration automatically. Adding them to conftest.py creates duplicates and hides whether the auto-discovery path works.
**Instead:** Empty conftest.py (or minimal pytest-asyncio mode config only). Trust the entry point.

### Anti-Pattern 3: Shared mageflow_client across tests
**What:** Elevating `mageflow_client` fixture to module or session scope to reduce overhead.
**Why bad:** The adapter accumulates dispatches. Shared state across tests means early-test dispatches pollute later-test assertions. A test that calls `assert_nothing_dispatched()` would fail spuriously.
**Instead:** Keep fixture function-scoped. The Redis flush happens per test. The overhead is negligible (adapter is pure Python, no network).

### Anti-Pattern 4: Testing mageflow internals from mageflow-e2e
**What:** Tests that reach into `Signature.ClientAdapter`, `SignatureLifecycle`, or other internal objects.
**Why bad:** Breaks the external-user simulation. Also creates import coupling that would require mageflow's internal packages to be explicitly installed as a test dependency.
**Instead:** Scope every assertion to the `TestClientAdapter` public API: `assert_task_dispatched`, `assert_chain_dispatched`, `assert_swarm_dispatched`, `assert_nothing_dispatched`, and the typed `task_dispatches` / `swarm_dispatches` / `chain_dispatches` properties.

## Scalability Considerations

| Concern | Now (small E2E suite) | Later (larger suite) |
|---------|----------------------|---------------------|
| Test isolation | Function-scoped adapter + Redis flush per test | Same — already correct pattern |
| CI time (testcontainers) | Container starts once per CI job (session scope) | Consider pre-warming image in CI runner or using service containers |
| Backend parity | Run both fakeredis and testcontainers backends in CI | Consider adding a `pytest.mark.backend` marker if some tests need backend-specific validation |
| Multiple client configurations | Single pyproject.toml client reference | Could use `@pytest.mark.mageflow(client="...")` per-test marker override (already supported by plugin) |
| Task definition sprawl in myapp/ | One client.py with all tasks | Split into myapp/tasks/task.py, myapp/tasks/chain.py, myapp/tasks/swarm.py — mirrors real user project layout |

## Key Constraints That Drive Architecture

**Constraint 1: rootdir determines pyproject.toml lookup.**
The plugin calls `_read_testing_config(request.config.rootdir)`. Pytest rootdir is resolved from `pyproject.toml` / `pytest.ini` location. The E2E package's `pyproject.toml` must be at `libs/mageflow-e2e/pyproject.toml`, and pytest must be invoked from that directory (or with that as rootdir) for the plugin to read the correct config.

**Constraint 2: Entry point registration requires mageflow installed.**
The pytest11 entry point is declared in `libs/mageflow/pyproject.toml`. For CI, mageflow must be installed via `pip install ./libs/mageflow[testing]` (not in editable mode from the monorepo workspace) to validate the external-user scenario. If tox handles this with `deps = ../mageflow`, the entry point is registered correctly.

**Constraint 3: `local_execution` mode requires hatchet task objects.**
If tests want actual task function execution (not just dispatch recording), `TestClientAdapter` needs `hatchet_tasks` populated. This requires `[tool.mageflow.testing] local_execution = true` and the `HatchetMageflow` client to have tasks decorated. For this E2E scope (dispatch + verify only), `local_execution = false` is correct per PROJECT.md.

## Sources

- `libs/mageflow/mageflow/testing/_config.py` — pyproject.toml reading logic, rootdir resolution
- `libs/mageflow/mageflow/testing/_redis.py` — Redis fixture lifecycle, env var vs pyproject.toml backend selection
- `libs/mageflow/mageflow/testing/plugin.py` — mageflow_client fixture, client loading, adapter injection
- `libs/mageflow/mageflow/testing/_adapter.py` — TestClientAdapter public API surface
- `libs/mageflow/pyproject.toml` — entry point declaration (`[project.entry-points.pytest11]`)
- `libs/mageflow/tox.ini` — how existing testing-fakeredis / testing-testcontainers tox envs work
- `libs/mageflow/tests/testing/conftest.py` — existing internal test pattern (which E2E must NOT mirror)
- `libs/mageflow/tests/testing/test_integration_user_workflow.py` — usage patterns that E2E tests emulate
- `.planning/PROJECT.md` — project scope and constraints

*All findings HIGH confidence — derived directly from codebase source files.*
