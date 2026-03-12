---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: planning
stopped_at: Completed 02-ci-pipeline-installers-02-PLAN.md
last_updated: "2026-03-12T18:48:06.652Z"
last_activity: 2026-03-12 — Roadmap created (3 phases, 13/13 requirements mapped)
progress:
  total_phases: 3
  completed_phases: 2
  total_plans: 10
  completed_plans: 10
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-12)

**Core value:** Single installable app — connect to Hatchet/Redis, visualize mageflow workflows, no server setup required.
**Current focus:** Phase 1 — Working App

## Current Position

Phase: 1 of 3 (Working App)
Plan: 0 of TBD in current phase
Status: Ready to plan
Last activity: 2026-03-12 — Roadmap created (3 phases, 13/13 requirements mapped)

Progress: [░░░░░░░░░░] 0%

## Performance Metrics

**Velocity:**
- Total plans completed: 0
- Average duration: —
- Total execution time: —

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**
- Last 5 plans: —
- Trend: —

*Updated after each plan completion*
| Phase 01-working-app P00 | 5min | 2 tasks | 6 files |
| Phase 01-working-app P01 | 20 | 2 tasks | 11 files |
| Phase 01-working-app P03 | 2 | 2 tasks | 3 files |
| Phase 01-working-app P02 | 15 | 1 tasks | 2 files |
| Phase 01-working-app P04 | 2 | 2 tasks | 5 files |
| Phase 01-working-app P05 | 6 | 2 tasks | 6 files |
| Phase 01-working-app P06 | 45 | 2 tasks | 7 files |
| Phase 01-working-app P07 | 5 | 1 tasks | 1 files |
| Phase 02-ci-pipeline-installers P01 | 5 | 2 tasks | 2 files |
| Phase 02-ci-pipeline-installers P02 | 75 | 2 tasks | 1 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Tauri v2 over Electron: smaller bundle, system webview, built-in updater
- Nuitka over PyInstaller: clean `child.kill()`, faster startup, no orphan process
- Viewer-only (no bundled services): lightweight app, users have existing infrastructure
- [Phase 01-working-app]: Used it.todo() stubs so test:unit runs green before implementation (Wave 0 scaffolding)
- [Phase 01-working-app]: Integration tests live at tests/integration/ (outside frontend/) matching vitest integration project config
- [Phase 01-working-app]: Used create_dev_app() in __main__.py: Tauri serves frontend, server only needs API routes with CORS, no static files
- [Phase 01-working-app]: workers=1 in uvicorn.run() is mandatory for Nuitka - multi-worker spawning fails in compiled mode
- [Phase 01-working-app]: validateCredentials uses two-tier fallback: validate_credentials Tauri command first, then restart_sidecar + health poll
- [Phase 01-working-app]: Deferred sidecar spawn on first launch: port reserved immediately, spawn skipped if settings.json missing or credentials empty
- [Phase 01-working-app]: kill_sidecar is synchronous (not async) — RunEvent exit handlers cannot be async in Tauri
- [Phase 01-working-app]: Removed invalid open-api feature from tauri-plugin-shell v2 — that feature does not exist
- [Phase 01-working-app]: pollForReady extracted from startup sequence so onOnboardingComplete and retrySidecar share identical hatchet->redis->ready logic
- [Phase 01-working-app]: HttpTaskClient baseUrl: VITE_API_URL fallback only in browser dev mode; Tauri always receives explicit runtime port
- [Phase 01-working-app]: Icons embedded via include_bytes! — zero runtime I/O, works correctly in the bundled Tauri app
- [Phase 01-working-app]: Tray created in setup hook rather than RunEvent::Ready — ensures tray appears before window
- [Phase 01-working-app]: image crate used for tray icon PNG decode — Tauri v2.10 does not have Image::from_bytes
- [Phase 01-working-app]: externalBin must be root-relative path without binaries/ prefix — Tauri appends target-triple automatically
- [Phase 01-working-app]: open-settings listener co-located inside setupSidecarExitListener to share the @tauri-apps/api/event dynamic import
- [Phase 02-ci-pipeline-installers]: Nuitka 4.0.4 pinned in CI to match Phase 1 tested version for gRPC/protobuf compatibility
- [Phase 02-ci-pipeline-installers]: Windows ships unsigned initially; Azure Trusted Signing deferred to v1.1 (AZURE_* secrets wired, signCommand not yet added)
- [Phase 02-ci-pipeline-installers]: Separate arm64 + x86_64 DMGs instead of universal-apple-darwin — avoids Tauri bug #3355 sidecar runtime resolution failure
- [Phase 02-ci-pipeline-installers]: No Apple Developer account — macOS .dmg ships unsigned for v1.0; signed builds deferred until Apple Developer Program enrollment
- [Phase 02-ci-pipeline-installers]: GitHub Actions workflow permissions must be set to Read and write before first tag push

### Critical Pitfalls (from research — address in Phase 1)

- Nuitka `--standalone` (not `--onefile`) for Windows — avoids Defender false positives
- Nuitka must include `--include-package=grpc --include-package=google.protobuf --include-package-data=hatchet_sdk`
- Sidecar binary must have target-triple suffix in filename
- Tauri does NOT kill child processes automatically — hook `RunEvent::Exit`
- macOS: sidecar binary must be individually codesigned before Tauri bundles it
- CSP in production blocks `fetch()` to localhost — add `connect-src http://127.0.0.1:<port>`

### Pending Todos

None yet.

### Blockers/Concerns

- Windows EV certificate procurement can take days to weeks — initiate at Phase 2 planning time, not build time.
- Nuitka + hatchet-sdk gRPC compatibility (issue #3608) — must smoke-test on clean VM in Phase 1.

## Session Continuity

Last session: 2026-03-12T18:48:06.651Z
Stopped at: Completed 02-ci-pipeline-installers-02-PLAN.md
Resume file: None
