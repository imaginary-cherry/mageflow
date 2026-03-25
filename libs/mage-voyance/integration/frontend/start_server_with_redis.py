import os
import signal
import sys

import click
import uvicorn
from testcontainers.redis import RedisContainer

_redis_container = None


def cleanup_handler(signum, frame):
    global _redis_container
    print("\nReceived signal, stopping Redis container...", file=sys.stderr)
    if _redis_container:
        try:
            _redis_container.stop()
        except Exception as e:
            print(f"Error stopping container: {e}", file=sys.stderr)
    sys.exit(0)


@click.command()
@click.option("--port", default=8089, type=int, help="Port to run FastAPI server on")
def main(port: int):
    global _redis_container

    signal.signal(signal.SIGTERM, cleanup_handler)
    signal.signal(signal.SIGINT, cleanup_handler)

    try:
        print("Starting Redis container on port 6379...", file=sys.stderr)
        _redis_container = RedisContainer(
            "redis/redis-stack-server:7.2.0-v10"
        ).with_bind_ports(6379, 6379)
        _redis_container.start()
        print(f"Redis container started at localhost:6379", file=sys.stderr)

        os.environ["REDIS_URL"] = "redis://localhost:6379"

        print(f"Starting FastAPI server on port {port}...", file=sys.stderr)
        uvicorn.run(
            "visualizer.server:create_dev_app",
            factory=True,
            host="127.0.0.1",
            port=port,
            log_level="info",
            access_log=False,
        )

    except Exception as e:
        print(f"Startup failed: {e}", file=sys.stderr)
        if _redis_container:
            try:
                _redis_container.stop()
            except Exception as cleanup_error:
                print(f"Error during cleanup: {cleanup_error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
