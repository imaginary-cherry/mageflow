# Pitfalls Research

**Domain:** Desktop app packaging — Tauri v2 + Python sidecar (Nuitka) + React/Vite frontend
**Researched:** 2026-03-12
**Confidence:** MEDIUM-HIGH (most findings verified via official docs and GitHub issues; some from community reports)

---

## Critical Pitfalls

### Pitfall 1: Orphaned Sidecar Processes on App Exit

**What goes wrong:**
When the user quits the app via the OS menu (Cmd+Q, window close button, taskbar right-click) the Python sidecar process keeps running in the background. The user accumulates orphaned Python server processes across reboots, consuming ports and memory. On next launch the sidecar may fail to bind its port because the previous instance still holds it.

**Why it happens:**
Tauri's `Command.spawn()` returns a child handle, but the developer is fully responsible for calling `child.kill()`. Nothing in Tauri kills child processes automatically when the window closes. `Ctrl+C` from the terminal does propagate SIGTERM, but GUI quit events do not.

**How to avoid:**
Store the `Child` handle in Tauri `State` (Rust side). Hook `app.on_run_event` for `RunEvent::ExitRequested` and `RunEvent::Exit` and call `child.kill()` inside both handlers. Also add a guard: on startup, scan for and kill any leftover processes bound to the sidecar's port before spawning a new one. Log sidecar PID to a lockfile so even crash recovery can find it.

**Warning signs:**
- Multiple processes named `mageflow-server` or the compiled binary appear in Activity Monitor / Task Manager after repeated launches.
- Port binding errors on second launch (`Address already in use`).
- Users report high CPU/memory on idle machines.

**Phase to address:** Phase 1 — Sidecar integration scaffold. Must be handled before any real testing; otherwise every test run leaks a process.

---

### Pitfall 2: Sidecar Startup Race — Frontend Loads Before Backend Is Ready

**What goes wrong:**
The React frontend (loaded in the webview) fires API requests immediately on mount. The Python sidecar takes 0.5–3 seconds to start and begin listening. All initial API calls return connection errors, the UI enters an error state, and TanStack Query may cache those failures with backoff, degrading UX for seconds even after the sidecar is healthy.

**Why it happens:**
Tauri spawns the sidecar via `Command.spawn()` and returns immediately — there is no built-in "wait until ready" mechanism. The webview is initialized in parallel and loads the frontend fast (it is served from embedded assets). The Python process startup involves unpacking (if onefile), importing asyncio/gRPC/hatchet-sdk, and binding a socket — all of which take nontrivial time on first launch.

**How to avoid:**
Implement a health-check loop on the Rust side before emitting a "sidecar-ready" event to the frontend. Poll `GET http://127.0.0.1:<port>/health` (add a `/health` endpoint to the Python server) with a 100ms interval and a 30s timeout. Emit a Tauri event (`sidecar:ready` or `sidecar:failed`) that the React frontend listens for before issuing any API calls. Show a "connecting…" splash screen during this window. Never let the frontend issue requests without confirmation.

**Warning signs:**
- Network errors in the console on fresh app launch that resolve on reload.
- TanStack Query shows stale or error states immediately after startup.
- Flaky integration tests that pass on retry but fail on first run.

**Phase to address:** Phase 1 — Sidecar integration scaffold. The health-check pattern must be in place from the first working prototype; retrofitting it later requires changes to both Rust and frontend layers.

---

### Pitfall 3: Nuitka Cannot Cross-Compile — Requires Native Runner per Platform

**What goes wrong:**
Developers attempt to build the Windows binary on a macOS CI machine (or vice versa) using Nuitka. The build either fails outright or produces a binary that crashes at runtime. The team loses hours debugging what looks like a Nuitka configuration issue but is actually a fundamental limitation.

**Why it happens:**
Nuitka does not support cross-compilation between different OS families (macOS → Windows, Linux → macOS, etc.). It compiles Python to C and then invokes the native C compiler, which must target the host OS. This is documented as a known permanent limitation.

For macOS universal binaries (arm64 + x86_64): Intel macOS can compile for arm64 via `--macos-target-arch=arm64`, but an Apple Silicon machine cannot compile for x86_64 in the same way because Rosetta only runs x86_64 code at the OS level, not cross-compile it.

**How to avoid:**
Use a GitHub Actions matrix with a separate native runner for each platform:
- `macos-latest` (Apple Silicon) for `aarch64-apple-darwin`
- `macos-13` (Intel) for `x86_64-apple-darwin`
- `windows-latest` for `x86_64-pc-windows-msvc`
- `ubuntu-22.04` for `x86_64-unknown-linux-gnu`

Build the Nuitka binary on each runner, then collect all four artifacts for Tauri's `beforeBuildCommand` or as pre-placed binaries in `src-tauri/binaries/`. Use the Nuitka-Action GitHub Action for the compilation step.

**Warning signs:**
- Any CI workflow that runs Nuitka from a single OS and ships binaries for multiple OSes.
- A "matrix: false" in CI config for the Nuitka build step while Tauri matrix is present.

**Phase to address:** Phase 2 — CI/CD pipeline. The per-platform build matrix must be established before any release candidate.

---

### Pitfall 4: Nuitka Standalone Binary Missing Modules at Runtime (Hidden Imports)

**What goes wrong:**
The Nuitka build completes without errors, but at runtime the binary crashes with `ModuleNotFoundError` or silent import failures. The most likely offenders for this project: `grpc` (hatchet-sdk uses gRPC), `protobuf` generated `_pb2` files, `asyncio` standard library submodules, and any modules loaded via `importlib.import_module()` with dynamic strings.

**Why it happens:**
Nuitka traces static imports during compilation. Dynamic imports (`importlib.import_module(name)` where `name` is computed at runtime, `exec()` on string code, `__import__` with dynamic arguments) are invisible to the tracer. gRPC and protobuf rely heavily on dynamic module loading. Additionally, `asyncio` is no longer automatically included in all Nuitka versions.

**How to avoid:**
- Use `--standalone` mode (not `--onefile`) for the sidecar; the dist folder is easier to debug.
- Add explicit `--include-package=grpc --include-package=google.protobuf` flags.
- Avoid `_pb2` protobuf file compilation — Nuitka 2.7+ has a flag to skip those; use `--nofollow-import-to=*_pb2` or rely on the built-in protobuf config in Nuitka's YAML plugin config.
- Include all hatchet-sdk package data: `--include-package-data=hatchet_sdk`.
- Run the binary through a smoke test (e.g., `./server --help` and then start + connect) as part of CI before packaging into Tauri.
- Pin Nuitka version in CI; never use `latest`.

**Warning signs:**
- Binary starts fine on the build machine but crashes on a clean machine or Docker container.
- `ImportError` or `AttributeError` in log output referencing gRPC or protobuf modules.
- `FileNotFoundError` referencing package metadata (`METADATA`, `VERSION` files).

**Phase to address:** Phase 1 — Python sidecar compilation. Must be validated on a clean VM before Phase 2 begins.

---

### Pitfall 5: Sidecar Binary Target Triple Naming Error

**What goes wrong:**
Tauri cannot find the sidecar at runtime with error: "sidecar not found" or "binary not found." The binary exists in `src-tauri/binaries/` but has the wrong filename. Alternatively, the `Command.sidecar()` call in JavaScript uses the full path instead of just the base name, causing silent failure.

**Why it happens:**
Tauri requires every sidecar binary to be named `<base-name>-<target-triple>` exactly (e.g., `mageflow-server-aarch64-apple-darwin`). The `externalBin` config entry is the base path, and Tauri appends the running platform's target triple at runtime. Developers frequently place the binary without the suffix, or rename it inconsistently across platforms.

Additionally, `Command.sidecar("binaries/mageflow-server")` fails — the argument must match only the filename portion declared in `externalBin`, not the path prefix.

**How to avoid:**
- In CI, rename each compiled binary with the correct target triple immediately after Nuitka builds it: `mv mageflow-server mageflow-server-$(rustc --print host-tuple)`.
- Automate the rename step — never do it manually. Use the script shown in Tauri's docs.
- In JS/Rust: call `Command.sidecar("mageflow-server")` (not the full path).
- Verify with `tauri info` and a local test before committing CI changes.

**Warning signs:**
- Any "binary not found" or "spawn error: No such file or directory" at runtime.
- Inconsistent naming across platform artifacts in release assets.

**Phase to address:** Phase 1 — Tauri scaffold. Establish the naming convention and automation script on day one.

---

### Pitfall 6: Missing Tauri Capabilities/Permissions for Shell Spawn

**What goes wrong:**
The app builds, installs, and launches successfully in dev mode, but after a production build the sidecar silently fails to spawn. No error appears in the webview; the app just hangs on the connecting screen. The issue is that Tauri v2's capabilities system blocks shell execution by default, and the production build enforces capabilities strictly.

**Why it happens:**
Tauri v2 introduced a fine-grained permissions system. All potentially dangerous plugin commands — including `shell:allow-spawn` and `shell:allow-execute` — are blocked unless explicitly granted in `src-tauri/capabilities/default.json`. In development with `tauri dev` the behavior may differ from a release build because of default capability overrides.

**How to avoid:**
Add the required permissions to `capabilities/default.json` explicitly:
```json
{
  "permissions": [
    "shell:allow-spawn",
    "shell:allow-execute",
    { "identifier": "shell:allow-execute", "allow": [{ "name": "mageflow-server", "sidecar": true }] }
  ]
}
```
Also scope arguments: only allow the specific flags the sidecar accepts; do not use `"args": true` in production (allows arbitrary argument injection).

**Warning signs:**
- Sidecar spawns fine in `tauri dev` but not in a packaged `.app`/`.exe`.
- No error thrown — just the sidecar never starts.
- Tauri console shows capability-related denials when devtools are enabled.

**Phase to address:** Phase 1 — Tauri scaffold. Include capability config as part of the initial integration checklist, not as a debug step.

---

### Pitfall 7: Tauri Updater Private Key Loss = Permanent Update Blackout

**What goes wrong:**
The auto-updater is shipped in v1.0. The updater signing keypair is generated once, the private key is stored in a CI secret. Six months later the CI environment is rotated or the secret is lost. All existing installed copies of the app can no longer receive updates — they will check for updates, verify signatures, fail validation, and refuse to install. Users are permanently stranded unless they manually uninstall and reinstall.

**Why it happens:**
Tauri's updater uses an asymmetric signing scheme. The public key is baked into the shipped binary. Update payloads must be signed by the matching private key. There is no key rotation mechanism for already-distributed apps. Losing the private key is final.

**How to avoid:**
- Generate the keypair once with `tauri signer generate` and store the private key in at least two independent secrets stores (e.g., GitHub Actions secret + a password manager like Bitwarden or 1Password team vault).
- Document key storage location in an internal runbook, not just CI config.
- Test the full update flow (sign → publish → app receives + applies) before shipping v1.0.
- Never commit the private key to git. The public key in `tauri.conf.json` is safe to commit.

**Warning signs:**
- Updater private key only exists in one CI environment variable.
- No runbook entry for "what to do if CI is reset."
- Key was generated by a single developer without team backup.

**Phase to address:** Phase 3 — Distribution and auto-updater. Address explicitly in the phase checklist, before any release.

---

### Pitfall 8: macOS Notarization Fails for Sidecar Binaries (Nested Code Signature)

**What goes wrong:**
Tauri builds and code-signs the main `.app` bundle, but Apple's notarization service rejects the submission with: "The signature of the binary is invalid" or "nested code is modified or invalid." The sidecar binary inside the bundle is either unsigned or was signed with a certificate set to "Always Trust" in the system keychain, causing a keychain conflict during notarization.

**Why it happens:**
Apple's notarization requires every executable within an `.app` bundle to be individually signed with a valid Developer ID Application certificate, with the `--timestamp` flag and `--options runtime`. Tauri signs its own Rust binary but does NOT sign sidecar binaries — that is the developer's responsibility. A known additional failure mode: having the Developer ID certificate set to "Always Trust" in the macOS Keychain causes the codesign tool to use an incorrect keychain during signing, producing invalid signatures.

**How to avoid:**
- Sign the Nuitka binary explicitly before it is placed in `src-tauri/binaries/`:
  ```bash
  codesign -f --timestamp --sign "Developer ID Application: ..." \
    --options runtime \
    --keychain "$HOME/Library/Keychains/login.keychain-db" \
    mageflow-server-aarch64-apple-darwin
  ```
- In CI (where there is no interactive keychain), import the certificate into a temporary keychain and reference it explicitly.
- Never set the Developer ID certificate to "Always Trust" in the system keychain on CI.
- Verify signing before notarization: `codesign --verify --verbose mageflow-server-aarch64-apple-darwin`.

**Warning signs:**
- Notarization succeeds locally but fails in CI.
- `spctl --assess` reports "rejected" on the sidecar binary.
- Apple notarization log contains "nested code is modified or invalid."

**Phase to address:** Phase 2 — CI/CD pipeline and Phase 3 — Distribution. The signing script must be part of the build pipeline, not a manual step.

---

### Pitfall 9: Nuitka Onefile Mode Triggers Windows Defender False Positives

**What goes wrong:**
The Windows build of the Python sidecar compiled with `--onefile` is flagged as `Trojan:Win32/Wacatac.B!ml` or similar by Windows Defender on end-user machines. Users see a security warning, the binary is quarantined, and the app fails silently.

**Why it happens:**
Nuitka's `--onefile` mode creates a self-extracting executable that unpacks itself to a temporary directory, executes, then cleans up. This behavior (write-to-temp, execute from temp, delete) matches common malware patterns and triggers Windows Defender's heuristic detection. This is a documented ongoing issue with no definitive fix in the compiler itself.

**How to avoid:**
Use `--standalone` mode (directory output) instead of `--onefile`. The directory output does not trigger self-extraction heuristics. Tauri bundles the entire `dist/` directory as an `externalBin` resource (point `externalBin` at the main executable; Tauri copies the dist folder). Obtain an EV (Extended Validation) code signing certificate for the Windows binary — EV-signed binaries bypass SmartScreen and reduce Defender false positives significantly. For MVP, submit the binary to Microsoft's malware sample submission portal to build reputation.

**Warning signs:**
- VirusTotal shows detections even for a freshly compiled "Hello World" with `--onefile`.
- Windows test machines quarantine the sidecar on first launch.
- User reports of "Windows blocked this app" dialogs.

**Phase to address:** Phase 2 — CI/CD pipeline. The decision between `--onefile` and `--standalone` must be made before the Windows build is finalized.

---

### Pitfall 10: CSP Blocks Frontend Fetch to Localhost Sidecar

**What goes wrong:**
The React frontend calls `fetch("http://127.0.0.1:8000/api/...")` to communicate with the Python sidecar. In production Tauri builds (especially on Windows and Linux), the webview's Content Security Policy blocks this request with a CSP violation. The app appears to hang or returns empty data.

**Why it happens:**
Tauri v2 injects a strict CSP into all HTML pages by default. The `connect-src` directive does not include `http://127.0.0.1` unless explicitly configured. On Windows the webview (WebView2) is particularly strict about mixed HTTP/HTTPS contexts — Tauri serves the app over `https://tauri.localhost`, and `http://127.0.0.1` is treated as a different origin.

**How to avoid:**
In `tauri.conf.json`, set the CSP to explicitly allow the sidecar origin:
```json
{
  "app": {
    "security": {
      "csp": "default-src 'self'; connect-src 'self' http://127.0.0.1:8000; img-src 'self' data:; style-src 'self' 'unsafe-inline'"
    }
  }
}
```
Alternatively, use Tauri's IPC bridge (Rust commands) as a proxy to the sidecar instead of direct HTTP from the frontend — this is more secure and avoids CSP issues entirely. For this project, given the existing frontend already calls the Python backend directly, the CSP approach is simpler for brownfield integration.

**Warning signs:**
- `fetch()` calls succeed in `tauri dev` but fail in production build.
- Browser console shows CSP violation errors referencing `connect-src`.
- Network tab shows requests blocked without a response.

**Phase to address:** Phase 1 — Tauri scaffold and frontend integration.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Use `"args": true` in shell capability (allow any args) | Saves time on capability config | Arbitrary argument injection from compromised frontend | Never in production |
| Skip health-check loop, use `setTimeout(2000)` delay | Fast to implement | Race conditions on slow machines, flaky tests, bad UX | Never; use a real health check |
| Store updater private key only in GitHub Actions secret | Simple setup | Permanent update blackout if CI is rotated | Never; always have backup |
| Use `--onefile` for Nuitka on Windows for simplicity | Single file to ship | Windows Defender false positives for end users | Only for internal tools, never for distribution |
| Sign sidecar manually on developer machine before commit | No CI signing setup needed | Build is not reproducible; fails on any other machine | Prototype only, never for release |
| Skip Nuitka smoke test in CI | Faster CI runs | Broken sidecar ships silently; only caught post-release | Never |
| Use `process.kill()` on PyInstaller/Nuitka onefile PID | Simple cleanup code | Kills only the bootstrap loader, not the actual Python process | Never for onefile; use named pipes or shutdown endpoints |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Tauri sidecar naming | Place binary as `mageflow-server` in `src-tauri/binaries/` | Must be `mageflow-server-<target-triple>` (e.g., `mageflow-server-aarch64-apple-darwin`) |
| Tauri `Command.sidecar()` | Call with full path: `sidecar("binaries/mageflow-server")` | Call with base name only: `sidecar("mageflow-server")` |
| gRPC + Nuitka | Build succeeds but runtime fails; assume it "just works" | Explicitly include `--include-package=grpc` and `--include-package=google.protobuf`; run smoke test on clean VM |
| Tauri updater key | Generate key, put in CI, forget about it | Store key in password manager + CI secret; document in runbook |
| macOS notarization | Rely on Tauri to sign the sidecar binary | Manually sign the Nuitka binary before placing in `src-tauri/binaries/`; specify login keychain explicitly |
| CSP + sidecar HTTP | Default Tauri CSP blocks localhost fetch | Add `connect-src http://127.0.0.1:<port>` to CSP config |
| Sidecar shutdown | Ignore cleanup; rely on OS to clean up child processes | Hook `RunEvent::Exit` and `RunEvent::ExitRequested` in Rust; call `child.kill()` explicitly |
| Nuitka + asyncio | Assume standard library is always included | Verify asyncio is present in compiled output; add `--include-module=asyncio` if missing |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Nuitka `--onefile` startup latency on Windows | App appears frozen for 2-5s on first launch while binary self-extracts to temp dir | Use `--standalone` (directory) mode; extraction overhead does not apply | Every cold launch on Windows |
| Sidecar port discovery at runtime | Port conflicts on multi-instance launch; fragile hardcoded port | Pick a fixed default port with fallback; write chosen port to a temp file so Rust and frontend agree | When user runs two instances or another app claims the port |
| Nuitka compilation time in CI | 10-20 minute CI runs; developers skip the CI step locally | Cache the Nuitka output directory keyed on requirements hash; use Nuitka-Action's built-in caching | Every uncached CI run |
| Large Nuitka binary size from unused imports | Binary > 200MB due to transitive dependencies of hatchet-sdk | Use `--noinclude-pytest-mode=nofollow` and anti-bloat plugin; audit with `--show-modules` | At packaging time; users see oversized downloads |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Bind Python sidecar to `0.0.0.0` instead of `127.0.0.1` | Exposes internal API to the local network; other machines can connect to user's workflow data | Always bind to `127.0.0.1`; assert this in server startup code |
| Pass Hatchet/Redis credentials as CLI args to sidecar | Credentials visible in process list (`ps aux`) | Pass credentials via environment variables or a temp config file readable only by the current user; use Tauri's `env` option in `Command::new_sidecar()` |
| Use `"args": true` in Tauri shell capability | Any compromised frontend JS can pass arbitrary args to the sidecar binary | Enumerate allowed argument patterns explicitly in capability config |
| Expose sidecar's full API surface via Tauri IPC without validation | Frontend can trigger arbitrary sidecar actions | If proxying through Rust, validate and whitelist commands; the sidecar should also authenticate requests |
| Ship updater private key in source code or `.env` files | Key compromise means attacker can ship malicious updates | Use CI secrets only; never commit; rotate immediately if leaked |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| No splash/loading screen during sidecar startup | Users see blank or broken UI for 1-3 seconds, assume the app is broken | Show a "Connecting to Mageflow backend…" splash; emit `sidecar:ready` event to dismiss it |
| Silent sidecar crash — app shows "no data" with no explanation | Users assume their Hatchet/Redis config is wrong and waste time debugging | Capture sidecar stderr; surface error messages in a visible status indicator in the UI |
| Auto-updater applies update without user confirmation | Background restarts surprise users during active monitoring sessions | Show update notification with "Restart to update" action; never auto-restart without acknowledgment |
| App works on developer machine (arm64 Mac) but ships wrong binary for Intel Mac users | Intel Mac users cannot launch the app; silent failure | Always test both macOS architectures in CI with separate runners |
| Windows SmartScreen "Unknown publisher" warning on first install | Users cancel installation thinking it is malware | Obtain EV code signing; plan for SmartScreen reputation building period in release timeline |

---

## "Looks Done But Isn't" Checklist

- [ ] **Sidecar lifecycle:** Sidecar binary spawns and serves requests — but verify it is also killed on app exit via cmd+Q, window close, and crash. Check Activity Monitor after closing.
- [ ] **Sidecar naming:** Binary placed in `src-tauri/binaries/` — but verify the filename has the correct `--target-triple` suffix for ALL target platforms, not just the dev machine.
- [ ] **Nuitka completeness:** Binary runs on the build machine — but verify it runs on a *clean machine* with no Python or dev tools installed. Use Docker or a fresh VM.
- [ ] **gRPC runtime:** Import-time smoke test passes — but verify actual gRPC calls work (connect, subscribe, receive data). Dynamic protobuf loading is a separate failure point from import-time failures.
- [ ] **macOS notarization:** Tauri signs the `.app` — but verify the *sidecar binary inside* is also individually signed with `--timestamp --options runtime`. Run `codesign --verify --verbose` on the sidecar path inside the bundle.
- [ ] **CSP in production:** `fetch()` works in `tauri dev` — but verify it works in a production build (`tauri build` + install the `.dmg`/`.exe`). CSP is only enforced strictly in production.
- [ ] **Updater key backup:** Updater key is in CI secret — but verify it is also stored in the team password manager with documented recovery steps.
- [ ] **Windows Defender:** Binary compiles cleanly — but verify a fresh Windows 11 machine (no exclusions) can launch the app without a quarantine dialog.
- [ ] **Health-check race:** App launches successfully in 1-second test — but verify behavior when the machine is under load (VM with limited CPU) and the sidecar takes 5+ seconds to start.

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Orphaned sidecar processes | LOW | Ship a patch that adds `RunEvent::Exit` handler; users restart the app |
| Startup race condition (no health check) | MEDIUM | Add health-check loop and `sidecar:ready` event in Rust; update frontend to listen before fetching |
| Nuitka missing modules | MEDIUM | Add `--include-package` flags and rebuild; requires new release for each fix; test on clean VM before release |
| Lost updater private key | HIGH (irreversible) | Cannot fix for existing installs. Options: (1) ship a forced-migration update via a separate channel before the key is lost; (2) if already lost, users must manually reinstall. Prevention is the only real mitigation |
| macOS notarization failure | MEDIUM | Fix signing script, re-notarize, re-release; no impact on already-installed users but delays the release |
| Windows Defender false positive | MEDIUM | Switch from `--onefile` to `--standalone`; obtain EV certificate; submit to Microsoft; ship new release |
| Wrong sidecar target triple | LOW | Rename binary correctly in CI; rebuild; no data loss |
| CSP blocking frontend fetch | LOW | Update `tauri.conf.json` CSP; rebuild; ship patch release |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Orphaned sidecar processes | Phase 1: Sidecar integration | `tauri build`, install app, quit via Cmd+Q, check Activity Monitor for lingering process |
| Startup race (no health check) | Phase 1: Sidecar integration | Simulate slow startup (add `time.sleep(3)` to Python server init); verify UI shows loading state not error |
| Nuitka cannot cross-compile | Phase 2: CI/CD pipeline | Verify GitHub Actions matrix has separate runners for macOS arm64, macOS x86_64, Windows, Linux |
| Nuitka missing modules at runtime | Phase 1: Python sidecar compilation | Run compiled binary on Docker `python:3.11-slim` (no dev tools); verify gRPC connect succeeds |
| Sidecar binary naming | Phase 1: Tauri scaffold | `tauri build` with `TAURI_SKIP_SIDECAR_SIGNATURE_CHECK=1` on each platform; verify binary found |
| Missing Tauri capabilities | Phase 1: Tauri scaffold | Perform a full `tauri build` (not `tauri dev`); verify sidecar spawns in packaged app |
| Updater private key loss | Phase 3: Distribution | Document key location in runbook; verify second team member can access backup |
| macOS notarization failure | Phase 2-3: CI/CD + Distribution | Run full CI pipeline on a tagged release and verify Apple notarization ticket is stapled |
| Nuitka onefile Windows Defender | Phase 2: CI/CD pipeline | Install compiled `.exe` on fresh Windows 11 VM with default Defender; verify no quarantine |
| CSP blocks localhost fetch | Phase 1: Tauri scaffold | In production build, open devtools and check Console for CSP violations on all API routes |

---

## Sources

- [Tauri v2 — Embedding External Binaries (Sidecar)](https://v2.tauri.app/develop/sidecar/) — HIGH confidence (official docs)
- [Tauri v2 — Capabilities](https://v2.tauri.app/security/capabilities/) — HIGH confidence (official docs)
- [Tauri v2 — Content Security Policy](https://v2.tauri.app/security/csp/) — HIGH confidence (official docs)
- [Tauri v2 — Updater Plugin](https://v2.tauri.app/plugin/updater/) — HIGH confidence (official docs)
- [Tauri v2 — macOS Code Signing](https://v2.tauri.app/distribute/sign/macos/) — HIGH confidence (official docs)
- [Nuitka — Common Issue Solutions](https://nuitka.net/user-documentation/common-issue-solutions.html) — HIGH confidence (official docs)
- [Nuitka — macOS Cross-Compilation](https://nuitka.net/info/macos-cross-compile.html) — HIGH confidence (official docs)
- [Nuitka-Action GitHub Action](https://github.com/Nuitka/Nuitka-Action) — HIGH confidence (official repo)
- [GitHub issue: macOS codesigning/notarization failure with ExternalBin](https://github.com/tauri-apps/tauri/issues/11992) — MEDIUM confidence (community report, workaround verified)
- [GitHub discussion: Kill process on exit](https://github.com/tauri-apps/tauri/discussions/3273) — MEDIUM confidence (community, widely referenced)
- [GitHub issue: Sidecar not killed via GUI quit](https://github.com/tauri-apps/tauri/issues/8139) — MEDIUM confidence (community report)
- [GitHub issue: Feature — Sidecar Lifecycle Management Plugin](https://github.com/tauri-apps/plugins-workspace/issues/3062) — MEDIUM confidence (official plugin proposal, confirms gaps)
- [GitHub issue: Windows Defender flags Nuitka onefile](https://github.com/Nuitka/Nuitka/issues/2685) — MEDIUM confidence (community, multiple confirmations)
- [GitHub issue: Nuitka gRPC async generator bug](https://github.com/Nuitka/Nuitka/issues/3608) — MEDIUM confidence (community report, version-specific)
- [GitHub issue: Nuitka protobuf segfault](https://github.com/Nuitka/Nuitka/issues/3442) — MEDIUM confidence (community report)
- [Tauri discussion: HTTP request to sidecar server](https://github.com/tauri-apps/tauri/discussions/5391) — MEDIUM confidence (community)
- [DEV: Tauri v2 app with Python server sidecar example](https://github.com/dieharders/example-tauri-v2-python-server-sidecar) — MEDIUM confidence (community example project)
- [Security advisory: Updater private key leak via Vite env vars](https://github.com/tauri-apps/tauri/security/advisories/GHSA-2rcp-jvr4-r259) — HIGH confidence (official security advisory)

---
*Pitfalls research for: Tauri v2 + Python sidecar (Nuitka) desktop app packaging*
*Researched: 2026-03-12*
