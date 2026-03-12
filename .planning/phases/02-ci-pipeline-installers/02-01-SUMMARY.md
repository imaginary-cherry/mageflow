---
phase: 02-ci-pipeline-installers
plan: 01
subsystem: infra
tags: [github-actions, tauri, nuitka, ci, codesign, macos, windows, linux, release]

# Dependency graph
requires:
  - phase: 01-working-app
    provides: Nuitka-compiled sidecar pattern, tauri.conf.json with externalBin, Python sidecar entry point at libs/mage-voyance/visualizer/__main__.py

provides:
  - GitHub Actions release workflow that compiles Python sidecar per platform and produces signed installers
  - draft GitHub Release with .dmg (arm64 + x86_64), .msi/.exe (unsigned), .deb/.AppImage artifacts on v* tag push
  - macOS sidecar codesigning step using ephemeral keychain pattern

affects: [03-auto-updater, any future release automation]

# Tech tracking
tech-stack:
  added: [tauri-apps/tauri-action@v0, Nuitka/Nuitka-Action@main (pinned 4.0.4), swatinem/rust-cache@v2, actions/setup-python@v5]
  patterns: [tag-triggered release matrix, sidecar pre-build before tauri-action, ephemeral keychain for macOS codesign, Windows unsigned-first with Azure Trusted Signing TODO]

key-files:
  created:
    - .github/workflows/release-desktop.yml
  modified:
    - frontend/src-tauri/tauri.conf.json

key-decisions:
  - "Use onefile mode for all platforms initially; standalone mode on Windows deferred if Defender issues arise"
  - "Pin Nuitka to 4.0.4 matching Phase 1 tested version for gRPC/protobuf compatibility"
  - "releaseDraft: true so artifacts are reviewed before publishing"
  - "Windows ships unsigned initially; AZURE_CLIENT_ID/SECRET/TENANT_ID secrets wired but signCommand in tauri.conf.json deferred to v1.1"
  - "macOS signingIdentity: null in tauri.conf.json — tauri-action injects via APPLE_SIGNING_IDENTITY env var"
  - "Separate arm64 + x86_64 DMGs (not universal-apple-darwin) — universal target has open sidecar runtime bug Tauri #3355"

patterns-established:
  - "Pattern: Nuitka sidecar pre-build runs in same job as tauri-action, placed in frontend/src-tauri/binaries/ with target-triple suffix"
  - "Pattern: Ephemeral keychain (not system keychain) for macOS CI codesign to avoid notarization failures on nested binaries"
  - "Pattern: Windows fallback detection for standalone .dist directory in rename step"

requirements-completed: [DIST-01]

# Metrics
duration: 5min
completed: 2026-03-12
---

# Phase 2 Plan 01: CI Release Workflow Summary

**GitHub Actions release-desktop.yml workflow that compiles Nuitka sidecar on all 4 platform runners, individually codesigns the macOS binary, and runs tauri-action to produce draft .dmg/.msi/.deb installers on v* tag push**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-12T15:07:13Z
- **Completed:** 2026-03-12T15:12:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Created `.github/workflows/release-desktop.yml` with 4-platform matrix (macOS arm64, macOS x86_64, Ubuntu 22.04, Windows), Nuitka 4.0.4 sidecar pre-build, macOS cert import + codesign, and tauri-action draft release
- Updated `frontend/src-tauri/tauri.conf.json` with `bundle.macOS.signingIdentity` and `bundle.windows` digest/timestamp defaults for future signing
- Windows unsigned initially with all Azure secrets wired and a TODO comment for v1.1 EV signing

## Task Commits

Each task was committed atomically:

1. **Task 1: Create release-desktop.yml workflow** - `dfd6e9f` (feat)
2. **Task 2: Update tauri.conf.json bundle config for signing** - `383b9f3` (feat)

**Plan metadata:** `(final doc commit — see below)`

## Files Created/Modified

- `.github/workflows/release-desktop.yml` - Cross-platform release CI workflow (trigger, matrix, Nuitka compile, rename, codesign, tauri-action)
- `frontend/src-tauri/tauri.conf.json` - Added bundle.macOS.signingIdentity and bundle.windows signing defaults

## Decisions Made

- **onefile mode for all platforms:** Simplest initial path. If Windows Defender flags self-extraction to %TEMP%, switch to standalone — see research Open Question 2 for the directory-vs-single-file tradeoff.
- **Nuitka 4.0.4 pinned:** Matches Phase 1's hatchet-sdk gRPC/protobuf verified version. Do not upgrade without explicit smoke testing.
- **releaseDraft: true:** Artifacts are reviewed before public release. Prevents accidental public release of broken builds.
- **Windows unsigned:** Ships without signCommand. Azure TENANT/CLIENT/SECRET secrets are wired for when Azure Trusted Signing is configured in v1.1.
- **macOS signingIdentity: null:** CI-only pattern — tauri-action reads APPLE_SIGNING_IDENTITY env var. Null in config avoids hardcoding identity string.
- **Separate arm64 + x86_64 builds (not universal):** Avoids Tauri bug #3355 where universal-apple-darwin breaks sidecar runtime resolution.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

Before the workflow can run, the following GitHub Actions secrets must be configured in the repository:

**macOS secrets (7):**
- `APPLE_CERTIFICATE` — Base64-encoded .p12 Developer ID Application certificate
- `APPLE_CERTIFICATE_PASSWORD` — .p12 export password
- `APPLE_SIGNING_IDENTITY` — Certificate name string (e.g. "Developer ID Application: Name (TEAMID)")
- `APPLE_ID` — Apple Developer account email
- `APPLE_PASSWORD` — App-specific password from appleid.apple.com
- `APPLE_TEAM_ID` — 10-character Team ID from developer.apple.com/account
- `KEYCHAIN_PASSWORD` — Any strong random password for the ephemeral CI keychain

**Windows secrets (3 — configure when Azure Trusted Signing is set up in v1.1):**
- `AZURE_CLIENT_ID`
- `AZURE_CLIENT_SECRET`
- `AZURE_TENANT_ID`

**GitHub Permissions:** Repository Settings > Actions > Workflow permissions must be set to "Read and write permissions" for tauri-action to create releases.

## Next Phase Readiness

- CI pipeline is complete for DIST-01. The workflow file is in place and ready to trigger on the first `v*` tag push.
- Before first tag push: configure the 7 macOS secrets listed above and set Actions workflow permissions to "Read and write".
- Windows unsigned initially — users will see SmartScreen warning on first install. Add Azure Trusted Signing for v1.1.
- Phase 3 (auto-updater) can build on the `releaseDraft: true` + `tagName: v__VERSION__` pattern established here.

## Self-Check: PASSED

- FOUND: .github/workflows/release-desktop.yml
- FOUND: .planning/phases/02-ci-pipeline-installers/02-01-SUMMARY.md
- FOUND: commit dfd6e9f (Task 1 — release-desktop.yml)
- FOUND: commit 383b9f3 (Task 2 — tauri.conf.json)

---
*Phase: 02-ci-pipeline-installers*
*Completed: 2026-03-12*
