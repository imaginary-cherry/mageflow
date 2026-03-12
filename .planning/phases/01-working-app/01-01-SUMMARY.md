---
phase: 01-working-app
plan: "01"
subsystem: infra
tags: [tauri, rust, vite, react, python, fastapi, uvicorn, nuitka]

# Dependency graph
requires: []
provides:
  - Tauri v2 project scaffold in frontend/src-tauri/ with complete configuration
  - CSP configured for sidecar localhost API access
  - tauri-plugin-shell and tauri-plugin-store registered in Rust and JS
  - capabilities/default.json with shell:allow-execute for mageflow-server sidecar
  - Python __main__.py entry point for Nuitka compilation with programmatic uvicorn
  - Tauri-compatible Vite configuration (clearScreen, TAURI_ENV, watch ignore, build targets)
affects:
  - 01-02 (sidecar lifecycle Rust code depends on Cargo.toml plugins)
  - 01-03 (health-check polling uses sidecar port from capabilities)
  - 01-06 (Nuitka compilation uses __main__.py entry point)

# Tech tracking
tech-stack:
  added:
    - "@tauri-apps/cli ^2.10.1 (dev)"
    - "@tauri-apps/api ^2.10.1"
    - "@tauri-apps/plugin-shell ^2.3.5"
    - "@tauri-apps/plugin-store ^2.4.2"
    - "tauri-plugin-shell 2 (Rust, open-api feature)"
    - "tauri-plugin-store 2 (Rust)"
  patterns:
    - "Tauri v2 project structure: frontend/src-tauri/ alongside Vite app"
    - "capabilities/ directory for Tauri v2 permissions (replaces v1 allowlist)"
    - "Programmatic uvicorn.run() with workers=1 for Nuitka compatibility"
    - "freeze_support() at top of main() for compiled multiprocessing apps"

key-files:
  created:
    - frontend/src-tauri/tauri.conf.json
    - frontend/src-tauri/Cargo.toml
    - frontend/src-tauri/src/lib.rs
    - frontend/src-tauri/src/main.rs
    - frontend/src-tauri/build.rs
    - frontend/src-tauri/capabilities/default.json
    - frontend/src-tauri/binaries/.gitkeep
    - frontend/src-tauri/icons/
    - libs/mage-voyance/visualizer/__main__.py
  modified:
    - frontend/vite.config.ts
    - frontend/package.json
    - frontend/package-lock.json

key-decisions:
  - "Used create_dev_app() in __main__.py (not create_app()): Tauri serves the frontend, server only needs API routes with CORS — no static file serving needed"
  - "Kept tauri-plugin-log registration in lib.rs (debug only) from generated init: useful for development"
  - "workers=1 in uvicorn.run() is mandatory for Nuitka — multi-worker spawning fails in compiled mode"

patterns-established:
  - "Pattern 1: Tauri capabilities use object-form shell:allow-execute with validator regex per arg"
  - "Pattern 2: Vite config reads TAURI_DEV_HOST for cross-device development, falls back to :: for localhost"
  - "Pattern 3: Python sidecar accepts --hatchet-api-key and --redis-url CLI args, sets env vars before creating app"

requirements-completed:
  - PKG-02

# Metrics
duration: 20min
completed: "2026-03-12"
---

# Phase 1 Plan 01: Tauri v2 Scaffold and Python Entry Point Summary

**Tauri v2 desktop shell scaffolded into existing Vite+React app with CSP-configured sidecar capabilities and a Nuitka-compatible Python __main__.py entry point**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-03-12T09:00:00Z
- **Completed:** 2026-03-12T09:20:00Z
- **Tasks:** 2
- **Files modified:** 11 (9 created, 3 modified including icons dir)

## Accomplishments
- Tauri v2 initialized in frontend/src-tauri/ with correct app identifier (dev.mageflow.viewer), CSP, window dimensions (1200x800), and externalBin configuration for the mageflow-server sidecar
- tauri-plugin-shell and tauri-plugin-store added to Cargo.toml and registered in lib.rs; capabilities/default.json grants shell:allow-execute with per-arg validators and store permissions
- Python `__main__.py` created with argparse CLI (--port, --host, --hatchet-api-key, --redis-url), programmatic uvicorn.run with workers=1, and freeze_support() for Nuitka compatibility
- Vite config updated for Tauri: clearScreen, TAURI_ENV envPrefix, TAURI_DEV_HOST-aware server, watch ignore for src-tauri, platform-aware build targets, proxy removed

## Task Commits

Each task was committed atomically:

1. **Task 1: Initialize Tauri v2 project and install dependencies** - `8677cc5` (feat)
2. **Task 2: Update Vite config for Tauri and create Python sidecar entry point** - `f6a644b` (feat)

## Files Created/Modified
- `frontend/src-tauri/tauri.conf.json` - Tauri configuration: identifier, CSP, window 1200x800, externalBin for mageflow-server
- `frontend/src-tauri/Cargo.toml` - Rust dependencies with tauri-plugin-shell (open-api) and tauri-plugin-store
- `frontend/src-tauri/src/lib.rs` - Tauri builder with shell and store plugins registered
- `frontend/src-tauri/src/main.rs` - App entry point (delegates to lib.rs run())
- `frontend/src-tauri/capabilities/default.json` - core:default + store permissions + shell:allow-execute with sidecar arg validators
- `frontend/src-tauri/binaries/.gitkeep` - Placeholder for compiled sidecar binary (Plan 06)
- `frontend/vite.config.ts` - Tauri-compatible Vite config (removed proxy, lovable-tagger; added clearScreen, TAURI_ENV)
- `frontend/package.json` - Added tauri script, Tauri JS packages (@tauri-apps/api, plugin-shell, plugin-store)
- `libs/mage-voyance/visualizer/__main__.py` - Nuitka-compatible sidecar entry point with programmatic uvicorn

## Decisions Made
- Used `create_dev_app()` instead of `create_app()` in `__main__.py` because Tauri serves the frontend at runtime — the Python server only needs to expose API routes with CORS, not static file hosting or SPA fallback
- Retained tauri-plugin-log from generated init code (debug-only) as it provides useful development logging with no production overhead
- Set `workers=1` in uvicorn.run — this is mandatory for Nuitka; the multiprocessing-based worker spawning mechanism fails in compiled binaries

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- `npx tauri init` produced no output but succeeded silently when run with `CI=true` flag — verified by checking src-tauri/ directory creation. All generated files were then modified to match plan specifications.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Tauri v2 shell foundation complete — Plan 02 (sidecar lifecycle Rust code) can now add spawn/kill logic to lib.rs
- Cargo.toml already has tauri-plugin-shell dependency needed for Plan 02's sidecar spawn commands
- Python `__main__.py` is ready for Nuitka compilation in Plan 06 — only test with `python -m visualizer` needed to validate before compilation
- Concern: binaries/ directory is empty — `npx tauri dev` will fail until a stub or real binary is placed there (Plan 02 can run without a binary if sidecar spawn is made conditional)

---
*Phase: 01-working-app*
*Completed: 2026-03-12*
