import argparse
from multiprocessing import freeze_support

import uvicorn

from visualizer.server import create_dev_app


def main():
    freeze_support()  # required when Nuitka compiles multiprocessing apps
    parser = argparse.ArgumentParser(description="Mageflow Viewer backend server")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    # Secrets (HATCHET_API_KEY, REDIS_URL) are expected as env vars set by the
    # launcher (Tauri sidecar).  This avoids leaking them in process listings.

    # Use dev app — Tauri serves the frontend, server only needs API routes with CORS
    app = create_dev_app()
    uvicorn.run(
        app, host=args.host, port=args.port, workers=1
    )  # workers=1 CRITICAL for Nuitka


if __name__ == "__main__":
    main()
