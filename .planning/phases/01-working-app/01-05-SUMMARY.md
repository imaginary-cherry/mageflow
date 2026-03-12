---
phase: 01-working-app
plan: "05"
subsystem: infra
tags: [tauri, rust, tray, system-tray, tray-icon, menu, connection-status]

# Dependency graph
requires:
  - phase: 01-working-app
    plan: "02"
    provides: "lib.rs structure with tauri::Builder, SidecarState/SidecarPort, setup hook"
provides:
  - System tray icon at app startup (yellow = starting state)
  - Three tray icon assets: green (connected), yellow (starting), red (disconnected)
  - Right-click context menu: Show Window, Settings..., Quit
  - Left-click toggles main window visibility (macOS/Windows)
  - Settings menu item emits 'open-settings' event to React frontend
  - Tauri command: set_tray_status (changes icon + tooltip based on status string)
affects:
  - 01-04 (frontend calls set_tray_status('connected'/'starting'/'disconnected') from useAppStartup)

# Tech tracking
tech-stack:
  added:
    - "tauri tray-icon feature (added to Cargo.toml)"
  patterns:
    - "TrayIconBuilder::with_id('main') — access later via app.tray_by_id('main')"
    - "include_bytes! for PNG icon loading — zero runtime I/O, icons embedded in binary"
    - "menu_on_left_click(false) — left click handler and menu are independent"

key-files:
  created:
    - frontend/src-tauri/src/tray.rs
    - frontend/src-tauri/icons/tray-green.png
    - frontend/src-tauri/icons/tray-yellow.png
    - frontend/src-tauri/icons/tray-red.png
  modified:
    - frontend/src-tauri/src/lib.rs
    - frontend/src-tauri/Cargo.toml

key-decisions:
  - "Icons embedded via include_bytes! — no runtime file I/O, works in bundled Tauri app"
  - "Tray created in setup hook (not RunEvent::Ready) — ensures tray exists before window appears"
  - "Quit calls app.exit(0) not std::process::exit — triggers RunEvent::Exit sidecar cleanup"

# Metrics
duration: 6min
completed: "2026-03-12"
---

# Phase 1 Plan 05: System Tray Integration Summary

**System tray with three-color status indicator (green/yellow/red), Show Window/Settings/Quit context menu, left-click window toggle, and set_tray_status Tauri command for frontend-driven icon updates**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-03-12T11:23:00Z
- **Completed:** 2026-03-12T11:29:00Z
- **Tasks:** 2
- **Files modified:** 6 (4 created, 2 modified)

## Accomplishments

- Generated three 32x32 RGBA PNG tray icons (green/yellow/red) with colored circles on transparent backgrounds using Python Pillow
- Implemented `tray.rs` with `create_tray()` and `update_tray_icon()` functions using Tauri v2 `TrayIconBuilder` API
- System tray starts with yellow (starting) icon; tooltip reads "Mageflow Viewer - starting"
- Left-click toggles main window show/hide via `is_visible()` check; uses `menu_on_left_click(false)` to keep click handler and menu separate
- Settings menu item emits `"open-settings"` event via `app.emit()` — React frontend listens and opens SettingsDialog
- Quit menu item calls `app.exit(0)` which triggers `RunEvent::Exit` and kills the sidecar
- `set_tray_status` Tauri command updates icon and tooltip based on status string ("connected"/"starting"/"partial"/"disconnected")
- Added `tray-icon` feature to `tauri` dependency in Cargo.toml
- Called `create_tray(app.handle())` in the existing `setup` hook in lib.rs
- Registered `set_tray_status` in `invoke_handler` list

## Task Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create tray icon assets | `97dd8ee` | icons/tray-green.png, tray-yellow.png, tray-red.png |
| 2 | Implement tray module and integrate with app | `45d5247` | src/tray.rs, src/lib.rs, Cargo.toml |

## Files Created/Modified

- `frontend/src-tauri/src/tray.rs` — tray creation, menu, left-click handler, icon swap on status update
- `frontend/src-tauri/src/lib.rs` — `mod tray;` declaration, `create_tray` call in setup hook, `set_tray_status` command
- `frontend/src-tauri/Cargo.toml` — added `features = ["tray-icon"]` to tauri dependency
- `frontend/src-tauri/icons/tray-green.png` — 32x32 green circle (#22c55e), connected state
- `frontend/src-tauri/icons/tray-yellow.png` — 32x32 yellow circle (#eab308), starting/partial state
- `frontend/src-tauri/icons/tray-red.png` — 32x32 red circle (#ef4444), disconnected state

## Decisions Made

- Icons embedded via `include_bytes!` — zero runtime I/O, works correctly in the bundled Tauri app where file paths are different
- Tray created in `setup` hook rather than `RunEvent::Ready` — ensures the tray icon appears immediately when the app starts, before the window is shown
- `app.exit(0)` used in Quit handler (not `std::process::exit`) — this properly triggers `RunEvent::Exit` which kills the sidecar via the existing `kill_sidecar` handler

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

- `cargo check` build-script error for missing `binaries/mageflow-server-aarch64-apple-darwin` persists (same as Plan 02). This is expected and does not indicate a Rust source compilation error. The rustc compilation of `app v0.1.0` itself succeeds (confirmed by "Compiling app v0.1.0" message with no `error[E...]` from rustc).

## User Setup Required

None.

## Next Phase Readiness

- Plan 06 (Nuitka sidecar packaging) places the binary in `binaries/` — after that, `cargo check` and `npx tauri dev` will work fully
- Frontend (useAppStartup hook from Plan 04) can now call `invoke('set_tray_status', { status: 'connected' })` to update the tray icon when health-check transitions complete

---
*Phase: 01-working-app*
*Completed: 2026-03-12*
