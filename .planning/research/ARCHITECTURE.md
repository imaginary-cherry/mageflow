# Architecture Research

**Domain:** Tauri v2 desktop app with Python sidecar (brownfield: existing React/Vite frontend + FastAPI backend)
**Researched:** 2026-03-12
**Confidence:** HIGH (Tauri v2 official docs + real-world examples + direct codebase inspection)

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    Desktop App (Tauri v2)                        │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              System WebView (OS-native)                   │   │
│  │                                                           │   │
│  │   React 18 + Vite + xyflow + TanStack Query               │   │
│  │   (served from src-tauri/frontend-dist/ at startup)       │   │
│  │                                                           │   │
│  │   HttpTaskClient → fetch("http://localhost:{port}/api/…") │   │
│  └──────────────────────────┬────────────────────────────────┘  │
│                             │ HTTP (localhost only)               │
│  ┌──────────────────────────▼────────────────────────────────┐  │
│  │              Rust Core (src-tauri/src/)                    │  │
│  │                                                            │  │
│  │  • Spawns Python sidecar on startup                       │  │
│  │  • Allocates free port, passes as CLI arg                 │  │
│  │  • Emits "backend-ready" event after /api/health passes   │  │
│  │  • Kills sidecar on window close                          │  │
│  │  • Tauri commands: get_backend_port                       │  │
│  └──────────────────────────┬────────────────────────────────┘  │
│                             │ spawn() + kill() (OS process)       │
│  ┌──────────────────────────▼────────────────────────────────┐  │
│  │         Python Sidecar (Nuitka-compiled binary)            │  │
│  │                                                            │  │
│  │  FastAPI + Uvicorn + Rapyer                               │  │
│  │  GET  /api/health                                         │  │
│  │  GET  /api/workflows/roots                                │  │
│  │  POST /api/tasks/batch                                    │  │
│  │  GET  /api/workflows/{id}/children                        │  │
│  │  GET  /api/workflows/{id}/callbacks                       │  │
│  │  POST /api/tasks/{id}/cancel|pause|retry                  │  │
│  └──────────────────────────┬────────────────────────────────┘  │
│                             │ redis.asyncio (TCP)                  │
└─────────────────────────────┼───────────────────────────────────┘
                              │
              ┌───────────────▼────────────────┐
              │   External: User's Redis        │
              │   (Hatchet populates state)      │
              └────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Communicates With |
|-----------|----------------|-------------------|
| React Webview | Render workflow graph, handle user interactions | Rust core (Tauri IPC for port), Python sidecar (HTTP) |
| Rust Core (`main.rs`) | App lifecycle, sidecar spawn/kill, port allocation, readiness gating | OS (process management), WebView (Tauri events/commands) |
| Python Sidecar (FastAPI) | Query Redis via Rapyer, serve REST API, expose task state | Redis (external), Rust core (receives port arg, receives kill signal) |
| Nuitka Build Pipeline | Compile Python sidecar to native binary per target platform | CI only |
| Redis (external) | Source of truth for mageflow task state | Python sidecar (read/write via Rapyer) |

## Recommended Project Structure

```
mage-voyence/
├── frontend/                      # Existing React/Vite app (unchanged)
│   ├── src/
│   │   ├── services/
│   │   │   ├── httpTaskClient.ts  # Uses dynamic base URL from Tauri
│   │   │   └── TaskClientContext.tsx
│   │   └── ...
│   └── vite.config.ts
│
├── libs/mage-voyance/
│   └── visualizer/
│       ├── server.py              # FastAPI app (existing, keep as-is)
│       ├── commands.py            # CLI entry point (add --port arg)
│       └── models.py
│
└── src-tauri/                     # New: Tauri shell
    ├── tauri.conf.json            # externalBin, bundle config, updater
    ├── capabilities/
    │   └── default.json           # shell:allow-sidecar, http permissions
    ├── binaries/                  # Platform-specific sidecar binaries
    │   ├── mageflow-viewer-x86_64-unknown-linux-gnu
    │   ├── mageflow-viewer-x86_64-pc-windows-msvc.exe
    │   ├── mageflow-viewer-aarch64-apple-darwin
    │   └── mageflow-viewer-x86_64-apple-darwin
    ├── Cargo.toml
    ├── build.rs
    └── src/
        ├── main.rs                # Entry point
        └── lib.rs                 # setup_sidecar, get_backend_port command
```

### Structure Rationale

- **`src-tauri/binaries/`:** Tauri requires platform-specific target triple suffixes; Nuitka CI builds deposit compiled binaries here before `tauri build`.
- **`src-tauri/capabilities/`:** Tauri v2 uses fine-grained capability files instead of a flat allowlist. Sidecar execution requires `shell:allow-sidecar`, HTTP requests to localhost require `http:default`.
- **`frontend/src/services/httpTaskClient.ts`:** Needs one change — read port from `invoke('get_backend_port')` instead of `import.meta.env.VITE_API_URL` when running inside Tauri. The `window.__TAURI__` guard makes this safe for web-only builds too.

## Architectural Patterns

### Pattern 1: Rust as Process Manager, HTTP as Data Channel

**What:** Rust manages the sidecar lifecycle (spawn, health-poll, kill) while all data flows via HTTP between the webview and the Python server. Rust does not proxy requests.

**When to use:** Always — this is the standard Tauri + HTTP sidecar pattern. It avoids Rust becoming a bottleneck for API traffic and keeps Python code unchanged.

**Trade-offs:** Requires CORS to be disabled (or scoped to `localhost`) in the FastAPI server for production mode. The existing `create_dev_app()` already has permissive CORS; `create_app()` should be tightened to `allow_origins=["tauri://localhost", "http://tauri://localhost"]`.

**Example (Rust startup):**
```rust
// src-tauri/src/lib.rs
use tauri_plugin_shell::ShellExt;

fn setup_sidecar(app: &tauri::App) -> Result<(), Box<dyn std::error::Error>> {
    let port = find_free_port()?;
    let (_rx, child) = app
        .shell()
        .sidecar("mageflow-viewer")?
        .args(["--port", &port.to_string(), "--host", "127.0.0.1"])
        .spawn()?;

    // Store child handle and port in managed state
    app.manage(SidecarState { child, port });

    // Poll /api/health before emitting ready event
    let app_handle = app.handle().clone();
    tauri::async_runtime::spawn(async move {
        wait_for_health(port).await;
        app_handle.emit("backend-ready", port).unwrap();
    });
    Ok(())
}
```

### Pattern 2: Dynamic Port Allocation

**What:** Rust allocates a random free port by binding a `TcpListener` to port 0, then passes that port to the sidecar as a `--port` CLI argument.

**When to use:** Always — hardcoded ports fail when another process (or second app instance) owns the port.

**Trade-offs:** The React frontend cannot know the port at build time. It must call `invoke('get_backend_port')` at runtime. This requires a small change to `HttpTaskClient` constructor.

**Example:**
```rust
fn find_free_port() -> std::io::Result<u16> {
    let listener = std::net::TcpListener::bind("127.0.0.1:0")?;
    Ok(listener.local_addr()?.port())
    // listener drops here, releasing port; race window is tiny
}
```

### Pattern 3: Readiness Gate Before Showing Window

**What:** Keep the main window hidden or show a loading splash until `/api/health` returns 200. Only then emit `backend-ready` and show the real UI.

**When to use:** Always — Nuitka binaries start fast (~100-300ms) but the Python asyncio event loop and Rapyer/Redis initialization take additional time. Showing the UI before the backend is ready causes a broken first-load experience.

**Trade-offs:** Adds slight perceived startup delay. Use a simple loading screen (Tauri can show a `splashscreen` window, then close it on `backend-ready`).

## Data Flow

### Startup Sequence

```
User launches app
    ↓
Tauri main() [main.rs]
    ↓
find_free_port() → port=54321
    ↓
shell().sidecar("mageflow-viewer").args(["--port","54321"]).spawn()
    ↓
Python process starts, FastAPI binds 127.0.0.1:54321, Rapyer connects to Redis
    ↓
Rust polls GET http://127.0.0.1:54321/api/health (retry loop, 50ms interval)
    ↓
health returns 200
    ↓
app.emit("backend-ready", 54321)
    ↓
React: listen for "backend-ready" → store port in state
    ↓
HttpTaskClient initialized with baseUrl = "http://127.0.0.1:54321"
    ↓
TanStack Query begins fetching workflow data
```

### Normal API Request Flow

```
User navigates to workflow
    ↓
React component → useQuery() → HttpTaskClient.getRootTaskIds()
    ↓
fetch("http://127.0.0.1:54321/api/workflows/roots")
    ↓
FastAPI route handler
    ↓
TaskSignature.afind() / ChainTaskSignature.afind() / SwarmTaskSignature.afind()
    ↓
Rapyer → redis.asyncio → user's Redis instance
    ↓
JSON response ← React component renders graph
```

### Shutdown Sequence

```
User closes window
    ↓
Tauri on_window_event(CloseRequested)
    ↓
SidecarState.child.kill()   [SIGKILL on POSIX, TerminateProcess on Windows]
    ↓
Python process exits
    ↓
Tauri process exits
```

Note: For Nuitka-compiled single-file binaries, `child.kill()` directly kills the compiled process (unlike PyInstaller's bootloader issue). This is a key advantage of Nuitka.

### Frontend Port Discovery

```
React app loads (served from tauri://localhost or file://)
    ↓
window.__TAURI__ is defined → running in desktop mode
    ↓
invoke('get_backend_port') → Rust returns stored port number
    ↓
HttpTaskClient("http://127.0.0.1:" + port)
```

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| User's Redis | TCP from Python sidecar via `redis.asyncio` | URL from `REDIS_URL` env var or future connection settings UI |
| User's Hatchet | Not connected in viewer — viewer reads Redis state written by mageflow | No Hatchet SDK in sidecar |
| Auto-updater | Tauri built-in updater plugin (`tauri-plugin-updater`) | Checks GitHub Releases endpoint |
| Package managers | CI produces `.dmg`, `.msi`, `.deb`/`.AppImage` artifacts | Homebrew formula, Chocolatey package, apt/snap require separate publish step |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| React webview ↔ Rust core | Tauri IPC `invoke()`/`emit()` | Used only for port discovery and lifecycle events, not API data |
| React webview ↔ Python sidecar | HTTP REST (fetch) | All workflow data flows here; CORS scoped to `tauri://localhost` in production |
| Rust core ↔ Python sidecar | OS process (spawn/kill) + stdout/stderr capture | Port passed as CLI arg; health polling over TCP |
| Python sidecar ↔ Redis | `redis.asyncio` TCP connection | URL injected at launch; sidecar reads task state written by mageflow workers |

## Build Order Implications

The components have hard dependencies that dictate build order per phase:

1. **Sidecar binary must exist before `tauri build`** — `src-tauri/binaries/` must contain the platform-specific Nuitka binary before Tauri bundles the app. CI matrix: build sidecar on each native runner first, upload as artifact, then run `tauri build`.

2. **Frontend static assets must be built before sidecar production mode** — The existing `server.py` serves `static/index.html` for non-API routes. In the Tauri model, the frontend is served by Tauri's webview directly from `src-tauri/frontend-dist/`; sidecar no longer needs to serve static files. This is a small existing-code change.

3. **Port discovery change in React is prerequisite for any Tauri integration** — Without this, the webview will call the wrong URL and the app won't function.

**Recommended phase order derived from dependencies:**
- Phase 1: Sidecar binary build (Nuitka compilation + CI matrix)
- Phase 2: Rust shell + port management + health gating
- Phase 3: Frontend port discovery wiring (one-line `HttpTaskClient` change)
- Phase 4: Packaging + signing + updater
- Phase 5: Package manager distribution

## Anti-Patterns

### Anti-Pattern 1: Hardcoded Port

**What people do:** Set `baseUrl = "http://localhost:8000"` in the frontend and `--port 8000` in the sidecar CLI.

**Why it's wrong:** Fails silently when the port is occupied by another service. Second instances of the app break. Users with port 8000 in use (common) get a broken app with no explanation.

**Do this instead:** Allocate a free port in Rust at startup, pass it as `--port`, and expose it to React via `invoke('get_backend_port')`.

### Anti-Pattern 2: Rust Proxying API Traffic

**What people do:** Route all API calls through Tauri IPC commands in Rust, which then make HTTP requests to the Python server.

**Why it's wrong:** Doubles serialization overhead, adds Rust boilerplate for every endpoint, and negates the benefit of having a FastAPI server. The existing `HttpTaskClient` already works correctly with HTTP.

**Do this instead:** Let the webview call the Python server directly via `fetch()`. Rust's role is process management only.

### Anti-Pattern 3: PyInstaller Instead of Nuitka for Sidecar

**What people do:** Use PyInstaller (`-F` one-file mode) because it is more widely documented in Tauri examples.

**Why it's wrong:** PyInstaller bootloader extraction to a temp dir adds 1-3 seconds of startup latency. More critically, `child.kill()` from Tauri only kills the PyInstaller bootloader PID, not the embedded Python interpreter — the server keeps running after the user closes the app, occupying the port.

**Do this instead:** Nuitka compiles Python to C and produces a direct executable. `child.kill()` terminates the process cleanly. This is the key reason Nuitka is chosen for this project.

### Anti-Pattern 4: Serving React from Python Sidecar

**What people do:** Keep the existing pattern where FastAPI serves `static/index.html` and Tauri opens `http://localhost:{port}` as the webview URL.

**Why it's wrong:** Creates a circular startup dependency (webview needs the backend ready before showing anything, including loading UI). Tauri's webview serves local assets natively and more efficiently via `tauri://localhost` custom protocol.

**Do this instead:** Build React to `src-tauri/frontend-dist/`, let Tauri serve it via `distDir` in `tauri.conf.json`. Python sidecar exposes only `/api/` routes — remove the static file serving from `server.py`.

## Scaling Considerations

This is a local desktop app, not a web service. "Scale" means performance for a single user.

| Concern | Approach |
|---------|----------|
| Large task graphs (10k+ nodes) | Frontend already uses virtualization via xyflow; backend pagination exists on `/children` endpoint |
| Slow Redis queries | Rapyer afind() with many signatures; consider adding Redis pipeline batching in `fetch_all_tasks()` |
| Sidecar crash recovery | Tauri v2 has no built-in auto-restart; detect exit via stdout close and emit error event to UI |
| Multiple app instances | Dynamic port allocation handles this automatically |

## Sources

- [Tauri v2 Sidecar Documentation](https://v2.tauri.app/develop/sidecar/) — HIGH confidence
- [Tauri v2 IPC Overview](https://v2.tauri.app/concept/inter-process-communication/) — HIGH confidence
- [Tauri v2 Capabilities/Security Model](https://v2.tauri.app/security/capabilities/) — HIGH confidence
- [example-tauri-v2-python-server-sidecar (dieharders)](https://github.com/dieharders/example-tauri-v2-python-server-sidecar) — MEDIUM confidence (community example, Tauri v2, FastAPI, similar pattern)
- [Evil Martians: Tauri + Sidecar Architecture](https://evilmartians.com/chronicles/making-desktop-apps-with-revved-up-potential-rust-tauri-sidecar) — MEDIUM confidence (TCP variant, but component boundary reasoning applies)
- Direct codebase inspection: `libs/mage-voyance/visualizer/server.py`, `commands.py`, `frontend/src/services/httpTaskClient.ts` — HIGH confidence

---
*Architecture research for: Mageflow Viewer Desktop App (Tauri v2 + Python sidecar)*
*Researched: 2026-03-12*
