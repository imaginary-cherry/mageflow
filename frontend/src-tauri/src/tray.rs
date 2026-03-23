use tauri::{
    image::Image,
    menu::{Menu, MenuItem},
    tray::{MouseButton, MouseButtonState, TrayIcon, TrayIconBuilder, TrayIconEvent},
    AppHandle, Emitter, Manager,
};

/// Decode a PNG from embedded bytes into a Tauri `Image`.
fn png_to_image(png_bytes: &[u8]) -> tauri::Result<Image<'static>> {
    let img = image::load_from_memory_with_format(png_bytes, image::ImageFormat::Png)
        .map_err(|e| tauri::Error::Anyhow(e.into()))?;
    let rgba = img.to_rgba8();
    let (w, h) = rgba.dimensions();
    Ok(Image::new_owned(rgba.into_raw(), w, h))
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/// Create the system tray icon and context menu.
pub fn create_tray(app: &AppHandle) -> tauri::Result<TrayIcon> {
    let show = MenuItem::with_id(app, "show", "Show Window", true, None::<&str>)?;
    let settings = MenuItem::with_id(app, "settings", "Settings...", true, None::<&str>)?;
    let quit = MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?;

    let menu = Menu::with_items(app, &[&show, &settings, &quit])?;

    // Start with yellow icon (starting state).
    let icon = png_to_image(include_bytes!("../icons/tray-yellow.png"))?;

    let tray = TrayIconBuilder::with_id("main")
        .icon(icon)
        .menu(&menu)
        .tooltip("Mage Voyance - starting")
        .show_menu_on_left_click(false)
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
                let _ = app.emit("open-settings", ());
            }
            "quit" => {
                app.exit(0);
            }
            _ => {}
        })
        .build(app)?;

    Ok(tray)
}

/// Update the tray icon to reflect the given connection status.
pub fn update_tray_icon(app: &AppHandle, status: &str) {
    let icon_bytes: &[u8] = match status {
        "connected" => include_bytes!("../icons/tray-green.png"),
        "starting" | "partial" => include_bytes!("../icons/tray-yellow.png"),
        _ => include_bytes!("../icons/tray-red.png"),
    };

    let tooltip = format!("Mage Voyance - {}", status);

    if let Some(tray) = app.tray_by_id("main") {
        if let Ok(icon) = png_to_image(icon_bytes) {
            let _ = tray.set_icon(Some(icon));
        }
        let _ = tray.set_tooltip(Some(&tooltip));
    }
}
