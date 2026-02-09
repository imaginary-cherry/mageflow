import os
from contextlib import asynccontextmanager
from pathlib import Path

import rapyer
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from rapyer.errors.base import KeyNotFound, RapyerModelDoesntExistError
from redis.asyncio import Redis
from starlette.exceptions import HTTPException as StarletteHTTPException

from mageflow.chain.model import ChainTaskSignature
from mageflow.signature.container import ContainerTaskSignature
from mageflow.signature.model import TaskSignature
from mageflow.signature.status import SignatureStatus
from mageflow.swarm.model import SwarmTaskSignature
from mageflow.visualizer.models import (
    BatchTasksRequest,
    RootTasksResponse,
    TaskCallbacksResponse,
    TaskChildrenResponse,
    TaskFromServer,
    serialize_task,
)


def get_static_dir() -> Path:
    return Path(__file__).parent / "static"


async def fetch_all_tasks() -> dict:
    base_tasks = await TaskSignature.afind()
    chains = await ChainTaskSignature.afind()
    swarms = await SwarmTaskSignature.afind()

    all_tasks = list(base_tasks) + list(chains) + list(swarms)
    return {task.key: task for task in all_tasks}


async def fetch_root_tasks() -> dict:
    base_tasks = list(await TaskSignature.afind())
    chains = list(await ChainTaskSignature.afind())
    swarms = list(await SwarmTaskSignature.afind())

    chain_children = {child_id for chain in chains for child_id in chain.tasks}
    swarm_linked_tasks = {sub_task for swarm in swarms for sub_task in swarm.task_ids}

    all_tasks = base_tasks + chains + swarms
    all_callbacks = {
        cb_id
        for task in all_tasks
        for cb_id in list(task.success_callbacks) + list(task.error_callbacks)
    }

    non_root_ids = chain_children | all_callbacks | swarm_linked_tasks

    return {task.key: task for task in all_tasks if task.key not in non_root_ids}


async def fetch_task_children(
    task_id: str, page: int = 1, page_size: int = 20
) -> TaskChildrenResponse | None:
    try:
        task = await rapyer.aget(task_id)
    except KeyNotFound:
        return None
    if not isinstance(task, ContainerTaskSignature):
        return None

    all_ids = task.task_ids

    total_count = len(all_ids)
    start = (page - 1) * page_size
    end = start + page_size
    page_ids = all_ids[start:end]

    return TaskChildrenResponse(
        task_ids=page_ids,
        total_count=total_count,
        page=page,
        page_size=page_size,
    )


async def fetch_task_callbacks(task_id: str) -> TaskCallbacksResponse | None:
    try:
        task = await rapyer.aget(task_id)
    except KeyNotFound:
        return None
    if not isinstance(task, TaskSignature):
        return None

    return TaskCallbacksResponse(
        success_callback_ids=list(task.success_callbacks),
        error_callback_ids=list(task.error_callbacks),
    )


async def fetch_tasks_batch(task_ids: list[str]) -> list[TaskFromServer]:
    if not task_ids:
        return []
    try:
        tasks = await rapyer.afind(*task_ids)
    except (KeyNotFound, RapyerModelDoesntExistError):
        return []
    return [serialize_task(task) for task in tasks if isinstance(task, TaskSignature)]


@asynccontextmanager
async def lifespan(app: FastAPI):
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    redis_client = Redis.from_url(redis_url, decode_responses=True)
    await rapyer.init_rapyer(redis_client, prefer_normal_json_dump=True)
    yield
    await rapyer.teardown_rapyer()


def register_api_routes(app: FastAPI):
    @app.get("/api/health")
    async def health():
        return {"status": "ok"}

    @app.get("/api/workflows")
    async def get_tasks():
        tasks_data = await fetch_all_tasks()
        return {"tasks": tasks_data, "error": None}

    @app.get("/api/workflows/roots")
    async def get_root_tasks() -> RootTasksResponse:
        tasks_data = await fetch_root_tasks()
        return RootTasksResponse(task_ids=list(tasks_data.keys()))

    @app.post("/api/tasks/batch")
    async def get_tasks_batch(request: BatchTasksRequest) -> list[TaskFromServer]:
        return await fetch_tasks_batch(request.task_ids)

    @app.get("/api/workflows/{task_id}/children")
    async def get_task_children(
        task_id: str, page: int = 1, page_size: int = 20
    ) -> TaskChildrenResponse | None:
        return await fetch_task_children(task_id, page, page_size)

    @app.get("/api/workflows/{task_id}/callbacks")
    async def get_task_callbacks(task_id: str) -> TaskCallbacksResponse | None:
        return await fetch_task_callbacks(task_id)

    @app.post("/api/tasks/{task_id}/cancel", status_code=status.HTTP_202_ACCEPTED)
    async def cancel_task(task_id: str):
        success = await TaskSignature.safe_change_status(
            task_id, SignatureStatus.CANCELED
        )
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task {task_id} not found"
            )
        return Response(status_code=status.HTTP_202_ACCEPTED)

    @app.post("/api/tasks/{task_id}/pause", status_code=status.HTTP_202_ACCEPTED)
    async def pause_task(task_id: str):
        success = await TaskSignature.safe_change_status(
            task_id, SignatureStatus.SUSPENDED
        )
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task {task_id} not found"
            )
        return Response(status_code=status.HTTP_202_ACCEPTED)

    @app.post("/api/tasks/{task_id}/retry", status_code=status.HTTP_202_ACCEPTED)
    async def retry_task(task_id: str):
        try:
            await TaskSignature.resume_from_key(task_id)
            return Response(status_code=status.HTTP_202_ACCEPTED)
        except KeyNotFound:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task {task_id} not found"
            )


def create_app() -> FastAPI:
    app = FastAPI(title="Mageflow Task Visualizer", lifespan=lifespan)
    static_dir = get_static_dir()
    index_file = static_dir / "index.html"

    register_api_routes(app)

    @app.exception_handler(StarletteHTTPException)
    async def spa_fallback(request: Request, exc: StarletteHTTPException):
        if exc.status_code == 404 and not request.url.path.startswith("/api"):
            return FileResponse(index_file)
        raise exc

    app.mount("/", StaticFiles(directory=static_dir, html=True), name="spa")

    return app


def create_dev_app() -> FastAPI:
    app = FastAPI(title="Mageflow Task Visualizer (Dev)", lifespan=lifespan)
    register_api_routes(app)
    return app
