import os
from contextlib import asynccontextmanager
from pathlib import Path

import rapyer
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from rapyer.errors.base import KeyNotFound, RapyerModelDoesntExistError
from redis.asyncio import Redis

from mageflow.chain.model import ChainTaskSignature
from mageflow.signature.container import ContainerTaskSignature
from mageflow.signature.model import TaskSignature
from mageflow.swarm.model import BatchItemTaskSignature, SwarmTaskSignature
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
    batch_items = await BatchItemTaskSignature.afind()

    all_tasks = list(base_tasks) + list(chains) + list(swarms) + list(batch_items)
    return {task.key: task for task in all_tasks}


async def fetch_root_tasks() -> dict:
    base_tasks = list(await TaskSignature.afind())
    chains = list(await ChainTaskSignature.afind())
    swarms = list(await SwarmTaskSignature.afind())
    batch_items = list(await BatchItemTaskSignature.afind())

    chain_children = {child_id for chain in chains for child_id in chain.tasks}
    batch_item_ids = {batch_item.key for batch_item in batch_items}
    original_linked_tasks = {bi.original_task_id for bi in batch_items}
    original_to_swarm = {bi.original_task_id: bi.swarm_id for bi in batch_items}

    all_tasks = base_tasks + chains + swarms + batch_items
    all_callbacks = {
        cb_id
        for task in all_tasks
        for cb_id in list(task.success_callbacks) + list(task.error_callbacks)
    }

    non_root_ids = (
        chain_children
        | batch_item_ids
        | all_callbacks
        | set(original_to_swarm.keys())
        | original_linked_tasks
    )

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

    if isinstance(task, ChainTaskSignature):
        all_ids = list(task.tasks)
    elif isinstance(task, SwarmTaskSignature):
        all_ids = list(task.tasks)
    else:
        all_ids = []

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
    await rapyer.init_rapyer(redis_client)
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


def create_app() -> FastAPI:
    app = FastAPI(title="Mageflow Task Visualizer", lifespan=lifespan)
    static_dir = get_static_dir()

    app.mount("/static", StaticFiles(directory=static_dir / "static"), name="static")
    register_api_routes(app)

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


def create_dev_app() -> FastAPI:
    app = FastAPI(title="Mageflow Task Visualizer (Dev)", lifespan=lifespan)
    register_api_routes(app)
    return app
