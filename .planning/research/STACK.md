# Stack Research

**Domain:** Cross-platform desktop app — Tauri v2 shell + Python sidecar + React/Vite frontend
**Researched:** 2026-03-12
**Confidence:** MEDIUM-HIGH (Tauri v2 APIs verified against official docs; Nuitka universal binary limitation found in official docs; versions confirmed on PyPI and crates.io)

---

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Tauri v2 | 2.10.3 (Mar 2025) | Desktop shell: system webview, sidecar management, updater, cross-platform packaging | v2 is stable since Oct 2024. Provides first-class sidecar API, built-in signed updater, and generates macOS .dmg, Windows .msi/.exe, and Linux .deb/.AppImage from one codebase. Bundle sizes are 5-20x smaller than Electron because it uses the OS webview instead of bundling Chromium. |
| Nuitka | 4.0.4 (Mar 2026) | Compiles the Python backend server to a native binary (the sidecar executable) | Produces a C-compiled binary with faster startup than PyInstaller's frozen bytecode approach. The `--mode=standalone` output is a self-contained directory; `--mode=onefile` wraps it into a single file Tauri can ship as an `externalBin`. Python 3.4–3.13 supported. v4.x has explicit FastAPI standalone dependency support built in. |
| React 18 + Vite | React 18.x / Vite 5.x | Frontend UI (already exists) | Already in use. Vite's static build output (`dist/`) is exactly what Tauri's `frontendDist` config points at. No changes required. |
| Rust (stable) | ≥1.77.2 | Tauri's runtime requirement | Required by all Tauri plugins. Pin to stable channel; nightly is not needed. |

### Supporting Libraries (Tauri Plugins)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `tauri-plugin-shell` (Rust) / `@tauri-apps/plugin-shell` (JS) | 2.3.4 | Spawn and manage the Nuitka sidecar process; communicate with it via stdio or HTTP | Required. This is the only official Tauri v2 API for launching external binaries as sidecars. Grants `shell:allow-execute` permission scoped to the sidecar binary name. |
| `tauri-plugin-updater` (Rust) / `@tauri-apps/plugin-updater` (JS) | 2.10.0 | In-app auto-update: checks endpoint, downloads, verifies signature, installs | Required for the built-in updater. Signing is mandatory — Tauri will reject unsigned updates. Generate keys with `npm run tauri signer generate`. |
| `tauri-action` (GitHub Action) | v0 (latest) | Multi-platform CI builds: creates platform artifacts, attaches to GitHub Release, generates `latest.json` for the updater | Use in GitHub Actions CI. Handles the matrix build across `macos-latest` (aarch64 + x86_64), `ubuntu-22.04`, and `windows-latest`. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| `rustup` (stable toolchain) | Rust compiler for Tauri's native layer | Run `rustup target add aarch64-apple-darwin x86_64-apple-darwin` on the macOS runner to support both Apple Silicon and Intel builds. |
| Nuitka's `--mode=standalone` | Test phase for sidecar compilation | Always compile standalone first, verify it runs, then switch to `--mode=onefile`. Debugging missing imports is much easier in standalone mode (they show up as missing files in the output directory). |
| `orderly-nuitka` / `nuitka-action` (GitHub Action) | Automate Nuitka compilation in CI | Community action that handles Nuitka installation and dependency resolution per platform. Alternative: run `python -m nuitka` directly in CI steps. |
| Apple Developer ID certificate | macOS code signing + notarization | Required for Homebrew cask distribution and to avoid Gatekeeper blocking the app. Import into the macOS runner's Keychain in CI. Notarization takes 2–5 min via Apple's service. |
| `minisign` / Tauri's built-in signer | Sign updater artifacts | Tauri's updater requires minisign-format signatures. The private key must be in `TAURI_SIGNING_PRIVATE_KEY` env var at build time. Do not lose the private key — existing installs will be unable to receive updates. |

---

## Installation

```bash
# 1. Bootstrap Tauri v2 into the existing repo (run from repo root)
cargo install tauri-cli --version "^2"
npm run tauri init   # or: npx tauri init

# 2. Add the shell plugin (for sidecar)
cd src-tauri
cargo add tauri-plugin-shell

# 3. Add the updater plugin
cargo add tauri-plugin-updater --target 'cfg(any(target_os = "macos", windows, target_os = "linux"))'

# 4. JS bindings
npm install @tauri-apps/plugin-shell @tauri-apps/plugin-updater

# 5. Nuitka (Python side, in the Python project's virtualenv)
pip install nuitka==4.0.4

# 6. Generate updater signing keypair (run once, store private key securely)
npm run tauri signer generate -- -w ~/.tauri/mage-voyence.key
```

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| Nuitka `--mode=onefile` | PyInstaller onefile | PyInstaller is more documented and has broader community examples. Use it if Nuitka fails to compile a specific dependency (e.g., unusual C extensions). PyInstaller's boot time is noticeably slower due to temp-dir extraction. |
| Nuitka `--mode=onefile` | Nuitka `--mode=standalone` (shipped as a directory) | Use standalone (directory) if onefile extraction latency is unacceptable at startup, or if Tauri's `externalBin` layout is easier to manage as a directory. Tauri supports bundling a directory of files under `externalBin`. |
| GitHub Releases + `tauri-action` | CrabNebula Cloud / Nucleus updater service | Use a hosted service if you want a fully managed update server without serving a static `latest.json`. Adds cost but removes infrastructure maintenance. |
| Tauri v2 | Electron | Use Electron if you need Node.js APIs inside the shell, need to target older Windows versions (<10), or if your team has no Rust experience at all. Electron bundles are 100–200 MB vs Tauri's 3–10 MB. |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| PyInstaller as the sidecar compiler | Significantly slower startup (extract-to-temp on every launch), larger binary, no compile-time optimization | Nuitka — compiles to C, faster startup, smaller standalone output |
| Tauri v1 | v1 is in maintenance mode; v2 is stable since Oct 2024 with a redesigned plugin system, mobile support, and the new capabilities/permissions model | Tauri v2 (2.10.x) |
| Nuitka `--mode=accelerated` (default, no `--mode` flag) | Accelerated mode requires Python to be installed on the user's machine. It is NOT portable. | `--mode=standalone` or `--mode=onefile` |
| Hardcoding the sidecar port in the frontend | If the port is in use, the app silently fails. Python sidecar must pick a random free port and communicate it to Tauri/frontend via stdout or a temp file. | Sidecar writes chosen port to stdout on startup; Tauri reads it via `child.stdout.on('data', ...)` before opening the webview. |
| Nuitka universal binary on macOS | As of early 2026, Nuitka does not produce true universal (fat) macOS binaries in a single pass. The feature is on the roadmap but unimplemented. | Compile two separate binaries per architecture in CI (one `macos-latest` runner with `--target aarch64`, one with `--target x86_64`) and ship both — Tauri's `externalBin` naming convention (`my-sidecar-aarch64-apple-darwin` vs `my-sidecar-x86_64-apple-darwin`) handles this automatically. |
| Committing the Tauri signing private key | Loss or exposure of the private key means existing installs can never receive updates | Store in a GitHub Actions secret (`TAURI_SIGNING_PRIVATE_KEY`), never in the repo |

---

## Stack Patterns by Variant

**If the sidecar needs to serve HTTP (FastAPI/uvicorn):**
- Use `--include-package=uvicorn --include-package=fastapi --include-package=anyio` flags with Nuitka to force inclusion of dynamically-loaded ASGI components
- Test the standalone directory first: run the compiled binary and hit the API endpoint to verify all routes work before switching to onefile

**If you need macOS Apple Silicon + Intel support:**
- Run two separate Nuitka compilations: one on an `aarch64-apple-darwin` runner, one on `x86_64-apple-darwin`
- Name outputs `my-sidecar-aarch64-apple-darwin` and `my-sidecar-x86_64-apple-darwin`
- Tauri's `externalBin` entry `"binaries/my-sidecar"` automatically selects the right one at bundle time

**If distributing via Homebrew cask:**
- Build a universal macOS `.dmg` using the separate-architecture approach above (Tauri's macOS build generates the DMG)
- Create a `homebrew-<tap-name>` GitHub repo with a cask formula pointing to the GitHub Release DMG URL
- Automate SHA256 hash updates in the formula via a GitHub Actions step in the release workflow

**If distributing via Chocolatey (Windows):**
- Tauri generates a `.msi` installer automatically via `tauri build`
- Create a Chocolatey package that wraps the MSI; publish to the Chocolatey community feed or self-host

**If distributing via apt/snap (Linux):**
- Tauri generates `.deb` (for Debian/Ubuntu) and AppImage out of the box
- For snap, use Snapcraft with the AppImage as the base or build a snap-specific step

---

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| `tauri` 2.10.x | `tauri-plugin-shell` 2.3.x | Both in the `v2` release train; keep plugin versions aligned with the core Tauri version |
| `tauri` 2.10.x | `tauri-plugin-updater` 2.10.x | Version numbers track together in the plugins-workspace monorepo |
| Nuitka 4.0.x | Python 3.4–3.13 | Use the same Python version in CI that the app's dependencies were installed with; mixing versions causes import failures |
| Rust stable ≥1.77.2 | All Tauri v2 plugins | Tauri v2 plugins enforce this minimum; older Rust versions will fail to compile |
| `tauri-action` v0 | Ubuntu 22.04 runner | Ubuntu 22.04 is the minimum Linux runner; Ubuntu 24.04 support was added but 22.04 is safer for `libwebkit2gtk-4.1-dev` compatibility |

---

## Sources

- [Tauri v2 Sidecar Docs](https://v2.tauri.app/develop/sidecar/) — Verified `externalBin` config, target-triple naming convention, `shell:allow-execute` permission setup (HIGH confidence)
- [Tauri v2 Updater Plugin Docs](https://v2.tauri.app/plugin/updater/) — Verified plugin setup, signing key requirements, endpoint config format (HIGH confidence)
- [Tauri v2 GitHub Actions Pipeline Docs](https://v2.tauri.app/distribute/pipelines/github/) — Verified multi-platform matrix build, Ubuntu dependency list, macOS universal target setup (HIGH confidence)
- [Nuitka PyPI page](https://pypi.org/project/Nuitka/) — Confirmed latest version 4.0.4, released March 10, 2026 (HIGH confidence)
- [Nuitka User Manual](https://nuitka.net/user-documentation/user-manual.html) — Verified `--mode=standalone`, `--mode=onefile`, `--mode=app` flags; Python 3.4–3.13 support (HIGH confidence)
- [Nuitka macOS cross-compilation page](https://nuitka.net/info/macos-cross-compile.html) — Confirmed that universal (fat) binary is NOT supported in a single pass as of current release (HIGH confidence — critical limitation)
- [tauri-apps/tauri GitHub releases](https://github.com/tauri-apps/tauri/releases) — Confirmed Tauri v2.10.3 as latest release (HIGH confidence)
- [@tauri-apps/plugin-shell npm](https://www.npmjs.com/package/@tauri-apps/plugin-shell) — Version 2.3.4, released 2026-01-08 (HIGH confidence)
- [Shipping a production macOS Tauri 2.0 app — DEV Community](https://dev.to/0xmassi/shipping-a-production-macos-app-with-tauri-20-code-signing-notarization-and-homebrew-mc3) — Homebrew cask pattern, signing workflow (MEDIUM confidence — community article, not official docs)
- [Tauri v2 example with Python sidecar (v2)](https://github.com/dieharders/example-tauri-v2-python-server-sidecar) — Real-world FastAPI + Tauri v2 sidecar pattern (MEDIUM confidence — community project)
- [Nuitka FastAPI packaging](https://blog.thoughtparameters.com/post/nuitka_packaging_for_web_frameworks/) — FastAPI/uvicorn Nuitka compilation gotchas (MEDIUM confidence — community article)

---

*Stack research for: Mageflow Viewer — Tauri v2 + Nuitka Python sidecar + React/Vite desktop packaging*
*Researched: 2026-03-12*
