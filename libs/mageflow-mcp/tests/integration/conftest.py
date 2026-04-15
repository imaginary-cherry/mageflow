import asyncio
import dataclasses
import logging
import os
import subprocess
import sys
import time
import uuid
from contextlib import contextmanager
from io import BytesIO
from pathlib import Path
from threading import Thread
from typing import AsyncGenerator, Callable, Generator

import psutil
import pytest_asyncio
import rapyer
import requests
from dynaconf import Dynaconf
from hatchet_sdk import Hatchet
from hatchet_sdk.clients.admin import TriggerWorkflowOptions
from redis.asyncio.client import Redis

import mageflow
from mageflow import Mageflow
from mageflow.client import HatchetMageflow
from mageflow.startup import init_mageflow
from tests.integration.models import ContextMessage
from tests.integration.worker import (
    chain_callback,
    config_obj,
    fail_task,
    logging_task,
    task1,
    task2,
    task3,
)
from thirdmagic.signature import Signature
from thirdmagic.task_def import MageflowTaskDefinition

STATIC_REDIS_PREFIX_KEYS = [MageflowTaskDefinition.__name__]

settings = Dynaconf(
    envvar_prefix="DYNACONF",
    settings_files=["settings.toml", ".secrets.toml"],
)


@dataclasses.dataclass
class HatchetInitData:
    redis_client: Redis
    hatchet: HatchetMageflow


@dataclasses.dataclass
class DispatchedTasks:
    """Holds all pre-dispatched task signatures for shared test use."""

    task1_sig: Signature
    task2_sig: Signature
    fail_sig: Signature
    logging_sig: Signature
    chain_sig: Signature
    chain_task_sigs: list[Signature]  # [sig1, sig2, sig3] in the chain
    logging_workflow_run_id: str  # workflow run ID for log lookup


# ── Redis fixtures ──────────────────────────────────────────────────────


@pytest_asyncio.fixture(scope="session", loop_scope="session")
def redis_client():
    client = Redis.from_url(settings.redis.url, decode_responses=True)
    yield client


# ── Hatchet fixtures ───────────────────────────────────────────────────


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def hatchet_client_init(redis_client) -> AsyncGenerator[HatchetInitData, None]:
    await rapyer.init_rapyer(redis_client, prefer_normal_json_dump=True)
    copy_config = config_obj.model_copy(deep=True)
    h = Hatchet(debug=True, config=copy_config)
    mf = Mageflow(h, redis_client)
    await init_mageflow(redis_client, [])
    yield HatchetInitData(redis_client=redis_client, hatchet=mf)
    await rapyer.teardown_rapyer()


# ── Worker deployment ───────────────────────────────────────────────────


def wait_for_worker_health(healthcheck_port: int) -> bool:
    attempts = 0
    max_attempts = 25
    last_error = None

    while True:
        if attempts > max_attempts:
            raise last_error

        try:
            requests.get(f"http://localhost:{healthcheck_port}/health", timeout=5)
            return True
        except Exception as e:
            last_error = e
            time.sleep(1)

        attempts += 1


def log_output(
    pipe: BytesIO, log_func: Callable[[str], None], prefix: str = ""
) -> None:
    for line in iter(pipe.readline, b""):
        decoded_line = line.decode().strip()
        if decoded_line:
            log_func(f"[WORKER{prefix}] {decoded_line}")


@contextmanager
def hatchet_worker(
    command: list[str],
    healthcheck_port: int = 8002,
) -> Generator[subprocess.Popen[bytes], None, None]:
    logger = logging.getLogger()
    if not logger.handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            force=True,
        )

    logging.info(f"Starting background worker: {' '.join(command)}")

    os.environ["HATCHET_CLIENT_WORKER_HEALTHCHECK_PORT"] = str(healthcheck_port)
    env = os.environ.copy()

    current_path = Path(__file__).absolute()
    project_root = current_path
    while project_root.parent != project_root:
        if (project_root / "pyproject.toml").exists():
            break
        project_root = project_root.parent

    if not (project_root / "pyproject.toml").exists():
        raise RuntimeError(
            f"Could not find project root with pyproject.toml starting from {current_path}"
        )

    logging.info(f"Project root found: {project_root}")
    logging.info(f"Settings file exists: {(project_root / '.secrets.toml').exists()}")

    python_path = env.get("PYTHONPATH", "")
    if str(project_root) not in python_path:
        if python_path:
            env["PYTHONPATH"] = f"{project_root}:{python_path}"
        else:
            env["PYTHONPATH"] = str(project_root)

    env["COVERAGE_PROCESS_START"] = str(project_root / "pyproject.toml")

    proc = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        cwd=project_root,
    )

    if proc.poll() is not None:
        raise Exception(f"Worker failed to start with return code {proc.returncode}")

    Thread(
        target=log_output, args=(proc.stdout, logging.info, "-STDOUT"), daemon=True
    ).start()
    Thread(
        target=log_output, args=(proc.stderr, logging.error, "-STDERR"), daemon=True
    ).start()

    wait_for_worker_health(healthcheck_port=healthcheck_port)

    yield proc

    logging.info("Cleaning up background worker")

    parent = psutil.Process(proc.pid)
    children = parent.children(recursive=True)

    for child in children:
        child.terminate()

    parent.terminate()

    _, alive = psutil.wait_procs([parent] + children, timeout=5)

    for p in alive:
        logging.warning(f"Force killing process {p.pid}")
        p.kill()


@pytest_asyncio.fixture(scope="session", loop_scope="session", autouse=True)
async def hatchet_worker_deploy(
    redis_client,
) -> AsyncGenerator[subprocess.Popen[bytes], None]:
    await redis_client.flushall()
    current_file = Path(__file__).absolute()
    test_worker_path = current_file.parent / "worker.py"
    command = [sys.executable, str(test_worker_path)]

    with hatchet_worker(command) as proc:
        await asyncio.sleep(10)
        yield proc
    await redis_client.flushall()


# ── Shared dispatched tasks (run once per session) ──────────────────────


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def dispatched_tasks(
    hatchet_client_init: HatchetInitData,
    hatchet_worker_deploy,
) -> DispatchedTasks:
    """Dispatch all tasks once and wait for completion.

    Every test reads from these pre-dispatched results instead of
    dispatching its own tasks, saving ~5-15s of sleep per test.
    """
    test_ctx = {"test_data": uuid.uuid4().hex}
    metadata = {"test_run_id": uuid.uuid4().hex}
    trigger_opts = TriggerWorkflowOptions(additional_metadata=metadata)
    message = ContextMessage(base_data=test_ctx)

    # Sign individual tasks
    task1_sig = await mageflow.asign(task1)
    task2_sig = await mageflow.asign(task2)
    fail_sig = await mageflow.asign(fail_task)
    logging_sig = await mageflow.asign(logging_task)

    # Sign chain tasks
    chain_t1 = await mageflow.asign(task1)
    chain_t2 = await mageflow.asign(task2)
    chain_t3 = await mageflow.asign(task3)
    chain_cb = await mageflow.asign(chain_callback)
    chain_sig = await mageflow.achain(
        [chain_t1, chain_t2, chain_t3],
        success=chain_cb,
    )

    # Dispatch all
    await task1_sig.aio_run_no_wait(message, options=trigger_opts)
    await task2_sig.aio_run_no_wait(message, options=trigger_opts)
    await fail_sig.aio_run_no_wait(message, options=trigger_opts)
    logging_ref = await logging_sig.aio_run_no_wait(message, options=trigger_opts)
    await chain_sig.aio_run_no_wait(message, options=trigger_opts)

    # Wait for everything to complete
    await asyncio.sleep(15)

    return DispatchedTasks(
        task1_sig=task1_sig,
        task2_sig=task2_sig,
        fail_sig=fail_sig,
        logging_sig=logging_sig,
        chain_sig=chain_sig,
        chain_task_sigs=[chain_t1, chain_t2, chain_t3],
        logging_workflow_run_id=logging_ref.workflow_run_id,
    )


# ── MCP context stub for get_logs ───────────────────────────────────────


def mock_mcp_context(adapter):
    """Create a lightweight stub satisfying ctx.request_context.lifespan_context['adapter']."""

    class _LifespanCtx(dict):
        pass

    class _RequestCtx:
        def __init__(self, lc):
            self.lifespan_context = lc

    class _Ctx:
        def __init__(self, rc):
            self.request_context = rc

    lifespan_ctx = _LifespanCtx(adapter=adapter)
    return _Ctx(_RequestCtx(lifespan_ctx))
