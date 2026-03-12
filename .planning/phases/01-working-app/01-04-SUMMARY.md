---
phase: 01-working-app
plan: "04"
subsystem: startup-ux
tags: [tauri, react, startup-state-machine, health-check, splash-screen, connection-banner]

# Dependency graph
requires:
  - phase: 01-working-app
    plan: "02"
    provides: "invoke('get_sidecar_port'), invoke('restart_sidecar'), invoke('set_tray_status')"
  - phase: 01-working-app
    plan: "03"
    provides: "loadSettings, isTauriEnvironment, Onboarding, SettingsDialog"
provides:
  - Startup state machine hook (useAppStartup) driving full app startup flow
  - SplashScreen component with branded loading UI and status messages
  - ConnectionBanner component for post-launch service-unreachable warning
  - Fully rewired App.tsx with phase-gated rendering and fade transitions
affects:
  - 01-05 (health monitoring and tray status patterns established here)
  - 01-06 (packaged app will use this startup flow for real sidecar binary)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "transitionTo() wrapper ensures every phase change also calls invoke('set_tray_status')"
    - "pollForReady() extracted as reusable function — shared by initial startup and post-onboarding"
    - "30s total timeout split: 20x500ms sidecar port poll + 15s hatchet + 15s redis = 40s worst case; 30s achievable in practice"
    - "Browser dev mode: skips all invoke() calls, uses VITE_API_PORT env var or default 8000"
    - "Health endpoint field-presence check: missing field with status=ok treated as connected (backward compat)"
    - "Sidecar crash detection via listen('sidecar-exit') with polling fallback every 30s"

key-files:
  created:
    - frontend/src/hooks/useAppStartup.ts
    - frontend/src/components/SplashScreen.tsx
    - frontend/src/components/ConnectionBanner.tsx
  modified:
    - frontend/src/App.tsx
    - frontend/src/services/httpTaskClient.ts

key-decisions:
  - "pollForReady extracted from runStartup so both onOnboardingComplete and retrySidecar reuse identical hatchet->redis->ready sequence"
  - "Health field backward compat: if field absent but status=ok, treated as connected — works with both simple and detailed health endpoints"
  - "HttpTaskClient baseUrl: VITE_API_URL fallback only in browser dev mode; Tauri always receives explicit runtime port from startup hook"

# Metrics
duration: 2min
completed: "2026-03-12"
---

# Phase 1 Plan 04: Startup UX and Health-Check Gate Summary

**Startup state machine hook with 7 phases, tray-synced transitions, health-poll gate, branded splash screen, post-launch connection banner, and phase-gated App.tsx with fade transitions**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-03-12T09:24:02Z
- **Completed:** 2026-03-12T09:27:00Z
- **Tasks:** 2
- **Files modified:** 5 (3 created, 2 modified)

## Accomplishments

- `useAppStartup.ts`: Full 7-phase state machine (loading-settings -> onboarding | starting-sidecar -> connecting-hatchet -> connecting-redis -> ready | startup-error). Every phase transition calls `invoke('set_tray_status')` to sync tray icon. `pollForReady()` extracted for reuse. Browser dev mode skips all invoke calls. Both `onOnboardingComplete` and `retrySidecar` callbacks implemented.
- `SplashScreen.tsx`: Branded full-screen dark background with large app name, `Loader2 animate-spin` spinner, and live status message prop.
- `ConnectionBanner.tsx`: Amber warning banner pinned to top of content area with slide-in/out animation, status message, and "Check Settings" button.
- `App.tsx`: Rewired to use `useAppStartup` hook with phase-gated rendering. Splash phases use `transition-opacity duration-500` for fade effect. Post-launch health polling every 30s + `listen('sidecar-exit')` for crash detection. Sidecar crash shows sonner toast with Restart action (no auto-retry). `HttpTaskClient` receives runtime `http://127.0.0.1:${port}` from hook.
- `httpTaskClient.ts`: Constructor uses `VITE_API_URL` only in browser dev mode; Tauri mode requires explicit `baseUrl` from startup hook.

## Task Commits

Each task was committed atomically:

1. **Task 1: Create startup state machine hook and splash screen** — `bad3107` (feat)
2. **Task 2: Create ConnectionBanner and rewire App.tsx** — `dd1cc10` (feat)

## Files Created/Modified

- `frontend/src/hooks/useAppStartup.ts` — 7-phase startup state machine with tray sync, health polling, browser dev mode fallback (201 lines)
- `frontend/src/components/SplashScreen.tsx` — Branded loading screen with spinner and status message (32 lines)
- `frontend/src/components/ConnectionBanner.tsx` — Amber slide-in warning banner with settings link (38 lines)
- `frontend/src/App.tsx` — Phase-gated root component with fade transitions, crash detection, periodic health poll (220 lines)
- `frontend/src/services/httpTaskClient.ts` — Updated constructor to skip VITE_API_URL fallback in Tauri mode

## Decisions Made

- `pollForReady` extracted from the startup sequence so `onOnboardingComplete` and `retrySidecar` share identical hatchet->redis->ready logic without duplication.
- Health endpoint backward compatibility: if `hatchet`/`redis` fields are absent but `status === "ok"`, the hook treats that service as connected. This keeps the startup flow working with both the simple `{"status":"ok"}` response and the richer `{"status":"ok","hatchet":"connected","redis":"connected"}` format.
- `HttpTaskClient` no longer falls back to `VITE_API_URL` in Tauri mode — the startup hook always provides the correct runtime port via `http://127.0.0.1:${port}`.

## Deviations from Plan

None - plan executed exactly as written.

## Self-Check: PASSED

Files verified:
- FOUND: frontend/src/hooks/useAppStartup.ts (201 lines, min 60)
- FOUND: frontend/src/components/SplashScreen.tsx (32 lines, min 30)
- FOUND: frontend/src/components/ConnectionBanner.tsx (38 lines, min 25)
- FOUND: frontend/src/App.tsx (220 lines, min 40)
- FOUND: frontend/src/services/httpTaskClient.ts (modified)

Commits verified:
- bad3107 — feat(01-04): create startup state machine hook and splash screen
- dd1cc10 — feat(01-04): create ConnectionBanner and rewire App.tsx with startup gate

TypeScript: `npx tsc --noEmit` exits 0 with no errors.

---
*Phase: 01-working-app*
*Completed: 2026-03-12*
