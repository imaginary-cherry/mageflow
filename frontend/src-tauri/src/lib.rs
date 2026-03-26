mod crypto;
mod tray;

use std::sync::Mutex;
use tauri::{AppHandle, Manager, RunEvent, State};
use tauri_plugin_shell::ShellExt;
use tauri_plugin_shell::process::CommandChild;
use tauri_plugin_store::StoreExt;

const KEYRING_SERVICE: &str = "dev.mageflow.viewer";
const SECRET_HATCHET_API_KEY: &str = "hatchetApiKey";
const SECRET_REDIS_URL: &str = "redisUrl";

// ---------------------------------------------------------------------------
// State structs
// ---------------------------------------------------------------------------

pub struct SidecarState(pub Mutex<Option<CommandChild>>);
pub struct SidecarPort(pub Mutex<Option<u16>>);

// ---------------------------------------------------------------------------
// Keyring helpers
// ---------------------------------------------------------------------------

/// Read a secret from the OS keychain.
/// - `Ok(Some(value))` — secret exists and was read successfully.
/// - `Ok(None)` — no entry exists for this key (first launch).
/// - `Err(msg)` — entry may exist but access was denied (e.g. after app rename).
fn read_secret(key: &str) -> Result<Option<String>, String> {
    let entry = keyring::Entry::new(KEYRING_SERVICE, key)
        .map_err(|e| format!("keyring init error: {e}"))?;
    match entry.get_password() {
        Ok(s) => Ok(Some(s)),
        Err(keyring::Error::NoEntry) => Ok(None),
        Err(e) => Err(format!("keyring access error: {e}")),
    }
}

fn write_secret(key: &str, value: &str) -> Result<(), String> {
    let entry =
        keyring::Entry::new(KEYRING_SERVICE, key).map_err(|e| format!("keyring error: {e}"))?;
    entry
        .set_password(value)
        .map_err(|e| format!("keyring set error: {e}"))
}

fn delete_secret_entry(key: &str) {
    if let Ok(entry) = keyring::Entry::new(KEYRING_SERVICE, key) {
        let _ = entry.delete_credential();
    }
}

// ---------------------------------------------------------------------------
// Tauri keyring commands
// ---------------------------------------------------------------------------

#[tauri::command]
fn save_secret(key: String, value: String) -> Result<(), String> {
    write_secret(&key, &value)
}

#[tauri::command]
fn load_secret(key: String) -> Result<Option<String>, String> {
    read_secret(&key)
}

#[tauri::command]
fn delete_secret(key: String) -> Result<(), String> {
    delete_secret_entry(&key);
    Ok(())
}

/// Check whether the keychain is accessible.
/// Returns `"ok"` (credentials readable), `"empty"` (no entries), or `"denied:<detail>"`.
#[tauri::command]
fn check_keychain_health() -> String {
    let hatchet = read_secret(SECRET_HATCHET_API_KEY);
    let redis = read_secret(SECRET_REDIS_URL);

    match (&hatchet, &redis) {
        // Both readable (even if empty/None — that just means first launch)
        (Ok(Some(h)), Ok(Some(r))) if !h.is_empty() && !r.is_empty() => "ok".to_string(),
        // At least one access denied
        (Err(e), _) | (_, Err(e)) => format!("denied:{e}"),
        // No entries or empty values
        _ => "empty".to_string(),
    }
}

// ---------------------------------------------------------------------------
// One-time migration: settings.json store → OS keychain
// ---------------------------------------------------------------------------

fn migrate_secrets_to_keychain(app: &AppHandle) {
    let store = match app.store("settings.json") {
        Ok(s) => s,
        Err(_) => return, // no store yet — nothing to migrate
    };

    for key in &[SECRET_HATCHET_API_KEY, SECRET_REDIS_URL] {
        if let Some(val) = store.get(*key) {
            if let Some(s) = val.as_str() {
                if !s.is_empty() {
                    // Only write if keychain doesn't already have a value
                    if matches!(read_secret(key), Ok(None)) {
                        if write_secret(key, s).is_err() {
                            continue;
                        }
                    }
                    store.delete(*key);
                }
            }
        }
    }
    let _ = store.save();
}

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

    // Read credentials from the OS keychain.
    let hatchet_key = match read_secret(SECRET_HATCHET_API_KEY) {
        Ok(Some(s)) if !s.is_empty() => s,
        Ok(_) => {
            println!("[sidecar] {} not in keychain — skipping spawn until settings are saved", SECRET_HATCHET_API_KEY);
            return;
        }
        Err(e) => {
            eprintln!("[sidecar] keychain access denied for {}: {}", SECRET_HATCHET_API_KEY, e);
            return;
        }
    };
    let redis_url = match read_secret(SECRET_REDIS_URL) {
        Ok(Some(s)) if !s.is_empty() => s,
        Ok(_) => {
            println!("[sidecar] {} not in keychain — skipping spawn until settings are saved", SECRET_REDIS_URL);
            return;
        }
        Err(e) => {
            eprintln!("[sidecar] keychain access denied for {}: {}", SECRET_REDIS_URL, e);
            return;
        }
    };

    // Build and launch the sidecar command.
    // Secrets are passed via env vars (not CLI args) to avoid exposure in process listings.
    let shell = app.shell();
    match shell
        .sidecar("mageflow-server")
        .expect("Failed to create sidecar command")
        .args([
            "--port",
            &port.to_string(),
            "--host",
            "127.0.0.1",
        ])
        .envs([
            ("HATCHET_API_KEY", &hatchet_key),
            ("REDIS_URL", &redis_url),
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
            migrate_secrets_to_keychain(app.handle());
            tray::create_tray(app.handle())?;
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            get_sidecar_port,
            get_sidecar_status,
            restart_sidecar,
            set_tray_status,
            save_secret,
            load_secret,
            delete_secret,
            check_keychain_health,
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
