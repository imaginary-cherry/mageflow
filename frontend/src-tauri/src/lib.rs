mod crypto;
mod tray;

use std::sync::Mutex;
use rand::Rng;
use rand::distributions::Alphanumeric;
use tauri::{AppHandle, Manager, RunEvent, State};
use tauri_plugin_shell::ShellExt;
use tauri_plugin_shell::process::CommandChild;

const SECRET_HATCHET_API_KEY: &str = "hatchetApiKey";
const SECRET_REDIS_URL: &str = "redisUrl";

// ---------------------------------------------------------------------------
// State structs
// ---------------------------------------------------------------------------

pub struct SidecarState(pub Mutex<Option<CommandChild>>);
pub struct SidecarPort(pub Mutex<Option<u16>>);
pub struct IpcTokenState(pub Mutex<Option<String>>);

// ---------------------------------------------------------------------------
// Tauri secret commands (encrypted file via crypto module)
// ---------------------------------------------------------------------------

#[tauri::command]
fn save_secret(app: AppHandle, key: String, value: String) -> Result<(), String> {
    let data_dir = app.path().app_data_dir().map_err(|e| e.to_string())?;
    let secrets_path = data_dir.join("secrets.bin");
    let mut secrets = match crypto::load_secrets_from_file(&secrets_path) {
        Ok(Some(s)) => s,
        Ok(None) => serde_json::Map::new(),
        Err(_) => {
            let _ = std::fs::remove_file(&secrets_path);
            serde_json::Map::new()
        }
    };
    secrets.insert(key, serde_json::Value::String(value));
    crypto::save_secrets_to_file(&secrets_path, &secrets)
}

#[tauri::command]
fn load_secret(app: AppHandle, key: String) -> Result<Option<String>, String> {
    let data_dir = app.path().app_data_dir().map_err(|e| e.to_string())?;
    let secrets_path = data_dir.join("secrets.bin");
    match crypto::load_secrets_from_file(&secrets_path) {
        Ok(Some(secrets)) => Ok(secrets.get(&key).and_then(|v| v.as_str()).map(String::from)),
        Ok(None) => Ok(None),
        Err(_) => {
            let _ = std::fs::remove_file(&secrets_path);
            Ok(None)
        }
    }
}

#[tauri::command]
fn delete_secret(app: AppHandle, key: String) -> Result<(), String> {
    let data_dir = app.path().app_data_dir().map_err(|e| e.to_string())?;
    let secrets_path = data_dir.join("secrets.bin");
    let mut secrets = match crypto::load_secrets_from_file(&secrets_path) {
        Ok(Some(s)) => s,
        Ok(None) => return Ok(()),
        Err(_) => {
            let _ = std::fs::remove_file(&secrets_path);
            return Ok(());
        }
    };
    secrets.remove(&key);
    if secrets.is_empty() {
        let _ = std::fs::remove_file(&secrets_path);
        Ok(())
    } else {
        crypto::save_secrets_to_file(&secrets_path, &secrets)
    }
}

#[tauri::command]
fn load_all_secrets(app: AppHandle) -> Result<Option<String>, String> {
    let data_dir = app.path().app_data_dir().map_err(|e| e.to_string())?;
    let secrets_path = data_dir.join("secrets.bin");
    match crypto::load_secrets_from_file(&secrets_path) {
        Ok(Some(secrets)) => {
            let json = serde_json::Value::Object(secrets).to_string();
            Ok(Some(json))
        }
        Ok(None) => Ok(None),
        Err(_) => {
            let _ = std::fs::remove_file(&secrets_path);
            Ok(None)
        }
    }
}

// ---------------------------------------------------------------------------
// IPC token generation
// ---------------------------------------------------------------------------

fn generate_ipc_token() -> String {
    rand::thread_rng()
        .sample_iter(&Alphanumeric)
        .take(64)
        .map(char::from)
        .collect()
}

#[tauri::command]
fn get_ipc_token(state: State<IpcTokenState>) -> Result<String, String> {
    let guard = state.0.lock().unwrap();
    guard.clone().ok_or_else(|| "IPC token not yet generated".to_string())
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
// Sidecar readiness — poll /api/health until 200 OK
// ---------------------------------------------------------------------------

async fn poll_health(port: u16) -> Result<(), String> {
    let url = format!("http://127.0.0.1:{port}/api/health");
    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(2))
        .build()
        .map_err(|e| format!("Failed to create HTTP client: {e}"))?;

    let mut last_err = String::from("Health endpoint not reachable");
    for _ in 0..60 {
        tokio::time::sleep(std::time::Duration::from_millis(500)).await;
        match client.get(&url).send().await {
            Ok(resp) if resp.status().is_success() => return Ok(()),
            Ok(resp) => {
                last_err = format!("Health returned {}", resp.status());
            }
            Err(e) => {
                last_err = e.to_string();
            }
        }
    }
    Err(format!("Sidecar health check failed after 30s: {last_err}"))
}

/// Drain sidecar stdout/stderr events for logging (runs in background).
fn spawn_event_logger(
    mut rx: tokio::sync::mpsc::Receiver<tauri_plugin_shell::process::CommandEvent>,
) {
    use tauri_plugin_shell::process::CommandEvent;
    tauri::async_runtime::spawn(async move {
        while let Some(event) = rx.recv().await {
            match event {
                CommandEvent::Stdout(line) => {
                    let text = String::from_utf8_lossy(&line);
                    println!("[sidecar:stdout] {}", text.trim());
                }
                CommandEvent::Stderr(line) => {
                    let text = String::from_utf8_lossy(&line);
                    eprintln!("[sidecar:stderr] {}", text.trim());
                }
                CommandEvent::Terminated(payload) => {
                    eprintln!("[sidecar] Terminated (code: {:?})", payload.code);
                    break;
                }
                _ => {}
            }
        }
    });
}

// ---------------------------------------------------------------------------
// Sidecar spawn
// ---------------------------------------------------------------------------

async fn spawn_sidecar(app: &AppHandle) -> Result<(), String> {
    let port = find_free_port();

    // Store the port immediately so the frontend can read it even if spawn is
    // deferred (first-launch / missing credentials).
    {
        let state = app.state::<SidecarPort>();
        let mut guard = state.0.lock().unwrap();
        *guard = Some(port);
    }

    // Read credentials from the encrypted secrets file.
    let data_dir = app
        .path()
        .app_data_dir()
        .map_err(|e| format!("Cannot resolve app data dir: {e}"))?;
    let secrets_path = data_dir.join("secrets.bin");
    let secrets = match crypto::load_secrets_from_file(&secrets_path) {
        Ok(Some(s)) => s,
        Ok(None) => {
            println!("[sidecar] No secrets file — skipping spawn until settings are saved");
            return Ok(());
        }
        Err(e) => {
            eprintln!("[sidecar] Failed to load secrets: {e}");
            // Corrupt file — remove it so next save starts fresh
            let _ = std::fs::remove_file(&secrets_path);
            return Err(format!("Failed to load secrets: {e}"));
        }
    };

    // Validate required secrets exist before attempting spawn.
    let has_hatchet = secrets
        .get(SECRET_HATCHET_API_KEY)
        .and_then(|v| v.as_str())
        .map_or(false, |s| !s.is_empty());
    let has_redis = secrets
        .get(SECRET_REDIS_URL)
        .and_then(|v| v.as_str())
        .map_or(false, |s| !s.is_empty());
    if !has_hatchet || !has_redis {
        println!("[sidecar] Required secrets missing — skipping spawn until settings are saved");
        return Ok(());
    }

    // Generate ephemeral IPC token for this launch.
    let ipc_token = generate_ipc_token();

    // Build and launch the sidecar command (no env vars — secrets via stdin).
    let shell = app.shell();
    let (rx, mut child) = shell
        .sidecar("mageflow-server")
        .expect("Failed to create sidecar command")
        .args(["--port", &port.to_string(), "--host", "127.0.0.1"])
        .spawn()
        .map_err(|e| format!("Failed to spawn mageflow-server: {e}"))?;

    // Write secrets + IPC token to sidecar stdin as a single JSON line.
    let payload = serde_json::json!({
        "secrets": secrets,
        "ipc_token": &ipc_token,
    });
    let mut line = serde_json::to_string(&payload).map_err(|e| e.to_string())?;
    line.push('\n');
    child
        .write(line.as_bytes())
        .map_err(|e| format!("Failed to write secrets to sidecar stdin: {e}"))?;
    println!("[sidecar] Secrets delivered via stdin");

    // Drain sidecar stdout/stderr in background for logging.
    spawn_event_logger(rx);

    // Store the IPC token before polling health so the frontend can fetch it
    // as soon as it detects the sidecar port — avoids a race where the frontend
    // finishes its own health polling before this function stores the token.
    {
        let token_state = app.state::<IpcTokenState>();
        let mut guard = token_state.0.lock().unwrap();
        *guard = Some(ipc_token);
    }

    // Poll health endpoint until sidecar is ready.
    if let Err(e) = poll_health(port).await {
        eprintln!("[sidecar] {e}");
        let _ = child.kill();
        return Err(e);
    }
    println!("[sidecar] Ready on port {port}");

    // Store the child process handle.
    {
        let state = app.state::<SidecarState>();
        let mut guard = state.0.lock().unwrap();
        *guard = Some(child);
    }

    Ok(())
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
    spawn_sidecar(&app).await?;
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
        .manage(SidecarState(Mutex::new(None)))
        .manage(SidecarPort(Mutex::new(None)))
        .manage(IpcTokenState(Mutex::new(None)))
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
            save_secret,
            load_secret,
            delete_secret,
            load_all_secrets,
            get_ipc_token,
        ])
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app_handle, event| match event {
            RunEvent::Ready => {
                let app = app_handle.clone();
                tauri::async_runtime::spawn(async move {
                    if let Err(e) = spawn_sidecar(&app).await {
                        eprintln!("[sidecar] Startup error: {e}");
                    }
                });
            }
            RunEvent::ExitRequested { .. } | RunEvent::Exit => {
                kill_sidecar(app_handle);
            }
            _ => {}
        });
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_generate_ipc_token_length() {
        let token = generate_ipc_token();
        assert_eq!(token.len(), 64, "Token must be exactly 64 characters");
    }

    #[test]
    fn test_generate_ipc_token_alphanumeric() {
        let token = generate_ipc_token();
        assert!(
            token.chars().all(|c| c.is_ascii_alphanumeric()),
            "All characters must be alphanumeric, got: {token}"
        );
    }

    #[test]
    fn test_generate_ipc_token_unique() {
        let token1 = generate_ipc_token();
        let token2 = generate_ipc_token();
        assert_ne!(token1, token2, "Two generated tokens must differ");
    }
}
