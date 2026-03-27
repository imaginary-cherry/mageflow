import argparse
import json
import os
import sys
from multiprocessing import freeze_support

import uvicorn

from visualizer.server import create_dev_app


def read_stdin_secrets() -> dict:
    """Read secrets from stdin (piped JSON) or fall back to env vars on TTY.

    When launched by Tauri, stdin is piped with a single JSON line containing
    secrets and an IPC token. In dev mode (TTY), falls back to environment
    variables.

    Returns:
        dict with "secrets" (dict) and "ipc_token" (str or None)
    """
    if sys.stdin.isatty():
        # Dev mode: use environment variables, no IPC token
        return {
            "secrets": {
                "redisUrl": os.getenv("REDIS_URL", "redis://localhost:6379"),
                "hatchetApiKey": os.getenv("HATCHET_API_KEY", ""),
            },
            "ipc_token": None,
        }

    # Production mode: read JSON from piped stdin (blocks until newline)
    line = sys.stdin.readline()
    if not line:
        raise RuntimeError("No secrets received on stdin -- sidecar cannot start")

    payload = json.loads(line)
    return payload


def main():
    freeze_support()  # required when Nuitka compiles multiprocessing apps
    parser = argparse.ArgumentParser(description="Mageflow Viewer backend server")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    # Read secrets from stdin (Tauri piped) or env vars (dev TTY)
    payload = read_stdin_secrets()

    # Use dev app — Tauri serves the frontend, server only needs API routes with CORS
    app = create_dev_app(
        secrets=payload["secrets"],
        ipc_token=payload.get("ipc_token"),
    )
    uvicorn.run(
        app, host=args.host, port=args.port, workers=1
    )  # workers=1 CRITICAL for Nuitka


if __name__ == "__main__":
    main()
