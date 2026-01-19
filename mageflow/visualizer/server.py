import os
from contextlib import asynccontextmanager
from pathlib import Path

import rapyer
from fastapi import FastAPI, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from redis.asyncio import Redis

from mageflow.chain.model import ChainTaskSignature
from mageflow.signature.model import TaskSignature
from mageflow.swarm.model import BatchItemTaskSignature, SwarmTaskSignature


def get_static_dir() -> Path:
    return Path(__file__).parent / "static"


async def get_task_by_id(task_id: str) -> TaskSignature | None:
    for task_cls in [
        ChainTaskSignature,
        SwarmTaskSignature,
        BatchItemTaskSignature,
        TaskSignature,
    ]:
        task = await task_cls.get_safe(task_id)
        if task is not None:
            return task
    return None


def to_camel_case(snake_str: str) -> str:
    components = snake_str.split("_")
    return components[0] + "".join(x.title() for x in components[1:])


EXCLUDE_FIELDS = {"model_validators", "modelValidators"}


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


async def fetch_task_children(task_id: str, page: int = 0, size: int = 10) -> dict:
    task = await get_task_by_id(task_id)
    if task is None:
        return {"children": {}, "total": 0, "page": page, "hasMore": False}

    if not isinstance(task, (ChainTaskSignature, SwarmTaskSignature)):
        return {"children": {}, "total": 0, "page": page, "hasMore": False}

    batch_items = list(await BatchItemTaskSignature.afind())
    batch_to_original = {bi.key: bi.original_task_id for bi in batch_items}
    original_to_swarm = {bi.original_task_id: bi.swarm_id for bi in batch_items}

    child_ids = (
        list(task.tasks)
        if isinstance(task, ChainTaskSignature)
        else [batch_to_original.get(bid, bid) for bid in task.tasks]
    )

    total = len(child_ids)
    start_idx = page * size
    end_idx = min(start_idx + size, total)
    page_child_ids = child_ids[start_idx:end_idx]

    children = {}
    for child_id in page_child_ids:
        child_task = await get_task_by_id(child_id)
        if child_task:
            children[child_id] = serialize_task(
                child_task, batch_to_original, original_to_swarm
            )

    return {
        "children": children,
        "total": total,
        "page": page,
        "hasMore": end_idx < total,
    }


async def fetch_task_callbacks(task_id: str) -> dict:
    task = await get_task_by_id(task_id)
    if task is None:
        return {"callbacks": {}, "successCallbacks": [], "errorCallbacks": []}

    batch_items = list(await BatchItemTaskSignature.afind())
    batch_to_original = {bi.key: bi.original_task_id for bi in batch_items}
    original_to_swarm = {bi.original_task_id: bi.swarm_id for bi in batch_items}

    success_callback_ids = list(task.success_callbacks)
    error_callback_ids = list(task.error_callbacks)
    all_callback_ids = success_callback_ids + error_callback_ids

    callbacks = {}
    for callback_id in all_callback_ids:
        callback_task = await get_task_by_id(callback_id)
        if callback_task:
            callbacks[callback_id] = serialize_task(
                callback_task, batch_to_original, original_to_swarm
            )

    return {
        "callbacks": callbacks,
        "successCallbacks": success_callback_ids,
        "errorCallbacks": error_callback_ids,
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    redis_client = Redis.from_url(redis_url, decode_responses=True)
    await rapyer.init_rapyer(redis_client)
    yield
    await rapyer.teardown_rapyer()


def register_api_routes(app: FastAPI):
    @app.get("/api/tasks")
    async def get_tasks():
        tasks_data = await fetch_all_tasks()
        return {"tasks": tasks_data, "error": None}

    @app.get("/api/tasks/roots")
    async def get_root_tasks():
        tasks_data = await fetch_root_tasks()
        return {"tasks": tasks_data, "error": None}

    @app.get("/api/tasks/{task_id}/children")
    async def get_task_children(
        task_id: str,
        page: int = Query(default=0, ge=0),
        size: int = Query(default=10, ge=1, le=100),
    ):
        result = await fetch_task_children(task_id, page, size)
        return {**result, "error": None}

    @app.get("/api/tasks/{task_id}/callbacks")
    async def get_task_callbacks(task_id: str):
        result = await fetch_task_callbacks(task_id)
        return {**result, "error": None}


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
