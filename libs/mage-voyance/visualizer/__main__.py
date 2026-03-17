import argparse
import os
from multiprocessing import freeze_support

import uvicorn

from visualizer.server import create_dev_app


def main():
    freeze_support()  # required when Nuitka compiles multiprocessing apps
    parser = argparse.ArgumentParser(description="Mageflow Viewer backend server")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--hatchet-api-key", default="")
    parser.add_argument("--redis-url", default="redis://localhost:6379")
    args = parser.parse_args()

    # Pass credentials via env vars — FastAPI lifespan reads them
    os.environ["REDIS_URL"] = args.redis_url
    if args.hatchet_api_key:
        os.environ["HATCHET_API_KEY"] = args.hatchet_api_key

    # Use dev app — Tauri serves the frontend, server only needs API routes with CORS
    app = create_dev_app()
    uvicorn.run(
        app, host=args.host, port=args.port, workers=1
    )  # workers=1 CRITICAL for Nuitka


if __name__ == "__main__":
    main()
