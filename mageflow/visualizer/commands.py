import click

from mageflow.visualizer.server import get_static_dir


def validate_static_files_exist() -> bool:
    static_dir = get_static_dir()
    index_file = static_dir / "index.html"
    return index_file.exists()


@click.command(name="task-display")
@click.option("--host", default="127.0.0.1", help="Host to bind the server to")
@click.option("--port", default=8080, type=int, help="Port to bind the server to")
@click.option(
    "--dev", is_flag=True, help="Run in development mode with proxy to React dev server"
)
@click.option(
    "--dev-server",
    default="http://localhost:3000",
    help="React dev server URL (used with --dev)",
)
@click.option("--reload", is_flag=True, help="Enable auto-reload for uvicorn")
def task_display(host: str, port: int, dev: bool, dev_server: str, reload: bool):
    """Start the task visualization server"""
    import uvicorn

    if dev:
        click.echo(f"Starting development server, proxying to {dev_server}")
        uvicorn.run(
            "mageflow.visualizer.server:create_dev_app",
            host=host,
            port=port,
            reload=reload,
            factory=True,
        )
    else:
        if not validate_static_files_exist():
            click.echo(
                "Error: Static files not found. Please build the React app first.",
                err=True,
            )
            click.echo(
                "Run: cd app && npm run build && cp -r build/* ../mageflow/visualizer/static/",
                err=True,
            )
            raise SystemExit(1)

        click.echo(f"Starting production server at http://{host}:{port}")
        uvicorn.run(
            "mageflow.visualizer.server:create_app",
            host=host,
            port=port,
            reload=reload,
            factory=True,
        )
