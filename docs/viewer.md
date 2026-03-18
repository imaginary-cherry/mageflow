---
hide:
  - navigation
---

# MageFlow Viewer

Desktop app for visualizing mageflow workflows as interactive task graphs.

![MageFlow Viewer task graph](assets/viewer/task-graph.png)

## Installation

Download the latest release for your platform from [GitHub Releases](https://github.com/imaginary-cherry/mageflow/releases):

| Platform | Format |
|----------|--------|
| macOS (Apple Silicon) | `.dmg` |
| macOS (Intel) | `.dmg` |
| Windows | `.msi` |
| Linux | `.deb` / `.AppImage` |

!!! note "macOS unsigned app"
    The macOS build is currently unsigned. On first launch, right-click the app and select "Open", then confirm in the dialog.

## First Launch

On first launch, the onboarding screen asks for your connection details:

![Onboarding screen](assets/viewer/onboarding.png)

- **Hatchet API Key** -- from your Hatchet dashboard
- **Redis URL** -- your Redis instance (e.g. `redis://localhost:6379`)

After connecting, the app starts the backend sidecar and loads your workflows automatically.

## Task Graph

The main view renders your workflow as an interactive graph.

**Node types:**

- **Simple** -- a single task execution (blue)
- **Chain** -- sequential tasks that run one after another (purple container)
- **Swarm** -- parallel tasks that run simultaneously (orange container)

The header bar shows a legend and status filters. Use **Refresh** to reload the graph.

Pan, zoom, and click any node to inspect it.

## Task Details

Click a node to open the detail panel on the right.

![Task detail panel](assets/viewer/task-detail.png)

The panel shows:

- Task type, name, and ID
- Current status
- Child tasks (sequential or parallel)
- Callbacks (success/error)
- Actions: **Pause**, **Cancel**, **Retry**

## Settings

Click the gear icon in the top-right corner to open settings.

![Settings dialog](assets/viewer/settings.png)

Update your Hatchet API key or Redis URL here. Click **Save Settings** to apply.

## System Tray

The app lives in your system tray with connection status:

- **Connection indicator** -- shows whether the backend is connected
- **Show/Hide** -- toggle the main window
- **Settings** -- open the settings dialog
- **Quit** -- fully exit the app and stop the backend

## Troubleshooting

**Connection banner appears:**
A warning banner shows when the backend becomes unreachable. Check that your Redis instance is running and your Hatchet token is valid.

**Startup error screen:**
If the sidecar fails to start, an error screen shows the details with a **Retry** button. Open **Settings** to verify your credentials.
