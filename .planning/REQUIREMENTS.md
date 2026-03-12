# Requirements: Mageflow Viewer Desktop App

**Defined:** 2026-03-12
**Core Value:** Users can install a single app and immediately visualize mageflow workflows without setting up separate servers

## v1 Requirements

### Packaging

- [x] **PKG-01**: Python backend compiled to native binary via Nuitka (standalone, per-platform)
- [x] **PKG-02**: Tauri v2 shell hosts React frontend using system webview
- [ ] **PKG-03**: Sidecar auto-starts on app launch with dynamic port allocation
- [x] **PKG-04**: Sidecar health-check polling gates UI rendering (no blank/broken state)
- [ ] **PKG-05**: Sidecar auto-killed on app exit (no orphaned processes)
- [x] **PKG-06**: Loading/startup UI shown while sidecar initializes

### Distribution

- [ ] **DIST-01**: Single-file installer produced for macOS (universal), Windows x64, Linux x64
- [ ] **DIST-02**: Built-in auto-updater checks for and applies new releases
- [ ] **DIST-03**: App distributed via Homebrew tap (macOS), Chocolatey (Windows), and apt/snap (Linux)

### User Experience

- [x] **UX-01**: First-launch onboarding screen for Hatchet and Redis connection settings
- [x] **UX-02**: Connection settings persist across app restarts via tauri-plugin-store
- [x] **UX-03**: Meaningful error display for sidecar crash and external connection failures
- [ ] **UX-04**: System tray integration with connection status indicator and show/hide/quit actions

## v2 Requirements

### Resilience

- **RES-01**: Sidecar crash auto-recovery (restart without app relaunch)
- **RES-02**: Port conflict detection with user-friendly messaging

### Advanced

- **ADV-01**: Native OS notifications on workflow events (task failures/completions)
- **ADV-02**: Multi-connection profiles for switching between environments

## Out of Scope

| Feature | Reason |
|---------|--------|
| Bundled Redis/Hatchet services | Viewer-only by design; users have existing infrastructure |
| App Store distribution (Mac/Microsoft) | Sandbox requirements break sidecar spawning and local HTTP servers |
| Mobile app | Desktop only for v1 |
| WebSocket real-time streaming | HTTP polling via TanStack Query sufficient for workflow monitoring |
| Cross-platform CI signing | Deferred — builds work unsigned for initial development; signing added when distributing |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| PKG-01 | Phase 1 | Complete |
| PKG-02 | Phase 1 | Complete |
| PKG-03 | Phase 1 | Pending |
| PKG-04 | Phase 1 | Complete |
| PKG-05 | Phase 1 | Pending |
| PKG-06 | Phase 1 | Complete |
| DIST-01 | Phase 2 | Pending |
| DIST-02 | Phase 3 | Pending |
| DIST-03 | Phase 3 | Pending |
| UX-01 | Phase 1 | Complete |
| UX-02 | Phase 1 | Complete |
| UX-03 | Phase 1 | Complete |
| UX-04 | Phase 1 | Pending |

**Coverage:**
- v1 requirements: 13 total
- Mapped to phases: 13
- Unmapped: 0

---
*Requirements defined: 2026-03-12*
*Last updated: 2026-03-12 — traceability populated after roadmap creation*
