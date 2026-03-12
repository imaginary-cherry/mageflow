use tauri::{
    image::Image,
    menu::{Menu, MenuItem},
    tray::{MouseButton, MouseButtonState, TrayIcon, TrayIconBuilder, TrayIconEvent},
    AppHandle, Emitter, Manager,
};

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/// Create the system tray icon and context menu.
/// Returns the TrayIcon handle (Tauri keeps the icon alive as long as the
/// handle is held, so it should be stored in app state or kept alive by the
/// builder internally — Tauri v2 stores it internally via `id`).
pub fn create_tray(app: &AppHandle) -> tauri::Result<TrayIcon> {
    let show = MenuItem::with_id(app, "show", "Show Window", true, None::<&str>)?;
    let settings = MenuItem::with_id(app, "settings", "Settings...", true, None::<&str>)?;
    let quit = MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?;

    let menu = Menu::with_items(app, &[&show, &settings, &quit])?;

    // Start with yellow icon (starting state).
    let icon = Image::from_bytes(include_bytes!("../icons/tray-yellow.png"))?;

    let tray = TrayIconBuilder::with_id("main")
        .icon(icon)
        .menu(&menu)
        .tooltip("Mageflow Viewer - starting")
        // Left click should toggle the window, NOT open the menu.
        .menu_on_left_click(false)
        .on_tray_icon_event(|tray, event| {
            if let TrayIconEvent::Click {
                button: MouseButton::Left,
                button_state: MouseButtonState::Up,
                ..
            } = event
            {
                let app = tray.app_handle();
                if let Some(window) = app.get_webview_window("main") {
                    match window.is_visible() {
                        Ok(true) => {
                            let _ = window.hide();
                        }
                        _ => {
                            let _ = window.show();
                            let _ = window.set_focus();
                        }
                    }
                }
            }
        })
        .on_menu_event(|app, event| match event.id.as_ref() {
            "show" => {
                if let Some(window) = app.get_webview_window("main") {
                    let _ = window.show();
                    let _ = window.set_focus();
                }
            }
            "settings" => {
                // The React frontend listens for this event and opens SettingsDialog.
                let _ = app.emit("open-settings", ());
            }
            "quit" => {
                // app.exit(0) triggers RunEvent::Exit which kills the sidecar.
                app.exit(0);
            }
            _ => {}
        })
        .build(app)?;

    Ok(tray)
}

/// Update the tray icon to reflect the given connection status.
/// Called from the `set_tray_status` Tauri command.
///
/// Recognised status values:
///   "connected"              -> green icon
///   "starting" | "partial"  -> yellow icon
///   "disconnected" | *       -> red icon
pub fn update_tray_icon(app: &AppHandle, status: &str) {
    let icon_bytes: &[u8] = match status {
        "connected" => include_bytes!("../icons/tray-green.png"),
        "starting" | "partial" => include_bytes!("../icons/tray-yellow.png"),
        _ => include_bytes!("../icons/tray-red.png"),
    };

    let tooltip = format!("Mageflow Viewer - {}", status);

    if let Some(tray) = app.tray_by_id("main") {
        if let Ok(icon) = Image::from_bytes(icon_bytes) {
            let _ = tray.set_icon(Some(icon));
        }
        let _ = tray.set_tooltip(Some(&tooltip));
    }
}
