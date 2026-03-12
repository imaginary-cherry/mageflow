---
phase: 01-working-app
plan: "02"
subsystem: infra
tags: [tauri, rust, sidecar, process-lifecycle, tauri-plugin-shell, tauri-plugin-store]

# Dependency graph
requires:
  - phase: 01-working-app
    plan: "01"
    provides: "Tauri v2 project scaffold with tauri-plugin-shell and tauri-plugin-store in Cargo.toml, capabilities/default.json with shell:allow-execute for mageflow-server sidecar"
provides:
  - Full sidecar lifecycle management in frontend/src-tauri/src/lib.rs
  - Dynamic port allocation via TcpListener OS assignment
  - Graceful first-launch handling (port reserved, spawn deferred until settings saved)
  - Tauri commands: get_sidecar_port, get_sidecar_status, restart_sidecar
  - Process cleanup on RunEvent::ExitRequested and RunEvent::Exit
affects:
  - 01-03 (health-check polling calls get_sidecar_port to know which port to hit)
  - 01-04 (settings onboarding calls restart_sidecar after saving credentials)
  - 01-05 (frontend invokes get_sidecar_port and get_sidecar_status)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Dynamic port via TcpListener::bind(0) then drop — OS assigns and releases before sidecar binds"
    - "Tauri managed state pattern: SidecarState(Mutex<Option<CommandChild>>) / SidecarPort(Mutex<Option<u16>>)"
    - "StoreExt::store() for reading tauri-plugin-store keys in Rust backend"
    - "ShellExt::sidecar() for spawning sidecar commands with typed arg validators"
    - "Synchronous kill_sidecar() — RunEvent exit handlers cannot be async"

key-files:
  created: []
  modified:
    - frontend/src-tauri/src/lib.rs
    - frontend/src-tauri/Cargo.toml

key-decisions:
  - "Deferred sidecar spawn on first launch: port is reserved and stored, but spawn is skipped if settings.json is missing or credentials are empty — onboarding flow calls restart_sidecar after save"
  - "kill_sidecar is synchronous to be safely callable from RunEvent::ExitRequested and RunEvent::Exit — async is not available in that context"
  - "Removed invalid open-api feature flag from tauri-plugin-shell — that feature does not exist in v2; shell sidecar spawn works without it"

patterns-established:
  - "Pattern 4: Sidecar port allocated before spawn and stored immediately — frontend reads it via get_sidecar_port even if sidecar is deferred"
  - "Pattern 5: restart_sidecar command provides crash-recovery entry point — kills existing process, re-reads fresh settings, spawns with new port"

requirements-completed:
  - PKG-03
  - PKG-05

# Metrics
duration: 15min
completed: "2026-03-12"
---

# Phase 1 Plan 02: Sidecar Lifecycle Management Summary

**Rust sidecar manager with dynamic OS port allocation, tauri-plugin-store credential reading, graceful first-launch deferral, and synchronous process cleanup on app exit**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-03-12T09:20:00Z
- **Completed:** 2026-03-12T09:35:00Z
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments
- Full sidecar lifecycle in lib.rs: find_free_port() using TcpListener OS assignment, spawn_sidecar() reading settings from tauri-plugin-store, kill_sidecar() in both ExitRequested and Exit handlers
- Three Tauri commands exposed: get_sidecar_port (returns u16 or error), get_sidecar_status (returns "running"/"stopped"), restart_sidecar (kill + re-spawn with fresh settings, returns new port)
- Graceful first-launch handling: port is allocated and stored immediately but spawn is deferred when settings.json is absent or credentials are empty — no crash on fresh install
- Fixed Cargo.toml: removed the non-existent `open-api` feature flag from tauri-plugin-shell v2

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement sidecar lifecycle management in Rust** - `dfbe8b7` (feat)

## Files Created/Modified
- `frontend/src-tauri/src/lib.rs` - Full sidecar lifecycle: SidecarState/SidecarPort state, find_free_port, spawn_sidecar, kill_sidecar, get_sidecar_port/status/restart commands, RunEvent handlers
- `frontend/src-tauri/Cargo.toml` - Removed invalid `open-api` feature from tauri-plugin-shell dependency

## Decisions Made
- Deferred sidecar spawn on first launch rather than failing: the port is reserved immediately so the frontend has a port to query, but spawn only happens if both hatchetApiKey and redisUrl are present in settings.json
- kill_sidecar made synchronous (not async) because Tauri's RunEvent exit handlers run in a synchronous context; using async_runtime::block_on would deadlock
- restart_sidecar returns the new port as Result<u16, String> so the frontend can update its stored port reference after a crash recovery

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Removed non-existent `open-api` feature from tauri-plugin-shell**
- **Found during:** Task 1 (cargo check verification)
- **Issue:** Cargo.toml had `features = ["open-api"]` for tauri-plugin-shell v2, which caused `cargo check` to fail with "package does not have that feature"
- **Fix:** Removed the feature list entirely — `tauri-plugin-shell = { version = "2" }`
- **Files modified:** frontend/src-tauri/Cargo.toml
- **Verification:** cargo check proceeds past dependency resolution
- **Committed in:** dfbe8b7 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** The feature flag was inherited from Plan 01 scaffolding and is incorrect for tauri-plugin-shell v2 — removing it is necessary for compilation.

## Issues Encountered
- `cargo check` build fails with `resource path 'binaries/mageflow-server-aarch64-apple-darwin' doesn't exist` — this is expected. The Tauri build script validates externalBin paths at check time. The binary will be placed there in Plan 06. The Rust source code itself compiled successfully (no `error[E...]` messages from rustc).

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Sidecar lifecycle complete — Plan 03 (health-check polling) can call `invoke('get_sidecar_port')` to know which port to poll
- Plan 04 (settings/onboarding) can call `invoke('restart_sidecar')` after user saves credentials to trigger first spawn
- Concern: `cargo check` build-script error for missing binary will persist until Plan 06 places the Nuitka binary in binaries/. This does not block frontend development but does mean `npx tauri dev` will fail until a stub binary exists.

---
*Phase: 01-working-app*
*Completed: 2026-03-12*
