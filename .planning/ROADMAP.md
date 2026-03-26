# Roadmap: Mage Voyance — Secure Secret Management & Connection Loading Fix

## Overview

This roadmap delivers a complete overhaul of how Mage Voyance stores, delivers, and authenticates secrets between the Tauri host and the Python sidecar. Phase 1 builds the encrypted storage foundation (AES-256-GCM with machine-derived key) and patches the critical shell plugin CVE. Phase 2 wires up stdin-based secret delivery with startup synchronization and adds ephemeral IPC token authentication on all sidecar endpoints. Phase 3 integrates the frontend with first-run setup UI, health feedback, and end-to-end integration tests that validate the entire pipeline.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Encrypted Secret Storage & Security Foundation** - Patch shell plugin CVE, build AES-256-GCM encrypted storage with machine-derived key (completed 2026-03-26)
- [ ] **Phase 2: Secret Delivery & IPC Authentication** - Stdin-based secret delivery to sidecar with startup synchronization and ephemeral token auth on all endpoints
- [ ] **Phase 3: Frontend Integration & Validation** - First-run setup UI, silent subsequent launches, health feedback, and end-to-end integration tests

## Phase Details

### Phase 1: Encrypted Secret Storage & Security Foundation
**Goal**: Secrets can be encrypted, persisted to disk, and decrypted using a machine-derived key -- with the critical shell plugin vulnerability patched first
**Depends on**: Nothing (first phase)
**Requirements**: SEC-01, SEC-02, STOR-01, STOR-02, STOR-03, STOR-04, STOR-05
**Success Criteria** (what must be TRUE):
  1. tauri-plugin-shell is at version >= 2.2.1 and shell capabilities have `open: false`
  2. Secrets can be encrypted and saved to a secrets.bin file in the Tauri app data directory
  3. Secrets can be loaded and decrypted from secrets.bin on the same machine
  4. Attempting to decrypt secrets.bin on a different machine (or after tampering) triggers a graceful error rather than a crash
  5. Each save operation uses a fresh random nonce (re-saving the same secrets produces different ciphertext)
**Plans**: 2 plans

Plans:
- [ ] 01-01-PLAN.md — CVE patch, crypto dependencies, and crypto.rs module with TDD
- [ ] 01-02-PLAN.md — Wire crypto module into Tauri commands, remove keyring and store deps

### Phase 2: Secret Delivery & IPC Authentication
**Goal**: Decrypted secrets and an ephemeral IPC token are delivered to the Python sidecar via stdin before any service initialization, and all sidecar endpoints require valid token authentication
**Depends on**: Phase 1
**Requirements**: DLVR-01, DLVR-02, DLVR-03, DLVR-04, DLVR-05, AUTH-01, AUTH-02, AUTH-03, AUTH-04
**Success Criteria** (what must be TRUE):
  1. Python sidecar receives secrets via stdin and does not initialize Redis or Hatchet until secrets are received
  2. Sidecar emits a readiness signal on stdout after successful initialization, and Tauri waits for it with a configurable timeout
  3. If the sidecar fails to become ready within the timeout, an actionable error is surfaced (not a silent hang)
  4. Every sidecar HTTP endpoint rejects requests without a valid X-IPC-Token header with 403
  5. Secrets never appear in process arguments, environment variables, or application logs
**Plans**: TBD

Plans:
- [ ] 02-01: TBD
- [ ] 02-02: TBD

### Phase 3: Frontend Integration & Validation
**Goal**: Users experience a complete credential lifecycle -- first-run setup with validation, silent subsequent launches, live connection health feedback -- verified by end-to-end integration tests
**Depends on**: Phase 2
**Requirements**: UX-01, UX-02, UX-03, UX-04, UX-05, TEST-01, TEST-02
**Success Criteria** (what must be TRUE):
  1. On first launch (no secrets.bin), user sees a setup form for Redis URL and Hatchet token, and credentials are validated (connectivity tested) before saving
  2. On subsequent launches (secrets.bin exists), the app starts silently with no credential prompts
  3. The health endpoint reflects actual connection status after secret-based initialization, and connection failures show actionable "check credentials" guidance
  4. Integration test passes: app connects successfully when valid credentials exist
  5. Integration test passes: app shows first-run setup flow when no credentials exist
**Plans**: TBD

Plans:
- [ ] 03-01: TBD
- [ ] 03-02: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Encrypted Secret Storage & Security Foundation | 2/2 | Complete   | 2026-03-26 |
| 2. Secret Delivery & IPC Authentication | 0/TBD | Not started | - |
| 3. Frontend Integration & Validation | 0/TBD | Not started | - |
