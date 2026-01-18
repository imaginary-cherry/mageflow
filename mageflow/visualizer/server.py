import os
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import rapyer
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from redis.asyncio import Redis

from mageflow.chain.model import ChainTaskSignature
from mageflow.signature.model import TaskSignature
from mageflow.swarm.model import BatchItemTaskSignature, SwarmTaskSignature


def get_static_dir() -> Path:
    return Path(__file__).parent / "static"


def transform_task(task: TaskSignature) -> dict:
    base = {
        "id": task.key,
        "name": task.task_name,
        "successCallbacks": list(task.success_callbacks),
        "errorCallbacks": list(task.error_callbacks),
        "status": task.task_status.status.value,
    }

    if isinstance(task, ChainTaskSignature):
        base["type"] = "chain"
        base["children"] = list(task.tasks)
    elif isinstance(task, SwarmTaskSignature):
        base["type"] = "swarm"
        base["children"] = list(task.tasks)
    elif isinstance(task, BatchItemTaskSignature):
        base["type"] = "task"
        base["parent"] = task.swarm_id
    else:
        base["type"] = "task"

    return base


async def fetch_all_tasks() -> dict:
    base_tasks = await TaskSignature.afind()
    chains = await ChainTaskSignature.afind()
    swarms = await SwarmTaskSignature.afind()
    batch_items = await BatchItemTaskSignature.afind()

    all_tasks = list(base_tasks) + list(chains) + list(swarms) + list(batch_items)
    return {task.key: transform_task(task) for task in all_tasks}


@asynccontextmanager
async def lifespan(app: FastAPI):
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    redis_client = Redis.from_url(redis_url, decode_responses=True)
    await rapyer.init_rapyer(redis_client)
    yield
    await rapyer.teardown_rapyer()


def create_app() -> FastAPI:
    app = FastAPI(title="Mageflow Task Visualizer", lifespan=lifespan)
    static_dir = get_static_dir()

    app.mount("/static", StaticFiles(directory=static_dir / "static"), name="static")

    @app.get("/api/tasks")
    async def get_tasks():
        tasks_data = await fetch_all_tasks()
        return {"tasks": tasks_data, "error": None}

    @app.get("/")
    async def root():
        return FileResponse(static_dir / "index.html")

    @app.get("/{path:path}")
    async def catch_all(path: str):
        file_path = static_dir / path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(static_dir / "index.html")

    return app


def create_dev_app(dev_server_url: str = "http://localhost:3000") -> FastAPI:
    app = FastAPI(title="Mageflow Task Visualizer (Dev)", lifespan=lifespan)

    @app.get("/api/tasks")
    async def get_tasks():
        tasks_data = await fetch_all_tasks()
        return {"tasks": tasks_data, "error": None}

    @app.api_route(
        "/{path:path}",
        methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
    )
    async def proxy(request: Request, path: str):
        url = f"{dev_server_url}/{path}"
        if request.query_params:
            url = f"{url}?{request.query_params}"

        async with httpx.AsyncClient() as client:
            response = await client.request(
                method=request.method,
                url=url,
                headers={
                    k: v
                    for k, v in request.headers.items()
                    if k.lower() not in ("host", "content-length")
                },
                content=await request.body(),
            )
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers={
                    k: v
                    for k, v in response.headers.items()
                    if k.lower() not in ("content-encoding", "transfer-encoding")
                },
            )

    return app
