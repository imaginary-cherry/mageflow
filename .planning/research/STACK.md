# Technology Stack

**Project:** mageflow-e2e — E2E test package for mageflow public API
**Researched:** 2026-03-12
**Confidence:** HIGH (all versions verified from uv.lock and pyproject.toml in this repo)

---

## Context

This is a **standalone test package** (`libs/mageflow-e2e/`) that installs `mageflow` as an
external dependency and exercises its public testing API exactly as a downstream user would.
The package does not test mageflow internals — it validates the external contract.

The mageflow testing API already exists and works:
- `TestClientAdapter` records Task/Chain/Swarm dispatches
- `mageflow_client` fixture auto-registers via `[project.entry-points.pytest11]`
- Dual Redis backends: `testcontainers` (real Docker Redis) and `fakeredis` (in-memory)
- Backend selected via `[tool.mageflow.testing] backend = ...` in consuming package's `pyproject.toml`

The E2E package's job is to **consume** that API from a clean external package, proving it
works exactly as documented for a real user.

---

## Recommended Stack

### Test Runner

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| pytest | `>=9.0.2,<10.0.0` | Test discovery, execution, reporting | Already the standard across all libs in this repo; v9 is stable and current; mageflow's pytest plugin targets this range |
| pytest-asyncio | `>=1.2.0,<2.0.0` | Async test and fixture support | Already used; v1.2+ provides `loop_scope="session"` which is required for session-scoped async fixtures (Redis container lifecycle) |

**Configuration required** in `pyproject.toml`:
```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "session"
```

`asyncio_mode = "auto"` eliminates the need for `@pytest.mark.asyncio` on every test method.
`asyncio_default_fixture_loop_scope = "session"` prevents per-test event loop teardown which
would destroy the session-scoped Redis container between tests.

### Build Backend

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| hatchling | latest (via `[build-system]`) | Package build backend | Used by all three existing libs (mageflow, thirdmagic, mageflow-mcp); consistent with the monorepo pattern |

### Redis Test Backends

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| fakeredis[json,lua] | `>=2.34.0,<3.0.0` | In-memory Redis without Docker | Pinned to same range as mageflow's `testing` extra; `json` and `lua` extras required because mageflow uses JSON module commands and Lua scripts via rapyer |
| testcontainers[redis] | `>=4.14.0,<5.0.0` | Real Redis via Docker for CI | Pinned to same range as mageflow's `testing` extra; `AsyncRedisContainer` provides async Redis client directly |

**Which to use:** Both. The E2E package must run against each backend independently. Two
`pyproject.toml` files control which backend is active in CI (via `[tool.mageflow.testing]`
`backend = ...`), matching the existing tox pattern for `testing-fakeredis` /
`testing-testcontainers` environments.

### Core Dependencies (runtime of the system under test)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| mageflow | installed from `libs/mageflow` | System under test | Installed as an editable local dependency, not a PyPI release, so changes propagate immediately; must be installed with `[testing]` extra to pull in pytest plugin, fakeredis, testcontainers |
| thirdmagic | installed from `libs/third-magic` | Core signatures (TaskSignature, ChainTaskSignature, SwarmTaskSignature) | Transitive dependency of mageflow; needed for constructing test data |
| rapyer | `>=1.2.5,<1.3.0` | Redis-backed models (transitive) | Used internally by mageflow for signature storage; the E2E package does not interact with it directly but it must be present |
| pydantic | `>=2.0.0,<3.0.0` | BaseModel for task input validation | Used in every test to define task inputs; mageflow validates inputs against pydantic models |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| coverage[toml] | `>=7.0.0,<8.0.0` | Coverage measurement (optional) | If coverage reporting is desired for E2E tests; not strictly required given E2E scope |

### Code Quality (dev only)

| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| black | `>=26.1.0` | Formatter | Enforced in CI lint job; must match version used by rest of repo |
| ruff | `>=0.15.5` | Import sorter + linter | Enforced in CI lint job; `select = ["I", "F401"]` per repo root `pyproject.toml` |

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Build backend | hatchling | setuptools, flit | Hatchling is already used by all three libs; consistency matters in a monorepo; setuptools adds no value here |
| Backend switching | Two pyproject.toml files | env var `MAGEFLOW_TESTING_BACKEND` | Both work; pyproject.toml approach is more explicit and self-documenting — the CI matrix shows what each job is testing without reading env var injection logic. The env var fallback exists in the plugin and can be used in development, but pyproject.toml is the CI contract |
| Async framework | pytest-asyncio | anyio, trio | pytest-asyncio is what mageflow itself uses; using a different event loop backend would create incompatibility with async fixtures provided by the mageflow plugin |
| Redis images | `redis/redis-stack-server:7.2.0-v13` | `redis:7`, `redis:latest` | `redis-stack-server` includes the RedisJSON module required by rapyer's JSON commands. Using plain `redis:7` would cause JSON command failures in testcontainers backend. This is the exact image used in `mageflow/testing/_redis.py` |

---

## pyproject.toml Structure

The E2E package needs **two** pyproject.toml files — one base plus one variant — or a
single file that CI overrides with `MAGEFLOW_TESTING_BACKEND`. The cleanest approach (per
PROJECT.md) is two separate files:

**`libs/mageflow-e2e/pyproject.toml`** (fakeredis backend, default for local dev):
```toml
[project]
name = "mageflow-e2e"
version = "0.1.0"
requires-python = ">=3.10,<3.14"
dependencies = []

[project.optional-dependencies]
dev = [
    "pytest>=9.0.2,<10.0.0",
    "pytest-asyncio>=1.2.0,<2.0.0",
    "fakeredis[json,lua]>=2.34.0,<3.0.0",
    "testcontainers[redis]>=4.14.0,<5.0.0",
    "pydantic>=2.0.0,<3.0.0",
    "black>=26.1.0",
    "ruff>=0.15.5",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["mageflow_e2e"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "session"

[tool.mageflow.testing]
backend = "fakeredis"

[tool.ruff.lint]
select = ["I", "F401"]
```

**`libs/mageflow-e2e/pyproject-testcontainers.toml`** (testcontainers backend, used by CI):
Identical except `backend = "testcontainers"`. CI invokes pytest with
`--override-ini=...` or by temporarily copying the file, or by using the env var
`MAGEFLOW_TESTING_BACKEND=testcontainers` (which takes precedence per `_redis.py`).

The simplest CI approach is to use the env var for the testcontainers run since the
env var override is already supported by the plugin — no file copying required.

---

## uv Workspace Integration

```toml
# Root pyproject.toml — add mageflow-e2e to workspace members
[tool.uv.workspace]
members = ["libs/mageflow", "libs/third-magic", "libs/mageflow-mcp", "libs/mageflow-e2e"]
```

Install in E2E package's pyproject.toml:
```toml
[tool.uv.sources]
mageflow = { workspace = true }
thirdmagic = { workspace = true }
```

This mirrors the pattern used by `libs/mageflow/pyproject.toml` for `thirdmagic`. The E2E
package gets mageflow from the local workspace, not PyPI.

---

## Installation

```bash
# From repo root — install E2E package with dev extras
uv sync

# Run E2E tests with fakeredis backend (no Docker required)
cd libs/mageflow-e2e
MAGEFLOW_TESTING_BACKEND=fakeredis pytest tests/ -v

# Run E2E tests with testcontainers backend (Docker required)
MAGEFLOW_TESTING_BACKEND=testcontainers pytest tests/ -v
```

---

## What NOT to Use

| Avoid | Why |
|-------|-----|
| `tox` for E2E env matrix | tox adds env-isolation complexity for a focused package with only 2 backend variants; GitHub Actions matrix with env var `MAGEFLOW_TESTING_BACKEND` is sufficient and simpler |
| `pytest-xdist` for parallelism | E2E tests share a session-scoped Redis container; parallel test execution would create fixture ordering conflicts and race conditions on the adapter's global `Signature.ClientAdapter` |
| `anyio` / `trio` backends | mageflow uses asyncio throughout; mixing event loop backends introduces compatibility risk |
| Separate `tests/e2e/` inside existing libs | Defeats the purpose — the whole point is to import mageflow as if it were a published package, forcing the external-user perspective |
| Mocking the Redis client | E2E tests must use real backends (fakeredis or testcontainers) to validate that the plugin's backend switching actually works end-to-end |

---

## Version Pins Summary

All versions verified from `uv.lock` (locked 2026-03-12) and `pyproject.toml` files:

| Package | Exact resolved version | Range to specify |
|---------|----------------------|-----------------|
| pytest | 9.0.2 | `>=9.0.2,<10.0.0` |
| pytest-asyncio | 1.3.0 | `>=1.2.0,<2.0.0` |
| fakeredis | 2.34.0 | `>=2.34.0,<3.0.0` |
| testcontainers | 4.14.1 | `>=4.14.0,<5.0.0` |
| pydantic | 2.12.5 | `>=2.0.0,<3.0.0` |
| rapyer (transitive) | 1.2.5 | managed by mageflow/thirdmagic |
| hatchet-sdk (transitive) | 1.23.4 | managed by mageflow |
| black | 26.1.0 | `>=26.1.0` |
| ruff | 0.15.5 | `>=0.15.5` |

---

## Confidence Assessment

| Decision | Confidence | Basis |
|----------|------------|-------|
| pytest + pytest-asyncio versions | HIGH | Verified from uv.lock; matches existing mageflow pinning |
| fakeredis version | HIGH | Verified from uv.lock; matches mageflow `testing` extra |
| testcontainers version | HIGH | Verified from uv.lock; matches mageflow `testing` extra |
| `redis-stack-server:7.2.0-v13` image | HIGH | Used in production fixtures in `_redis.py` |
| hatchling build backend | HIGH | Used by all three existing libs |
| `asyncio_mode = "auto"` + `loop_scope = "session"` | HIGH | Required by pytest-asyncio 1.x for session-scoped async fixtures; pattern confirmed in `_redis.py` and `plugin.py` |
| env var approach for CI backend switching | HIGH | `_get_backend()` in `_redis.py` explicitly checks `MAGEFLOW_TESTING_BACKEND` first |
| Two-pyproject-file alternative | MEDIUM | Viable but adds file-management overhead; env var approach is simpler given plugin already supports it |

---

## Sources

- `libs/mageflow/pyproject.toml` — version ranges for all test dependencies
- `libs/mageflow/mageflow/testing/_redis.py` — Redis image, backend detection logic, fixture scopes
- `libs/mageflow/mageflow/testing/plugin.py` — Fixture implementation, `loop_scope="session"` pattern
- `libs/mageflow/mageflow/testing/_config.py` — pyproject.toml parsing logic
- `libs/mageflow/tox.ini` — `testing-fakeredis` and `testing-testcontainers` environment pattern
- `uv.lock` — Exact resolved versions for all packages
- `pyproject.toml` (root) — Workspace members list and ruff config
- `libs/third-magic/pyproject.toml` — thirdmagic dependency ranges
