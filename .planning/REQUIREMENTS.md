# Requirements: Mage Voyance — Secure Secret Management & Connection Loading Fix

**Defined:** 2026-03-26
**Core Value:** Secrets are persisted securely and delivered to the sidecar before any service initialization, enabling silent credential-free launches after first setup.

## v1 Requirements

### Security Dependencies

- [x] **SEC-01**: tauri-plugin-shell upgraded to >= 2.2.1 (CVE-2025-31477 patched)
- [x] **SEC-02**: Shell plugin capabilities set to `open: false`

### Encrypted Storage

- [x] **STOR-01**: Secrets encrypted with AES-256-GCM using machine-derived key (HKDF-SHA256 from machine ID)
- [x] **STOR-02**: Encrypted secrets.bin stored in Tauri app data directory
- [x] **STOR-03**: Secrets file uses versioned format with prepended nonce (fresh random nonce per save)
- [x] **STOR-04**: Machine ID derived cross-platform (IOPlatformUUID on macOS, MachineGuid on Windows, /etc/machine-id on Linux)
- [x] **STOR-05**: Decryption failure (tampered file, wrong machine) handled gracefully with re-prompt

### Secret Delivery

- [x] **DLVR-01**: Secrets delivered to Python sidecar via stdin pipe (never CLI args or env vars)
- [x] **DLVR-02**: Python sidecar blocks all service initialization until secrets received from stdin
- [x] **DLVR-03**: Sidecar emits readiness signal on stdout after successful initialization
- [x] **DLVR-04**: Tauri waits for sidecar readiness signal with configurable timeout
- [x] **DLVR-05**: Startup timeout produces actionable error in UI

### IPC Authentication

- [x] **AUTH-01**: Ephemeral IPC token generated per app launch (64-char alphanumeric)
- [x] **AUTH-02**: Token passed to sidecar via stdin alongside secrets
- [x] **AUTH-03**: FastAPI middleware validates X-IPC-Token header on every request
- [x] **AUTH-04**: Requests without valid token rejected with 403

### Frontend & UX

- [x] **UX-01**: First-run setup UI for entering Redis URL and Hatchet token
- [x] **UX-02**: Credential validation (test connectivity) before saving
- [x] **UX-03**: Subsequent launches load secrets silently — no prompts
- [x] **UX-04**: Health endpoint reflects actual connection status after secret-based initialization
- [x] **UX-05**: Connection failure surfaces actionable error with "check credentials" guidance

### Integration Tests

- [x] **TEST-01**: Integration test verifying successful connection when valid credentials exist in DB
- [x] **TEST-02**: Integration test verifying correct behavior when no credentials exist (first-run flow)

## v2 Requirements

### Transport Hardening

- **SOCK-01**: Unix domain socket IPC between Tauri and sidecar (macOS/Linux)
- **SOCK-02**: Socket created in 0700-permissioned directory with 0600 socket permissions
- **SOCK-03**: TCP loopback fallback on Windows with token auth
- **SOCK-04**: Stale socket cleanup on crash recovery

### Secret Management

- **SMGT-01**: Graceful secret rotation without full app restart
- **SMGT-02**: User can update individual credentials from settings UI

## Out of Scope

| Feature | Reason |
|---------|--------|
| OS keychain/credential store | Causes auth prompts on unsigned dev builds |
| OAuth/SSO | Local dev tool, not multi-tenant SaaS |
| Multi-user secret sharing | Secrets are machine-tied by design |
| Windows named pipes | Limited uvicorn support; TCP + token auth suffices |
| Tauri Stronghold plugin | Deprecated, migration debt, heavy for simple credential storage |
| Environment variable secret delivery | Visible via `ps aux` and `/proc/PID/environ` |
| Encrypted SQLite | Overkill for 2-3 credential strings |
| Automatic secret backup/sync | Risk of exfiltration; re-enter on new machine |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| SEC-01 | Phase 1 | Complete |
| SEC-02 | Phase 1 | Complete |
| STOR-01 | Phase 1 | Complete |
| STOR-02 | Phase 1 | Complete |
| STOR-03 | Phase 1 | Complete |
| STOR-04 | Phase 1 | Complete |
| STOR-05 | Phase 1 | Complete |
| DLVR-01 | Phase 2 | Complete |
| DLVR-02 | Phase 2 | Complete |
| DLVR-03 | Phase 2 | Complete |
| DLVR-04 | Phase 2 | Complete |
| DLVR-05 | Phase 2 | Complete |
| AUTH-01 | Phase 2 | Complete |
| AUTH-02 | Phase 2 | Complete |
| AUTH-03 | Phase 2 | Complete |
| AUTH-04 | Phase 2 | Complete |
| UX-01 | Phase 3 | Complete |
| UX-02 | Phase 3 | Complete |
| UX-03 | Phase 3 | Complete |
| UX-04 | Phase 3 | Complete |
| UX-05 | Phase 3 | Complete |
| TEST-01 | Phase 3 | Complete |
| TEST-02 | Phase 3 | Complete |

**Coverage:**
- v1 requirements: 23 total
- Mapped to phases: 23
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-26*
*Last updated: 2026-03-26 after initial definition*
