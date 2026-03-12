mod tray;

use std::sync::Mutex;
use tauri::{AppHandle, Manager, RunEvent, State};
use tauri_plugin_shell::ShellExt;
use tauri_plugin_shell::process::CommandChild;
use tauri_plugin_store::StoreExt;

// ---------------------------------------------------------------------------
// State structs
// ---------------------------------------------------------------------------

pub struct SidecarState(pub Mutex<Option<CommandChild>>);
pub struct SidecarPort(pub Mutex<Option<u16>>);

// ---------------------------------------------------------------------------
// Port allocation
// ---------------------------------------------------------------------------

fn find_free_port() -> u16 {
    let listener = std::net::TcpListener::bind("127.0.0.1:0")
        .expect("Failed to bind to an ephemeral port");
    let port = listener.local_addr().unwrap().port();
    drop(listener); // release the port so the sidecar can bind it
    port
}

// ---------------------------------------------------------------------------
// Sidecar spawn
// ---------------------------------------------------------------------------

async fn spawn_sidecar(app: &AppHandle) {
    let port = find_free_port();

    // Store the port immediately so the frontend can read it even if spawn is
    // deferred (first-launch / missing credentials).
    {
        let state = app.state::<SidecarPort>();
        let mut guard = state.0.lock().unwrap();
        *guard = Some(port);
    }

    // Read credentials from the persistent store.
    // If the store doesn't exist yet (first launch) we skip spawning and let
    // the onboarding flow trigger restart_sidecar once the user saves settings.
    let hatchet_key: String;
    let redis_url: String;

    match app.store("settings.json") {
        Ok(store) => {
            let key = store.get("hatchetApiKey");
            let url = store.get("redisUrl");

            match (key, url) {
                (Some(k), Some(u)) => {
                    hatchet_key = match k.as_str() {
                        Some(s) if !s.is_empty() => s.to_string(),
                        _ => {
                            println!("[sidecar] hatchetApiKey is empty — skipping spawn until settings are saved");
                            return;
                        }
                    };
                    redis_url = match u.as_str() {
                        Some(s) if !s.is_empty() => s.to_string(),
                        _ => {
                            println!("[sidecar] redisUrl is empty — skipping spawn until settings are saved");
                            return;
                        }
                    };
                }
                _ => {
                    println!("[sidecar] Settings not found — skipping spawn until settings are saved (port {} reserved)", port);
                    return;
                }
            }
        }
        Err(e) => {
            println!("[sidecar] Could not open settings store: {} — skipping spawn", e);
            return;
        }
    }

    // Build and launch the sidecar command.
    let shell = app.shell();
    match shell
        .sidecar("binaries/mageflow-server")
        .expect("Failed to create sidecar command")
        .args([
            "--port",
            &port.to_string(),
            "--host",
            "127.0.0.1",
            "--hatchet-api-key",
            &hatchet_key,
            "--redis-url",
            &redis_url,
        ])
        .spawn()
    {
        Ok((_, child)) => {
            println!("[sidecar] Spawned mageflow-server on port {}", port);
            let state = app.state::<SidecarState>();
            let mut guard = state.0.lock().unwrap();
            *guard = Some(child);
        }
        Err(e) => {
            eprintln!("[sidecar] Failed to spawn mageflow-server: {}", e);
        }
    }
}

// ---------------------------------------------------------------------------
// Sidecar kill (synchronous — safe to call from RunEvent handlers)
// ---------------------------------------------------------------------------

fn kill_sidecar(app: &AppHandle) {
    let state = app.state::<SidecarState>();
    let mut guard = state.0.lock().unwrap();
    if let Some(child) = guard.take() {
        match child.kill() {
            Ok(_) => println!("[sidecar] mageflow-server killed"),
            Err(e) => eprintln!("[sidecar] Failed to kill mageflow-server: {}", e),
        }
    }
}

// ---------------------------------------------------------------------------
// Tauri commands
// ---------------------------------------------------------------------------

#[tauri::command]
fn get_sidecar_port(state: State<SidecarPort>) -> Result<u16, String> {
    let guard = state.0.lock().unwrap();
    guard.ok_or_else(|| "Sidecar port not yet assigned".to_string())
}

#[tauri::command]
fn get_sidecar_status(state: State<SidecarState>) -> String {
    let guard = state.0.lock().unwrap();
    if guard.is_some() { "running".to_string() } else { "stopped".to_string() }
}

#[tauri::command]
async fn restart_sidecar(app: AppHandle) -> Result<u16, String> {
    kill_sidecar(&app);
    spawn_sidecar(&app).await;
    let state = app.state::<SidecarPort>();
    let guard = state.0.lock().unwrap();
    guard.ok_or_else(|| "Sidecar port not assigned after restart".to_string())
}

// ---------------------------------------------------------------------------
// Tray command
// ---------------------------------------------------------------------------

#[tauri::command]
fn set_tray_status(app: AppHandle, status: String) {
    tray::update_tray_icon(&app, &status);
}

// ---------------------------------------------------------------------------
// App entry point
// ---------------------------------------------------------------------------

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_store::Builder::new().build())
        .manage(SidecarState(Mutex::new(None)))
        .manage(SidecarPort(Mutex::new(None)))
        .setup(|app| {
            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
            }
            tray::create_tray(app.handle())?;
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            get_sidecar_port,
            get_sidecar_status,
            restart_sidecar,
            set_tray_status,
        ])
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app_handle, event| match event {
            RunEvent::Ready => {
                let app = app_handle.clone();
                tauri::async_runtime::spawn(async move {
                    spawn_sidecar(&app).await;
                });
            }
            RunEvent::ExitRequested { .. } | RunEvent::Exit => {
                kill_sidecar(app_handle);
            }
            _ => {}
        });
}
