# Feature Research

**Domain:** Desktop app packaging — web frontend (React) + native backend (Python sidecar) via Tauri v2
**Researched:** 2026-03-12
**Confidence:** MEDIUM — Tauri v2 is current and well-documented; sidecar lifecycle management is an emerging area with some rough edges confirmed by community issues

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = product feels incomplete or broken.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Single-file installer | Users expect one download → one install, not "install Python then run our app" | LOW | Tauri v2 produces .dmg / .exe (NSIS) / .deb / .AppImage out of the box; Nuitka binary bundled inside |
| Sidecar auto-start on app launch | Users never manually start backend processes | MEDIUM | Tauri's `shell` plugin spawns the sidecar; must poll for ready state before showing UI (Python HTTP server needs ~1-3s cold start) |
| Sidecar auto-kill on app exit | Leaving orphan processes is a critical UX failure; users will find zombie Python processes and blame the app | MEDIUM | Tauri does NOT kill sidecars automatically; must hook `on_window_close` and `on_exit` in Rust main.rs; stdout-based shutdown signal preferred over process.kill() for PyInstaller/Nuitka compat |
| Loading / startup state | App must not show blank or broken UI while Python backend initializes | LOW | Splash window or loading overlay until sidecar health check passes; Tauri supports splash screens natively |
| Connection settings UI | Users provide Hatchet URL + Redis URL; no hardcoded defaults | MEDIUM | `tauri-plugin-store` persists settings to disk; first-launch onboarding screen required |
| Settings persistence across restarts | Users enter connection details once | LOW | `tauri-plugin-store` handles this; settings stored in OS app data directory |
| Cross-platform packaging | macOS + Windows + Linux is the explicit requirement | HIGH | Three separate CI build jobs needed; macOS requires code signing + notarization; Windows requires NSIS signing; Linux .deb + .AppImage; architecture-specific sidecar binaries required (x86_64 and aarch64 suffixes) |
| Error display when backend fails | Users need to know if the Python sidecar crashed or connection to Hatchet/Redis failed | MEDIUM | Frontend must distinguish: (a) sidecar not started yet, (b) sidecar crashed, (c) external service unreachable |
| App version display | Users need to know what version they're running for support | LOW | Tauri exposes app version via `app.getVersion()`; show in About dialog or settings page |

### Differentiators (Competitive Advantage)

Features that set the product apart. Not required for launch, but valued.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Auto-updater | Users get fixes without manual reinstall; critical for a monitoring tool users run daily | MEDIUM | `tauri-plugin-updater` handles download + install; requires signing key pair, update endpoint (GitHub Releases works), and CI artifact publication; Windows exits app on install (OS limitation) |
| System tray with connection status | App persists as a background monitor; users can show/hide without taskbar clutter | MEDIUM | `tauri-plugin-system-tray` in Tauri v2; tray icon color/badge can reflect connection state (green=connected, red=error); adds "Show", "Quit" menu items |
| Package manager distribution (brew, choco, snap) | Developers already have these tools; `brew install mageflow-viewer` is a frictionless install path vs downloading a DMG | MEDIUM | Requires maintaining tap repo (homebrew) and formula automation from CI; Chocolatey requires separate nuspec; high value for developer audience |
| Sidecar crash auto-recovery | Backend restarts transparently if it crashes without requiring app relaunch | HIGH | No official Tauri plugin yet (issue #3062 open as of 2025); must implement manual restart loop in Rust using `CommandEvent::Terminated`; community tauri-sidecar-manager crate exists but is third-party |
| Port conflict detection and dynamic allocation | App fails gracefully if default port is in use instead of silently breaking | LOW | `tauri-plugin-network` provides `findAvailablePort`; pass chosen port to sidecar via CLI arg; tell frontend via Tauri event |
| Native OS notifications on workflow events | Push alerts when monitored tasks fail or complete | HIGH | Defer — requires backend to push events, not just serve on demand; architectural scope creep for v1 |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Bundled Redis + Hatchet services | "Zero-config" appeal — just open and it works | Massively increases app size, startup time, and operational complexity; requires embedded database lifecycle management; contradicts the explicit scope decision in PROJECT.md | Keep as viewer-only; document clearly that external infrastructure is required |
| In-app Python environment management | "Install Python for me" UX | Nuitka compiles to native binary — there is no Python runtime to manage; this feature would only apply to PyInstaller-based apps | N/A — Nuitka eliminates this entirely |
| App Store distribution (Mac App Store, Microsoft Store) | Broader reach, trust signals | Both stores have sandboxing requirements that break sidecar process spawning and local HTTP server patterns; review timelines are unpredictable | GitHub Releases + Homebrew/Choco tap provides equivalent discoverability for a developer tool without sandbox constraints |
| Real-time everything over WebSocket | Lower perceived latency | Requires maintaining persistent connection state in sidecar and frontend; polling on a short interval (2-5s) is sufficient for a workflow monitor and far simpler to implement and debug | HTTP polling from TanStack Query with `refetchInterval` |
| Multi-account / multi-connection profiles | Power user feature | Adds state management complexity to both UI and connection lifecycle before core value is proven | Single active connection at a time; users can relaunch with different settings |

---

## Feature Dependencies

```
[Single-file installer]
    └──requires──> [Nuitka sidecar binary]
                       └──requires──> [Cross-platform CI build matrix]

[App launch UX]
    └──requires──> [Sidecar auto-start]
                       └──requires──> [Sidecar health check / ready poll]
                                          └──requires──> [Loading state UI]

[Connection settings]
    └──requires──> [Settings persistence (tauri-plugin-store)]
    └──enhances──> [Sidecar startup] (port + target URLs passed to sidecar at start)

[Auto-updater]
    └──requires──> [Cross-platform packaging]
    └──requires──> [CI release pipeline with signing]

[System tray]
    └──enhances──> [Connection status] (tray icon reflects health)

[Sidecar crash auto-recovery]
    └──requires──> [Sidecar auto-start] (same mechanism, looped)

[Package manager distribution]
    └──requires──> [CI release pipeline]
    └──requires──> [Cross-platform packaging]
```

### Dependency Notes

- **Sidecar auto-start requires health check polling:** The sidecar is a Python HTTP server. Tauri spawns it asynchronously; the frontend must not attempt API calls until the server responds to a `GET /health`. Typical cold start is 1-3 seconds for a Nuitka binary.
- **Cross-platform packaging is a prerequisite for everything distribution-related:** Auto-updater, package managers, and GitHub Releases all depend on having signed, reproducible artifacts from CI. This must land before any distribution feature.
- **Settings persistence enhances sidecar startup:** Connection URLs (Hatchet endpoint, Redis URL) must be read from the store and passed to the sidecar binary as CLI arguments at launch time, not fetched later.
- **Auto-updater conflicts with App Store distribution:** macOS sandbox requirements prevent the updater from writing to the app bundle location. Do not combine.

---

## MVP Definition

### Launch With (v1)

Minimum viable product — what's needed to ship a usable monitoring tool.

- [ ] Single-file installer for macOS (Universal), Windows x64, Linux x64 — core distribution requirement
- [ ] Sidecar auto-start with health check polling before UI is shown — prevents broken startup experience
- [ ] Sidecar auto-kill on app exit — prevents orphan processes
- [ ] First-launch onboarding screen for connection settings — required since no defaults exist
- [ ] Settings persistence across restarts (`tauri-plugin-store`) — users must not re-enter credentials
- [ ] Loading/startup UI state — spinner or progress while sidecar initializes
- [ ] Error display for sidecar crash and external connection failure — users must know what went wrong
- [ ] Cross-platform CI build pipeline with signing — macOS notarization, Windows NSIS signing, Linux packages
- [ ] App version display — support and debugging baseline

### Add After Validation (v1.x)

Features to add once core install → connect → view flow is working.

- [ ] Auto-updater — add when release cadence is established and users are complaining about manual updates
- [ ] Package manager distribution (brew tap + choco) — add when GitHub Releases are stable and CI pipeline is proven
- [ ] Port conflict detection + dynamic allocation — add when first user reports "app shows blank screen" from port conflict
- [ ] System tray integration — add when users request background monitoring without keeping window open

### Future Consideration (v2+)

Features to defer until product-market fit is established.

- [ ] Sidecar crash auto-recovery — defer; requires non-trivial Rust work without an official plugin; manual relaunch acceptable for v1
- [ ] Native OS notifications on workflow events — defer; requires backend event-push architecture change
- [ ] Multi-connection profiles — defer; validate single-connection model first

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Single-file installer | HIGH | MEDIUM | P1 |
| Sidecar auto-start + health check | HIGH | MEDIUM | P1 |
| Sidecar auto-kill on exit | HIGH | LOW | P1 |
| First-launch onboarding + settings | HIGH | LOW | P1 |
| Settings persistence | HIGH | LOW | P1 |
| Loading / startup UI | HIGH | LOW | P1 |
| Error display (sidecar + connection) | HIGH | MEDIUM | P1 |
| Cross-platform CI + signing | HIGH | HIGH | P1 |
| App version display | LOW | LOW | P1 |
| Auto-updater | HIGH | MEDIUM | P2 |
| Package manager distribution | MEDIUM | MEDIUM | P2 |
| Port conflict detection | MEDIUM | LOW | P2 |
| System tray | MEDIUM | MEDIUM | P2 |
| Sidecar crash auto-recovery | MEDIUM | HIGH | P3 |
| Native notifications | LOW | HIGH | P3 |

**Priority key:**
- P1: Must have for launch
- P2: Should have, add when possible
- P3: Nice to have, future consideration

---

## Competitor Feature Analysis

| Feature | Electron apps (e.g., VS Code, Postman) | Tauri apps (e.g., Tauri examples) | Our Approach |
|---------|----------------------------------------|-----------------------------------|--------------|
| Installer size | 80-150 MB (bundles Chromium) | < 10 MB shell + sidecar size | ~10-60 MB total (Nuitka binary dominates) |
| Auto-updater | electron-updater; mature ecosystem | tauri-plugin-updater; built-in, signature-required | tauri-plugin-updater via GitHub Releases |
| System tray | electron tray; mature | tauri-plugin-system-tray; functional | tauri-plugin-system-tray for v1.x |
| Sidecar/backend management | Child process via Node.js; process tracking is manual | Rust Command API; also manual; no official lifecycle plugin | Manual Rust lifecycle in main.rs with health check loop |
| Cross-platform packaging | electron-builder; mature | tauri bundler; built-in | tauri bundler via GitHub Actions |
| Package manager distribution | Common for Electron apps | Less common; pattern established by OSS adopters | Homebrew tap + Chocolatey for developer reach |

---

## Sources

- [Tauri v2 Sidecar Documentation](https://v2.tauri.app/develop/sidecar/) — HIGH confidence (official docs)
- [Tauri v2 Updater Plugin](https://v2.tauri.app/plugin/updater/) — HIGH confidence (official docs)
- [Tauri v2 Store Plugin](https://v2.tauri.app/plugin/store/) — HIGH confidence (official docs)
- [Tauri v2 System Tray](https://v2.tauri.app/learn/system-tray/) — HIGH confidence (official docs)
- [Tauri v2 Deep Linking](https://v2.tauri.app/plugin/deep-linking/) — HIGH confidence (official docs)
- [Tauri v2 Distribute](https://v2.tauri.app/distribute/) — HIGH confidence (official docs)
- [Feature: Sidecar Lifecycle Management Plugin · Issue #3062](https://github.com/tauri-apps/plugins-workspace/issues/3062) — HIGH confidence (confirms no official plugin exists as of 2025)
- [Kill process on exit · tauri-apps/tauri · Discussion #3273](https://github.com/tauri-apps/tauri/discussions/3273) — HIGH confidence (confirms manual kill required)
- [example-tauri-v2-python-server-sidecar](https://github.com/dieharders/example-tauri-v2-python-server-sidecar) — MEDIUM confidence (community example, stdout-based shutdown pattern confirmed)
- [Tauri — How to Start/Stop a sidecar and pipe stdout/stderr](https://medium.com/@samuelint/tauri-how-to-start-stop-a-sidecar-and-pipe-sidecar-stdout-stderr-to-app-logs-from-rust-8f81a92111ad) — MEDIUM confidence (community, verified against official docs)
- [Nuitka vs PyInstaller comparison](https://krrt7.dev/en/blog/nuitka-vs-pyinstaller) — MEDIUM confidence (community benchmark, consistent with multiple sources)
- [Persistent state in Tauri apps - Aptabase](https://aptabase.com/blog/persistent-state-tauri-apps) — MEDIUM confidence (community, consistent with official plugin docs)

---
*Feature research for: Desktop app packaging — Tauri v2 + Python sidecar (Mageflow Viewer)*
*Researched: 2026-03-12*
