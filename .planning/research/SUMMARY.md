# Project Research Summary

**Project:** Mageflow Viewer — Tauri v2 desktop app packaging
**Domain:** Cross-platform desktop app — Tauri v2 shell + Python sidecar (Nuitka) + React/Vite frontend
**Researched:** 2026-03-12
**Confidence:** MEDIUM-HIGH

## Executive Summary

Mageflow Viewer is a brownfield desktop packaging problem: an existing React/Vite frontend and Python/FastAPI backend (already working as a web app) must be bundled into a standalone cross-platform desktop installer that requires no external Python runtime on user machines. The industry standard approach for this exact combination is Tauri v2 as the native shell (macOS .dmg / Windows .msi / Linux .deb+AppImage from one codebase, 3-10 MB shell), Nuitka to compile the Python server to a native C binary per target platform, and a GitHub Actions matrix build that produces platform-specific artifacts. The architecture is deliberately simple: Rust manages the sidecar process lifecycle while all workflow data flows directly over HTTP between the React webview and the Python server. Rust does not proxy API traffic.

The two most consequential design decisions are (1) Nuitka over PyInstaller — Nuitka's compiled binary means `child.kill()` terminates the process cleanly, PyInstaller's bootloader does not; and (2) dynamic port allocation — hardcoding a port fails when another process owns it and produces a silent broken state. Both decisions must be made and implemented in Phase 1 because retrofitting them later requires changes across all three layers (Rust, Python, React). The existing code already has the right shape: `HttpTaskClient` uses a base URL, FastAPI has a CLI entry point, and the React build produces a static `dist/` directory.

The primary risks are operational, not architectural. Nuitka cannot cross-compile between OS families, so CI must run four separate native runners. Dynamic imports in gRPC/protobuf (used by hatchet-sdk) are invisible to Nuitka's static tracer and require explicit `--include-package` flags. macOS notarization requires the sidecar binary to be individually signed before placement in the Tauri bundle — Tauri does not do this automatically. Finally, the Tauri updater signing private key must be backed up with documented recovery steps before v1 ships; there is no key rotation mechanism for already-distributed binaries.

## Key Findings

### Recommended Stack

Tauri v2 (2.10.3, stable since Oct 2024) is the clear choice for the native shell: it produces signed, notarized installers for all three platforms from one codebase, supports first-class sidecar management via `tauri-plugin-shell`, and has a built-in updater plugin. Bundle sizes are 3-10 MB compared to 100-200 MB for Electron because it uses the OS webview. Nuitka 4.0.4 compiles the Python FastAPI server to a native C binary that starts in ~100-300ms and is killed cleanly by Tauri — unlike PyInstaller whose bootloader process survives `child.kill()`.

**Core technologies:**
- Tauri v2 (2.10.3): Desktop shell, cross-platform packaging, sidecar lifecycle — only v2 APIs, v1 is maintenance mode
- Nuitka 4.0.4: Python → native binary compilation — `--mode=standalone` for distribution (not `--onefile` on Windows due to Defender false positives)
- React 18 + Vite 5: Frontend UI — already in use, no changes required; built output is what Tauri serves
- `tauri-plugin-shell` 2.3.4: Sidecar spawn/kill/stdout — required, no alternative for sidecar management
- `tauri-plugin-updater` 2.10.0: In-app auto-update with mandatory signature verification
- `tauri-plugin-store`: Settings persistence (connection URLs) across restarts
- Rust stable ≥1.77.2: Required by all Tauri v2 plugins

### Expected Features

The MVP is entirely focused on the install → connect → view flow. Distribution, sidecar lifecycle, and settings persistence are all table stakes — users will not tolerate needing to start a Python server manually or re-enter connection details on every launch. See `.planning/research/FEATURES.md` for full feature dependency graph.

**Must have (table stakes — v1):**
- Single-file installer (macOS Universal, Windows x64, Linux x64) — core distribution requirement
- Sidecar auto-start with health-check polling before UI is shown — prevents broken startup
- Sidecar auto-kill on app exit — prevents orphan processes occupying ports
- First-launch onboarding screen for Hatchet + Redis connection settings
- Settings persistence across restarts (`tauri-plugin-store`)
- Loading/splash UI during sidecar startup (1-3 second cold start)
- Error display for sidecar crash and external service unreachable
- Cross-platform CI build pipeline with code signing + notarization
- App version display

**Should have (differentiators — v1.x after validation):**
- Auto-updater via `tauri-plugin-updater` + GitHub Releases
- Package manager distribution (Homebrew tap + Chocolatey)
- Dynamic port conflict detection and allocation
- System tray with connection status indicator

**Defer (v2+):**
- Sidecar crash auto-recovery (no official Tauri plugin; manual Rust work required)
- Native OS notifications on workflow events (requires backend event-push architecture)
- Multi-connection profiles (validate single-connection model first)
- App Store distribution (sandboxing breaks sidecar process spawning)

### Architecture Approach

The architecture is a three-layer sandwich: Rust core manages the Python sidecar as an OS process and handles port allocation + health gating; the React webview calls the Python FastAPI server directly over HTTP for all workflow data; Tauri IPC is used only for port discovery and lifecycle events, never for data proxying. The Python sidecar must be modified minimally: accept `--port` and `--host` CLI arguments, expose a `GET /api/health` endpoint, and remove static file serving (Tauri serves React directly from `src-tauri/frontend-dist/`). The only React change needed is reading the port from `invoke('get_backend_port')` instead of a hard-coded env var. See `.planning/research/ARCHITECTURE.md` for detailed data flow diagrams and code examples.

**Major components:**
1. React Webview — render workflow graph; communicates with Rust via Tauri IPC for port, Python sidecar via HTTP for data
2. Rust Core (`src-tauri/src/lib.rs`) — sidecar spawn/kill, port allocation, health-check polling, readiness gating
3. Python Sidecar (FastAPI + Nuitka binary) — query Redis via Rapyer, serve REST API; receives port as CLI arg
4. Nuitka CI Build Pipeline — compile Python to native binary per platform; deposit in `src-tauri/binaries/` with target-triple suffix

### Critical Pitfalls

1. **Orphaned sidecar processes on app exit** — Tauri does NOT kill child processes automatically. Hook both `RunEvent::ExitRequested` and `RunEvent::Exit` in `main.rs` to call `child.kill()`. Must be implemented in Phase 1 or every test run leaks a process.

2. **Sidecar startup race (no health check)** — The frontend must not issue API calls until the Python server responds to `GET /api/health`. Implement a Rust polling loop (100ms interval, 30s timeout) that emits a `backend-ready` event; React waits for this event before making any requests. A `setTimeout` delay is never acceptable.

3. **Nuitka missing dynamic imports (gRPC/protobuf)** — gRPC and protobuf use dynamic module loading invisible to Nuitka's static tracer. Must add `--include-package=grpc --include-package=google.protobuf --include-package-data=hatchet_sdk` and run a smoke test on a clean VM (no Python installed) before any CI release.

4. **macOS notarization rejects unsigned sidecar binary** — Tauri signs its own Rust binary but not sidecar binaries. The Nuitka binary must be individually codesigned with `--timestamp --options runtime` before being placed in `src-tauri/binaries/`. Do not set the Developer ID certificate to "Always Trust" in CI keychains — this causes signing failures.

5. **Tauri updater private key loss = permanent update blackout** — There is no key rotation mechanism. Once a binary is shipped with a baked-in public key, updates must be signed by the matching private key forever. Store in two independent locations (CI secret + team password manager) and document recovery steps before v1 ships.

**Additional pitfalls to avoid:**
- Nuitka cannot cross-compile between OS families — requires a separate native CI runner per platform
- Nuitka `--onefile` triggers Windows Defender false positives — use `--standalone` (directory) for Windows
- Tauri v2 production builds enforce capabilities strictly — `shell:allow-spawn` and `shell:allow-execute` must be in `capabilities/default.json` or sidecar silently fails to start
- CSP in production builds blocks `fetch()` to localhost — add `connect-src http://127.0.0.1:<port>` to `tauri.conf.json`
- Sidecar binary must be named with target-triple suffix (`mageflow-server-aarch64-apple-darwin`) — automate rename in CI with `rustc --print host-tuple`

## Implications for Roadmap

All four research files agree on a natural phase order driven by hard build dependencies: the Nuitka binary must exist before Tauri can bundle it; the Rust shell and health-check logic must exist before frontend integration; CI and signing must exist before any release. The architecture research makes the build order explicit.

### Phase 1: Sidecar Foundation
**Rationale:** Everything else depends on a correctly compiled, correctly named, clean-shutdown Python binary. Nuitka compilation with gRPC/protobuf includes, smoke testing on a clean VM, target-triple naming convention, and the `GET /api/health` endpoint must all be established and validated before any Tauri work begins. This phase also produces the minimal FastAPI modifications (accept `--port`/`--host` args, remove static file serving, add `/health`). PITFALLS 4 (Nuitka missing modules) and 5 (target triple naming) are addressed here.
**Delivers:** Nuitka-compiled sidecar binary that starts cleanly, serves the API, and passes a smoke test on a clean machine with no Python installed.
**Addresses:** Single-file installer prerequisite, cross-platform CI prerequisite
**Avoids:** Nuitka missing modules, target-triple naming errors, PyInstaller orphan process issue

### Phase 2: Tauri Shell + Rust Lifecycle
**Rationale:** The Rust core is the orchestrator for the entire app. Port allocation, health-check polling, sidecar spawn/kill, capabilities config, and CSP must all be correct before any frontend or distribution work. PITFALLS 1 (orphaned processes), 2 (startup race), 6 (capabilities), and 10 (CSP) are all Phase 2 concerns. This phase produces a working app on the developer's own machine.
**Delivers:** Tauri app that spawns the sidecar, waits for readiness, shows a loading screen, gates the webview, and cleans up on exit.
**Uses:** `tauri-plugin-shell`, dynamic port allocation, `RunEvent::Exit` hooks, `capabilities/default.json`, CSP configuration
**Implements:** Rust core component; sidecar ↔ Rust boundary

### Phase 3: Frontend Integration + Settings
**Rationale:** With Rust lifecycle working, the one-line React change (port from `invoke('get_backend_port')` instead of env var) and the settings/onboarding UI can land. These are low-risk changes against a working foundation. `tauri-plugin-store` for settings persistence is a simple addition here.
**Delivers:** End-to-end working app: launch → connect settings → sidecar starts → workflow data visible.
**Uses:** `tauri-plugin-store`, Tauri IPC `invoke()`, first-launch onboarding screen
**Implements:** React webview ↔ Rust boundary; connection settings persistence

### Phase 4: Cross-Platform CI Build Pipeline + Signing
**Rationale:** Signing and multi-platform CI are prerequisites for distribution. This phase is the highest-complexity phase (four native runners, macOS notarization, Windows Defender, sidecar codesigning, artifact collection). PITFALLS 3 (no cross-compilation), 8 (macOS notarization), and 9 (Windows Defender / `--standalone`) are all addressed here.
**Delivers:** GitHub Actions pipeline that produces signed, notarized installers for macOS (arm64 + x86_64), Windows, and Linux on every tagged release.
**Uses:** `tauri-action` GitHub Action, Nuitka-Action, Apple Developer ID, macOS notarization, EV code signing for Windows
**Avoids:** Cross-compilation assumption, notarization failure, Windows Defender quarantine

### Phase 5: Distribution Channels + Auto-Updater
**Rationale:** After CI produces stable, signed artifacts, add the update and distribution layer. Updater private key backup (PITFALL 7) must be documented before this ships. Package manager taps are optional but high-value for the developer audience.
**Delivers:** Auto-updater via `tauri-plugin-updater` + GitHub Releases; Homebrew tap; Chocolatey package.
**Uses:** `tauri-plugin-updater`, `tauri signer generate`, GitHub Releases, Homebrew cask formula automation
**Avoids:** Updater private key loss; implements system tray (v1.x) if prioritized

### Phase Ordering Rationale

- **Sidecar first:** Nuitka binary must exist in `src-tauri/binaries/` before `tauri build` can run. Cannot parallelize with Tauri work.
- **Rust lifecycle before frontend integration:** Frontend port discovery requires the Rust `get_backend_port` command to exist. The `backend-ready` event must exist before React can listen for it.
- **Local working app before CI pipeline:** Attempting to debug CI for a multi-platform build when the local app doesn't work yet wastes time. Validate all three layers locally before adding CI complexity.
- **CI pipeline before distribution:** Auto-updater, Homebrew, and Chocolatey all require stable signed artifacts from CI. Do not begin distribution work until CI is proven.
- **Updater key backup in Phase 5 checklist:** The key is generated in Phase 5 before any release; the phase checklist must include explicit backup verification before any installer ships.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 4 (CI/CD Pipeline):** Nuitka-Action caching strategy, macOS CI keychain import process, EV certificate procurement process, and the exact codesign command for the sidecar binary are all operationally complex. Recommend a dedicated research step on CI signing workflows before Phase 4 planning.
- **Phase 5 (Distribution):** Homebrew tap automation (formula SHA256 update on release), Chocolatey nuspec requirements, and auto-updater endpoint format (GitHub Releases `latest.json` schema) should be verified against current platform requirements at planning time.

Phases with standard, well-documented patterns (can skip research-phase):
- **Phase 1 (Sidecar Foundation):** Nuitka compilation and FastAPI packaging are well-documented; PITFALLS.md already covers the gRPC/protobuf include flags.
- **Phase 2 (Tauri Shell):** ARCHITECTURE.md contains working Rust code examples for all Phase 2 concerns. Official Tauri docs are comprehensive.
- **Phase 3 (Frontend Integration):** Single `HttpTaskClient` change and `tauri-plugin-store` integration follow documented patterns with no ambiguity.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Tauri v2 official docs verified; Nuitka version confirmed on PyPI; version compatibility matrix explicit |
| Features | MEDIUM-HIGH | Official Tauri plugin docs high confidence; sidecar lifecycle management gaps confirmed via GitHub issues |
| Architecture | HIGH | Verified against official Tauri v2 docs + direct codebase inspection of existing `server.py`, `commands.py`, and `HttpTaskClient.ts` |
| Pitfalls | MEDIUM-HIGH | Most findings from official docs or confirmed GitHub issues; macOS codesigning flow from community report but consistent with Apple docs |

**Overall confidence:** MEDIUM-HIGH

### Gaps to Address

- **Nuitka + hatchet-sdk gRPC compatibility:** hatchet-sdk uses gRPC async generators, which had a specific Nuitka bug (issue #3608). Must verify the installed hatchet-sdk version works correctly with Nuitka 4.0.4 in Phase 1 smoke tests. If incompatible, fallback is to keep the Python server as a `--standalone` directory and address the specific gRPC plugin flags.
- **Windows EV certificate timeline:** EV code signing certificates take days to weeks to procure. This must be initiated at Phase 4 planning time, not at build time.
- **`tauri-plugin-store` settings migration:** If connection settings schema changes between releases, there is no built-in migration mechanism. Simple for v1 (no existing installs), but plan for it before v1.x ships.
- **Nuitka `--standalone` directory as `externalBin`:** The standard examples use `--onefile`. Using `--standalone` with a directory output as a Tauri `externalBin` is documented as supported but less tested in the community. Validate in Phase 1 that Tauri correctly bundles and executes a `--standalone` directory output.

## Sources

### Primary (HIGH confidence)
- [Tauri v2 Sidecar Docs](https://v2.tauri.app/develop/sidecar/) — sidecar spawn, target-triple naming, capabilities
- [Tauri v2 Updater Plugin Docs](https://v2.tauri.app/plugin/updater/) — updater setup, signing, key requirements
- [Tauri v2 GitHub Actions Pipeline Docs](https://v2.tauri.app/distribute/pipelines/github/) — multi-platform matrix build
- [Tauri v2 Capabilities/Security Model](https://v2.tauri.app/security/capabilities/) — permissions required for shell spawn
- [Tauri v2 CSP Docs](https://v2.tauri.app/security/csp/) — CSP configuration for localhost fetch
- [Tauri v2 macOS Code Signing](https://v2.tauri.app/distribute/sign/macos/) — notarization requirements
- [Nuitka User Manual](https://nuitka.net/user-documentation/user-manual.html) — `--mode=standalone`, `--mode=onefile`, include flags
- [Nuitka macOS cross-compilation page](https://nuitka.net/info/macos-cross-compile.html) — universal binary not supported confirmation
- [Nuitka PyPI page](https://pypi.org/project/Nuitka/) — confirmed version 4.0.4 (March 2026)
- [Nuitka-Action GitHub Action](https://github.com/Nuitka/Nuitka-Action) — CI compilation automation

### Secondary (MEDIUM confidence)
- [example-tauri-v2-python-server-sidecar (dieharders)](https://github.com/dieharders/example-tauri-v2-python-server-sidecar) — real-world FastAPI + Tauri v2 sidecar pattern
- [GitHub issue: macOS codesigning/notarization failure with ExternalBin #11992](https://github.com/tauri-apps/tauri/issues/11992) — sidecar binary signing requirement
- [GitHub issue: Sidecar not killed via GUI quit #8139](https://github.com/tauri-apps/tauri/issues/8139) — confirms manual kill required
- [GitHub issue: Sidecar Lifecycle Management Plugin #3062](https://github.com/tauri-apps/plugins-workspace/issues/3062) — confirms no official lifecycle plugin
- [GitHub issue: Windows Defender flags Nuitka onefile #2685](https://github.com/Nuitka/Nuitka/issues/2685) — `--standalone` recommended for Windows distribution
- [GitHub issue: Nuitka gRPC async generator bug #3608](https://github.com/Nuitka/Nuitka/issues/3608) — gRPC compatibility concern
- [DEV Community: Shipping a production macOS Tauri 2.0 app](https://dev.to/0xmassi/shipping-a-production-macos-app-with-tauri-20-code-signing-notarization-and-homebrew-mc3) — Homebrew cask and signing workflow
- [Nuitka FastAPI packaging](https://blog.thoughtparameters.com/post/nuitka_packaging_for_web_frameworks/) — FastAPI/uvicorn Nuitka compilation gotchas
- Direct codebase inspection: `libs/mage-voyance/visualizer/server.py`, `commands.py`, `frontend/src/services/httpTaskClient.ts`

---
*Research completed: 2026-03-12*
*Ready for roadmap: yes*
