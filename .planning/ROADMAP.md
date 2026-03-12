# Roadmap: Mageflow Viewer Desktop App

## Overview

Three phases take the project from zero to distributed desktop app. Phase 1 builds the entire working application locally — sidecar compilation, Tauri shell, lifecycle management, React integration, and all user-facing UX. Phase 2 establishes the cross-platform CI pipeline that produces signed, notarized installers for all three platforms. Phase 3 ships those installers to users via auto-updater and package managers.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Working App** - Python sidecar + Tauri shell + React integration + all UX running locally (completed 2026-03-12)
- [ ] **Phase 2: CI Pipeline + Installers** - Cross-platform signed installers produced from GitHub Actions
- [ ] **Phase 3: Distribution** - Auto-updater and package manager channels live

## Phase Details

### Phase 1: Working App
**Goal**: A developer can launch the app locally, connect to Hatchet/Redis, and see workflow graphs — no manual server start, no broken startup state, no orphaned processes on exit.
**Depends on**: Nothing (first phase)
**Requirements**: PKG-01, PKG-02, PKG-03, PKG-04, PKG-05, PKG-06, UX-01, UX-02, UX-03, UX-04
**Success Criteria** (what must be TRUE):
  1. User launches the app and sees a loading screen while the sidecar starts; the workflow UI appears automatically once the backend is ready — no manual steps.
  2. On first launch, user sees an onboarding screen to enter Hatchet and Redis URLs; those settings persist across restarts without re-entry.
  3. User quits the app and no orphaned Python server process remains (verified by process list).
  4. When the sidecar crashes or external services are unreachable, user sees a meaningful error message — not a blank screen.
  5. System tray icon shows connection status; user can show, hide, or quit the app from the tray.
**Plans:** 8/8 plans complete
Plans:
- [ ] 01-00-PLAN.md — Wave 0 test stubs for Nyquist compliance
- [ ] 01-01-PLAN.md — Scaffold Tauri v2 project, Vite config, Python entry point
- [ ] 01-02-PLAN.md — Sidecar lifecycle in Rust (spawn, port, kill)
- [ ] 01-03-PLAN.md — Settings persistence, credential validation, and onboarding UI
- [ ] 01-04-PLAN.md — Startup state machine, splash screen, tray status wiring, error states
- [ ] 01-05-PLAN.md — System tray integration
- [ ] 01-06-PLAN.md — Nuitka binary compilation and end-to-end verification
- [ ] 01-07-PLAN.md — Gap closure: wire tray Settings menu item to frontend SettingsDialog

### Phase 2: CI Pipeline + Installers
**Goal**: Every tagged release automatically produces signed, notarized single-file installers for macOS (Universal), Windows x64, and Linux x64 via GitHub Actions.
**Depends on**: Phase 1
**Requirements**: DIST-01
**Success Criteria** (what must be TRUE):
  1. Pushing a version tag triggers a GitHub Actions workflow that produces a .dmg (macOS Universal), .msi (Windows x64), and .deb/.AppImage (Linux x64) without manual intervention.
  2. The macOS installer passes Gatekeeper (notarized and signed); the Windows installer is signed and does not trigger Defender quarantine; the Linux package installs cleanly.
  3. A fresh machine with no Python, Rust, or Node installed can install the app from the produced artifact and connect to Hatchet/Redis successfully.
**Plans**: TBD

### Phase 3: Distribution
**Goal**: Users can install the app via their platform's package manager and receive in-app update notifications when new releases are available.
**Depends on**: Phase 2
**Requirements**: DIST-02, DIST-03
**Success Criteria** (what must be TRUE):
  1. macOS user installs the app with `brew install --cask mageflow-viewer`; Windows user installs with `choco install mageflow-viewer`; Linux user installs via apt or snap.
  2. Running app detects a new release and prompts the user to update; accepting the prompt downloads and applies the update without requiring a manual reinstall.
  3. The updater signing private key is backed up in two independent locations with documented recovery steps before any installer ships.
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Working App | 8/8 | Complete   | 2026-03-12 |
| 2. CI Pipeline + Installers | 0/TBD | Not started | - |
| 3. Distribution | 0/TBD | Not started | - |
