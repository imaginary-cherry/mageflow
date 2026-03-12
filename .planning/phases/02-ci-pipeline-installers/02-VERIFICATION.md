---
phase: 02-ci-pipeline-installers
verified: 2026-03-12T18:00:00Z
status: human_needed
score: 7/7 must-haves verified
human_verification:
  - test: "Push a v* tag and confirm workflow triggers"
    expected: "GitHub Actions shows 'Release Desktop App' workflow with 4 matrix jobs starting within ~30s of tag push"
    why_human: "Workflow triggering requires pushing a tag to GitHub — cannot verify a live CI run from the local codebase"
  - test: "All 4 matrix jobs complete and produce a draft release"
    expected: "Draft release named 'Mageflow Viewer vX.Y.Z' appears in GitHub Releases with .dmg (aarch64 + x86_64), .deb/.AppImage, and .msi/.exe artifacts attached"
    why_human: "Artifact production requires actual CI execution — no artifacts exist locally; this is the primary deliverable of DIST-01"
  - test: "macOS .dmg installs and runs on a fresh Mac without prior Python/Rust/Node"
    expected: "App launches, sidecar starts, workflow UI loads — no missing library or runtime errors"
    why_human: "Fresh-machine install test (ROADMAP Success Criterion 3) requires a real machine without dev tooling"
  - test: "macOS Gatekeeper behavior on unsigned .dmg"
    expected: "Gatekeeper shows 'unidentified developer' warning (no Apple account); user can open via right-click > Open or Privacy & Security > Open Anyway"
    why_human: "macOS UI security dialog requires a physical Mac to observe — workflow will produce an unsigned DMG per the no-Apple-account decision"
  - test: "Windows installer does not trigger Defender quarantine (ROADMAP Success Criterion 2)"
    expected: "Windows SmartScreen shows a 'More info > Run anyway' prompt (expected for unsigned first-run); installer completes successfully"
    why_human: "Windows SmartScreen behavior requires running the installer on a real Windows machine"
---

# Phase 2: CI Pipeline + Installers Verification Report

**Phase Goal:** Every tagged release automatically produces signed, notarized single-file installers for macOS (arm64 + x86_64), Windows x64, and Linux x64 via GitHub Actions.
**Verified:** 2026-03-12T18:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

All automated artifacts (workflow file, tauri config) are in place and substantive. The CI pipeline definition is complete. What cannot be verified locally are the three ROADMAP success criteria that require an actual tag push and live CI run.

### Observable Truths (from Plan 02-01 must_haves)

| #   | Truth                                                                    | Status     | Evidence                                                                                          |
| --- | ------------------------------------------------------------------------ | ---------- | ------------------------------------------------------------------------------------------------- |
| 1   | A release-desktop.yml workflow exists that triggers on v* tag push       | VERIFIED   | File exists at `.github/workflows/release-desktop.yml`; lines 9-12: `on.push.tags: ['v*']`       |
| 2   | The workflow builds on macOS (arm64 + x86_64), Ubuntu 22.04, and Windows | VERIFIED   | 4-entry matrix: `macos-latest` x2 (aarch64/x86_64 args), `ubuntu-22.04`, `windows-latest`        |
| 3   | Nuitka compiles the Python sidecar with correct packages on each runner  | VERIFIED   | `Nuitka/Nuitka-Action@main` pinned to `4.0.4`; 11 packages in `include-package`; `hatchet_sdk,rapyer` in `include-package-data` |
| 4   | The sidecar binary is renamed to target-triple format before tauri-action runs | VERIFIED | `rustc --print host-tuple` rename step with Windows `.dist` fallback (lines 114-133)             |
| 5   | macOS sidecar is individually codesigned before tauri-action bundles it  | VERIFIED   | Ephemeral keychain creation + `set-key-partition-list` + `codesign --force --timestamp --options runtime` (lines 141-170) |
| 6   | tauri-action produces installers and creates a draft GitHub Release      | VERIFIED   | `tauri-apps/tauri-action@v0` with `releaseDraft: true`, `tagName: v__VERSION__`, `projectPath: ./frontend` |
| 7   | tauri.conf.json has bundle signing config for macOS and Windows          | VERIFIED   | `bundle.macOS.signingIdentity: null` (CI env var injection) + `bundle.windows.digestAlgorithm` + `bundle.windows.timestampUrl` |

**Score:** 7/7 truths verified

### Required Artifacts

| Artifact                                  | Expected                              | Status     | Details                                                                                              |
| ----------------------------------------- | ------------------------------------- | ---------- | ---------------------------------------------------------------------------------------------------- |
| `.github/workflows/release-desktop.yml`   | Cross-platform release workflow       | VERIFIED   | 200 lines; valid YAML (python3 yaml.safe_load confirmed); substantive with all required steps        |
| `frontend/src-tauri/tauri.conf.json`      | Bundle signing configuration          | VERIFIED   | Contains `bundle` section with `macOS`, `windows`, `externalBin`, `icon`; existing fields preserved |
| `frontend/src-tauri/binaries/.gitkeep`    | Binaries directory placeholder        | VERIFIED   | Directory exists with `.gitkeep`; `.gitignore` excludes `mageflow-server-*` binaries correctly      |

### Key Link Verification

| From                                   | To                                       | Via                                         | Status  | Details                                                                                          |
| -------------------------------------- | ---------------------------------------- | ------------------------------------------- | ------- | ------------------------------------------------------------------------------------------------ |
| `release-desktop.yml`                  | `frontend/src-tauri/tauri.conf.json`     | `tauri-apps/tauri-action@v0` reads config   | WIRED   | `projectPath: ./frontend` points tauri-action at the config; `tauri.conf.json` has `bundle` section |
| `release-desktop.yml`                  | `frontend/src-tauri/binaries/`           | Nuitka output-dir + rename step             | WIRED   | `output-dir: frontend/src-tauri/binaries/`; rename step places `mageflow-server-${TARGET}` there |
| `externalBin: ["mageflow-server"]`     | `binaries/mageflow-server-${TARGET}`     | Tauri runtime target-triple resolution      | WIRED   | Tauri appends target triple; rename step produces exactly `mageflow-server-${TARGET}` format     |

### Requirements Coverage

| Requirement | Source Plan | Description                                                                 | Status        | Evidence                                                                                              |
| ----------- | ----------- | --------------------------------------------------------------------------- | ------------- | ----------------------------------------------------------------------------------------------------- |
| DIST-01     | 02-01       | Single-file installer produced for macOS (universal), Windows x64, Linux x64 | PARTIAL       | Workflow is structured to produce these artifacts; actual production requires live CI run (see Human Verification) |

**Note on DIST-01 status:** The requirement definition in REQUIREMENTS.md says "universal" macOS; the implementation intentionally uses separate arm64 + x86_64 DMGs (not universal-apple-darwin) due to Tauri bug #3355 where universal-apple-darwin breaks sidecar runtime resolution. This is a documented deviation in the SUMMARY's key-decisions and is the correct approach.

**Orphaned requirement check:** REQUIREMENTS.md maps only DIST-01 to Phase 2. Both plans (02-01, 02-02) claim DIST-01 (02-02 claims none completed). No orphaned requirements.

### Anti-Patterns Found

| File                                    | Line | Pattern                                 | Severity | Impact                                                                           |
| --------------------------------------- | ---- | --------------------------------------- | -------- | -------------------------------------------------------------------------------- |
| `.github/workflows/release-desktop.yml` | 5    | `TODO(windows-signing): Configure AZURE_*` | Info  | Intentional deferral; Azure secrets wired but `signCommand` not yet active; Windows ships unsigned for v1.0 as documented |

No blocker or warning anti-patterns. The single TODO is a deliberate, documented decision (Windows unsigned initially, Azure Trusted Signing deferred to v1.1).

### Human Verification Required

#### 1. Tag-triggered workflow execution

**Test:** From the repository root on `main` (after merging the feature branch), run:
```
git tag v0.1.0-rc.1
git push origin v0.1.0-rc.1
```
**Expected:** GitHub Actions tab shows "Release Desktop App" workflow triggered within ~30 seconds; 4 matrix jobs appear (macos-14 arm64, macos-13 x86_64, ubuntu-22.04, windows-latest).
**Why human:** CI execution requires pushing a tag to GitHub. The workflow has never been triggered (feature branch not yet merged to main).

#### 2. Installer artifact production

**Test:** Wait for all 4 CI jobs to complete (expect 15-30 min on first run due to Nuitka compilation).
**Expected:** GitHub Releases shows a draft named "Mageflow Viewer v0.1.0-rc.1" with these artifacts:
- `Mageflow Viewer_*_aarch64.dmg` (macOS arm64)
- `Mageflow Viewer_*_x64.dmg` (macOS x86_64)
- `mageflow-viewer_*_amd64.deb` and/or `mageflow-viewer_*_amd64.AppImage` (Linux)
- `Mageflow Viewer_*_x64-setup.exe` or `.msi` (Windows)
**Why human:** Artifact production is the primary deliverable of DIST-01 and requires a live CI run.

#### 3. macOS .dmg Gatekeeper behavior

**Test:** Download the macOS .dmg on a Mac, double-click to mount, drag app to Applications, double-click app.
**Expected:** Because no Apple Developer account is configured, Gatekeeper shows "Mageflow Viewer cannot be opened because it is from an unidentified developer." User bypasses via right-click > Open > Open, or System Settings > Privacy & Security > Open Anyway. App launches and sidecar starts.
**Why human:** macOS security dialog and app launch require a physical Mac.

#### 4. Fresh-machine install test (ROADMAP Success Criterion 3)

**Test:** On a machine with no Python, Rust, or Node installed, install the app from a downloaded artifact and attempt to connect to a running Hatchet/Redis instance.
**Expected:** App installs and runs fully self-contained — no "missing library" or runtime errors; the Nuitka onefile binary provides all Python dependencies.
**Why human:** Requires a clean machine without dev tooling — cannot simulate locally.

#### 5. Windows SmartScreen behavior (ROADMAP Success Criterion 2)

**Test:** Run the Windows installer on a Windows machine.
**Expected:** SmartScreen shows "More info > Run anyway" (expected for unsigned first-run); installer completes; app launches. Note: Full ROADMAP criterion requires "does not trigger Defender quarantine" which is stricter — Windows ships unsigned for v1.0 so SmartScreen warning is expected.
**Why human:** Windows SmartScreen behavior requires running the installer on real Windows.

### Context: Unsigned Build Decision

Plan 02-02 records the explicit user decision: no Apple Developer account for v1.0. The ROADMAP Success Criterion 2 ("macOS installer passes Gatekeeper; Windows installer is signed and does not trigger Defender quarantine") cannot be fully satisfied by this phase as executed. The 02-RELEASE-VERIFICATION.md documents the Gatekeeper bypass path for users. This is an accepted scope reduction, not a gap — it was a deliberate decision recorded in 02-02-SUMMARY.md key-decisions.

---

_Verified: 2026-03-12T18:00:00Z_
_Verifier: Claude (gsd-verifier)_
