---
phase: quick-2
plan: 01
subsystem: mageflow-e2e
tags: [refactor, testing, e2e, myapp]
dependency_graph:
  requires: []
  provides: [clean-myapp-client-code, real-hatchet-redis-init]
  affects: [libs/mageflow-e2e/myapp/, libs/mageflow/mageflow/testing/plugin.py]
tech_stack:
  added: []
  patterns: [env-default-jwt-for-dev, real-redis-init, real-hatchet-init]
key_files:
  created: []
  modified:
    - libs/mageflow-e2e/myapp/client.py
    - libs/mageflow-e2e/myapp/alt_client.py
    - libs/mageflow/mageflow/testing/plugin.py
decisions:
  - Use os.environ.setdefault with a minimal dev JWT token so myapp can be imported without a live Hatchet server
  - Keep _make_dev_token() helper in each client file rather than a shared utility to keep files self-contained
  - Fix plugin.py task_defs variable shadowing bug as Rule 1 auto-fix
metrics:
  duration: ~15 minutes
  completed_date: "2026-03-17"
  tasks_completed: 2
  files_modified: 3
---

# Phase quick-2 Plan 01: Refactor mageflow-e2e myapp to use real Hatchet and Redis initialization

**One-liner:** Rewrote myapp/client.py and alt_client.py to use real `Hatchet()` and `Redis()` init with env-defaulted dev JWT tokens, removing all MagicMock and fakeredis from application code.

## What Was Done

### Task 1: Rewrite myapp client files to use real Hatchet and Redis initialization

Rewrote both `myapp/client.py` and `myapp/alt_client.py` to look like real application code a developer would write:

- Removed all imports of `unittest.mock`, `MagicMock`, and `fakeredis`
- Added a `_make_dev_token()` helper that builds a minimal JWT-shaped token encoding local server addresses (`localhost:8080`, `localhost:7070`) — this satisfies Hatchet's token validation without a live server
- Used `os.environ.setdefault()` so the env vars don't override real tokens set by a developer/CI environment
- Created `Hatchet(debug=True)` and `Redis(host="localhost", port=6379, decode_responses=True)` — real instances a developer would write
- All task registrations (@mf.task decorators, OrderInput model, etc.) remain identical
- Both modules import cleanly with correct `_task_defs` populated

### Task 2: Update pyproject.toml configs and tox.ini (no changes required)

After reviewing all config files:

- `pyproject.toml`: `backend = "fakeredis"` in `[tool.mageflow.testing]` is correct — this tells the plugin which backend to use, not a dependency. No fakeredis as a direct project dependency (comes via `mageflow[testing]` extra).
- `pyproject.testcontainers.toml`: Already correct with `backend = "testcontainers"` and no fakeredis dependency.
- `tox.ini`: Already correct, both `e2e-fakeredis` and `e2e-testcontainers` environments work as-is.

All 10 e2e tests pass.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed plugin.py task_defs variable shadowing causing TypeError**

- **Found during:** Task 2 verification (running `pytest`)
- **Issue:** In `mageflow/testing/plugin.py`, `task_defs` was initialized as `{}` then overwritten with `real_client._task_defs` (a list). The subsequent loop `for task_def in task_defs: task_defs[task_def.task_name] = task_def` failed with `TypeError: list indices must be integers or slices, not RedisStr` because `task_defs` was now a list, not a dict.
- **Fix:** Renamed the list variable to `task_def_list` and kept `task_defs` as the dict being built by the loop.
- **Files modified:** `libs/mageflow/mageflow/testing/plugin.py`
- **Commit:** 9b137b6

## Verification Results

- `grep -r "fakeredis|MagicMock|unittest.mock" libs/mageflow-e2e/myapp/ --include="*.py"`: No matches (PASS)
- `python -c "from myapp.client import mf; print(len(mf._task_defs))"`: 3 (PASS)
- `python -c "from myapp.alt_client import mf; print(len(mf._task_defs))"`: 1 (PASS)
- `uv run --project libs/mageflow-e2e pytest libs/mageflow-e2e/tests/ -v`: 10 passed (PASS)

## Commits

| Hash | Message |
|------|---------|
| dba0e58 | refactor(quick-2-01): rewrite myapp client files to use real Hatchet and Redis |
| 9b137b6 | fix(quick-2-01): fix plugin.py task_defs list vs dict bug |

## Self-Check: PASSED

- `libs/mageflow-e2e/myapp/client.py` — exists and imports cleanly
- `libs/mageflow-e2e/myapp/alt_client.py` — exists and imports cleanly
- `libs/mageflow/mageflow/testing/plugin.py` — fixed and all tests pass
- Commits dba0e58 and 9b137b6 exist in git log
