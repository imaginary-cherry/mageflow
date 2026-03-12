---
phase: 01-working-app
plan: "06"
subsystem: infra
tags: [nuitka, tauri, python, sidecar, binary, packaging]

# Dependency graph
requires:
  - phase: 01-working-app plan 04
    provides: startup state machine, health-check gate, splash screen
  - phase: 01-working-app plan 05
    provides: system tray with status icons and context menu

provides:
  - Nuitka-compiled Python sidecar binary at frontend/src-tauri/binaries/mageflow-server-{TARGET_TRIPLE}
  - Full end-to-end working Mageflow Viewer desktop app verified by human

affects:
  - 02-distribution (binary packaging, codesigning, CI build steps)

# Tech tracking
tech-stack:
  added:
    - nuitka==4.0.4 (Python-to-native compiler)
    - image crate (PNG decode for tray icons, replaces non-existent Image::from_bytes)
  patterns:
    - Nuitka onefile compilation with --include-package-data=rapyer for Lua scripts
    - Sidecar binary placed at frontend/src-tauri/binaries/ with target-triple suffix (aarch64-apple-darwin)
    - externalBin configured as root path (binaries/ prefix must NOT appear in tauri.conf.json)

key-files:
  created:
    - frontend/src-tauri/.gitignore (excludes mageflow-server-* and Nuitka build artifacts)
  modified:
    - frontend/src-tauri/Cargo.toml (added image crate dependency)
    - frontend/src-tauri/capabilities/default.json (shell:allow-execute permission for sidecar)
    - frontend/src-tauri/src/lib.rs (sidecar path fix)
    - frontend/src-tauri/src/tray.rs (image crate PNG decode, show_menu_on_left_click)
    - frontend/src-tauri/tauri.conf.json (externalBin path corrected to root reference)

key-decisions:
  - "Nuitka onefile mode used (not standalone) — acceptable startup extraction latency on macOS, no Defender false-positive concerns on this platform"
  - "image crate used to decode tray icon PNGs — Tauri v2.10 does not have Image::from_bytes"
  - "externalBin value must be the binary name without the binaries/ prefix — Tauri resolves relative to app root, not src-tauri/"
  - "show_menu_on_left_click replaces deprecated menu_on_left_click in Tauri v2"
  - "--include-package-data=rapyer required to bundle Lua scripts used by rapyer Redis adapter"

patterns-established:
  - "Tray icon loading: use image crate decode_png then tauri::image::Image::from_raw()"
  - "Sidecar externalBin: omit subdirectory prefix, Tauri appends target-triple automatically"

requirements-completed: [PKG-01]

# Metrics
duration: 45min
completed: 2026-03-12
---

# Phase 1 Plan 06: Nuitka Sidecar Compilation and End-to-End Verification Summary

**Nuitka-compiled Python sidecar binary verified end-to-end in Tauri v2 desktop app with tray icons, onboarding, settings persistence, and process cleanup.**

## Performance

- **Duration:** ~45 min
- **Started:** 2026-03-12T09:30:00Z
- **Completed:** 2026-03-12T14:27:26Z
- **Tasks:** 2 (1 auto + 1 human-verify)
- **Files modified:** 7

## Accomplishments

- Compiled `visualizer/__main__.py` with Nuitka 4.0.4 (onefile mode) to `mageflow-server-aarch64-apple-darwin`
- Smoke tested binary: `/api/health` returns `{"status":"ok"}` with HTTP 200
- Fixed three Tauri v2 API incompatibilities discovered during integration (sidecar path, tray icon loading, deprecated method)
- Human confirmed full end-to-end app: launch, onboarding, splash, main UI, system tray, settings persistence, process cleanup

## Task Commits

Each task was committed atomically:

1. **Task 1: Compile Python sidecar with Nuitka** - `2ca0670` (feat)
2. **Fix: sidecar path, tray icon API, deprecated method** - `883f67a` (fix)
3. **Task 2: Human verification** - approved, no additional code commit

## Files Created/Modified

- `frontend/src-tauri/.gitignore` - Excludes mageflow-server-* binary and Nuitka .build/ artifacts
- `frontend/src-tauri/Cargo.toml` - Added `image` crate for PNG decoding
- `frontend/src-tauri/capabilities/default.json` - shell:allow-execute for sidecar
- `frontend/src-tauri/src/lib.rs` - Corrected sidecar path reference
- `frontend/src-tauri/src/tray.rs` - PNG decode via image crate, show_menu_on_left_click
- `frontend/src-tauri/tauri.conf.json` - externalBin path corrected (no binaries/ prefix)

## Decisions Made

- Used `image` crate for PNG decoding instead of Tauri's `Image::from_bytes` — that API does not exist in Tauri v2.10; the image crate is the correct approach.
- `externalBin` path must be the bare binary name (`binaries/mageflow-server`) — Tauri resolves from the app root and appends the target triple suffix automatically.
- `show_menu_on_left_click` replaces the deprecated `menu_on_left_click` — discovered at compile time, fixed immediately.
- Nuitka required `--include-package-data=rapyer` to bundle the Lua scripts that rapyer uses for atomic Redis operations.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed Tauri v2 tray icon loading API**
- **Found during:** Task 2 (end-to-end verification, app would not launch)
- **Issue:** `Image::from_bytes` does not exist in Tauri v2.10; caused compile error
- **Fix:** Added `image` crate, used `image::load_from_memory` to get RGBA bytes, then `tauri::image::Image::from_raw()`
- **Files modified:** `frontend/src-tauri/Cargo.toml`, `frontend/src-tauri/src/tray.rs`
- **Verification:** App launched with tray icons displaying correctly
- **Committed in:** 883f67a

**2. [Rule 1 - Bug] Fixed sidecar externalBin path resolution**
- **Found during:** Task 2 (sidecar not starting, Tauri could not find binary)
- **Issue:** `externalBin` had `binaries/mageflow-server` but Tauri v2 expects root-relative path without the `binaries/` prefix based on how it resolves the binary location
- **Fix:** Updated `tauri.conf.json` externalBin and corresponding `lib.rs` reference
- **Files modified:** `frontend/src-tauri/tauri.conf.json`, `frontend/src-tauri/src/lib.rs`
- **Verification:** Sidecar started and health endpoint returned 200
- **Committed in:** 883f67a

**3. [Rule 1 - Bug] Fixed deprecated `menu_on_left_click` tray method**
- **Found during:** Task 2 (compiler warning → upgraded to error)
- **Issue:** `menu_on_left_click` is deprecated in Tauri v2; replaced by `show_menu_on_left_click`
- **Fix:** Renamed method call in tray.rs
- **Files modified:** `frontend/src-tauri/src/tray.rs`
- **Verification:** Compiles cleanly with no deprecation warnings
- **Committed in:** 883f67a

---

**Total deviations:** 3 auto-fixed (all Rule 1 bugs — Tauri v2 API incompatibilities)
**Impact on plan:** All three fixes were necessary for the app to compile and run. No scope creep — all were direct blockers to task completion.

## Issues Encountered

- Nuitka compilation required `--include-package-data=rapyer` to bundle Lua scripts (not in plan's package list). Added without deviation tracking as it is a direct compilation requirement.
- gRPC/hatchet-sdk packages needed at runtime were already included via `--follow-imports`; no explicit grpc flags were necessary on this aarch64-apple-darwin target.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Phase 1 is complete. The full Mageflow Viewer desktop app is working end-to-end:
- Tauri v2 shell with React frontend
- Python sidecar compiled to native binary (Nuitka onefile, aarch64-apple-darwin)
- Onboarding, settings persistence, splash screen with health-check gate
- System tray with green/yellow/red status icons and context menu
- No orphaned sidecar processes on app exit

**Ready for Phase 2 (Distribution):**
- macOS: sidecar binary must be individually codesigned before Tauri bundling (known pitfall from research)
- Windows: `--standalone` mode for Nuitka instead of `--onefile` to avoid Defender false positives; EV certificate procurement needed
- CI: Nuitka compilation step must run on each target platform (no cross-compilation)
- CSP in production will need `connect-src http://127.0.0.1:<port>` added

---
*Phase: 01-working-app*
*Completed: 2026-03-12*
