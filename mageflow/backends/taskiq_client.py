"""
TaskIQ Mageflow client.

This provides a TaskIQ broker wrapper that adds Mageflow functionality
(sign, swarm, chain) while preserving the native TaskIQ API.

Usage:
    from taskiq_redis import ListQueueBroker
    from mageflow import Mageflow

    broker = ListQueueBroker(...)
    mage = Mageflow(taskiq_broker=broker, redis_client=redis_url)

    # Use like normal TaskIQ broker
    @mage.task
    async def my_task(x: int, y: int):
        return x + y

    # Plus Mageflow features
    signature = await mage.sign("my_task", x=1, y=2)
"""
from __future__ import annotations

import functools
import os
from typing import Any, Callable, TypeVar

import redis.asyncio
from pydantic import BaseModel
from redis.asyncio import Redis

from mageflow.backends.taskiq import (
    TaskIQTaskTrigger,
    TaskIQExecutionContext,
    MAGEFLOW_TASK_DATA_KEY,
)
from mageflow.chain.creator import chain
from mageflow.signature.creator import sign, TaskSignatureConvertible
from mageflow.signature.model import TaskSignature, TaskInputType
from mageflow.startup import mageflow_config
from mageflow.swarm.creator import swarm, SignatureOptions
from mageflow.callbacks import AcceptParams


F = TypeVar("F", bound=Callable[..., Any])


class TaskIQMageflow:
    """
    TaskIQ broker wrapper with Mageflow functionality.

    This class wraps a TaskIQ broker and adds:
    - sign(): Create task signatures
    - chain(): Create task chains
    - swarm(): Create task swarms
    - Automatic signature lifecycle management

    The native TaskIQ API (task decorator, .kiq(), etc.) is preserved.
    """

    def __init__(
        self,
        broker: Any,
        redis_client: Redis,
        param_config: AcceptParams = AcceptParams.NO_CTX,
    ):
        """
        Initialize TaskIQ Mageflow wrapper.

        Args:
            broker: TaskIQ broker instance (e.g., ListQueueBroker)
            redis_client: Redis client for Mageflow state
            param_config: Default parameter config for tasks
        """
        self._broker = broker
        self.redis = redis_client
        self.param_config = param_config
        self._task_registry: dict[str, Any] = {}

        # Set up task trigger for internal use
        self._task_trigger = TaskIQTaskTrigger(broker, self._task_registry)

    @property
    def broker(self) -> Any:
        """Get the underlying TaskIQ broker."""
        return self._broker

    def task(
        self,
        task_name: str | None = None,
        **labels,
    ) -> Callable[[F], F]:
        """
        Decorator to create a TaskIQ task with Mageflow lifecycle management.

        This wraps the native broker.task decorator and adds:
        - Signature key extraction from kwargs
        - Task lifecycle callbacks (start, success, error)

        Usage:
            @mage.task
            async def my_task(x: int, y: int) -> int:
                return x + y

            @mage.task(task_name="custom_name", my_label="value")
            async def another_task(msg: MyInput) -> MyOutput:
                ...
        """

        def decorator(func: F) -> F:
            name = task_name or func.__name__

            # Create wrapper that handles Mageflow lifecycle
            @functools.wraps(func)
            async def wrapper(**kwargs):
                # Extract execution context from kwargs
                exec_ctx = TaskIQExecutionContext(
                    kwargs=kwargs,
                    task_name=name,
                )

                # Get cleaned kwargs (without Mageflow metadata)
                clean_kwargs = exec_ctx.cleaned_kwargs

                # Handle Mageflow task lifecycle
                from mageflow.backends.taskiq_callbacks import handle_taskiq_task

                return await handle_taskiq_task(
                    func=func,
                    kwargs=clean_kwargs,
                    exec_ctx=exec_ctx,
                    param_config=self.param_config,
                )

            # Register with TaskIQ broker
            taskiq_task = self._broker.task(task_name=name, **labels)(wrapper)

            # Store in registry for triggering by name
            self._task_registry[name] = taskiq_task

            return taskiq_task

        return decorator

    async def sign(
        self,
        task: str | Any,
        **options: Any,
    ) -> TaskSignature:
        """Create a task signature for later execution."""
        return await sign(task, **options)

    async def chain(
        self,
        tasks: list[TaskSignatureConvertible],
        name: str = None,
        error: TaskInputType = None,
        success: TaskInputType = None,
    ):
        """Create a chain of tasks that execute sequentially."""
        return await chain(tasks, name, error, success)

    async def swarm(
        self,
        tasks: list[TaskSignatureConvertible] = None,
        task_name: str = None,
        **kwargs,
    ):
        """Create a swarm of tasks that execute in parallel."""
        return await swarm(tasks, task_name, **kwargs)

    # Delegate other broker methods to the underlying broker
    def __getattr__(self, name: str) -> Any:
        """Delegate unknown attributes to the underlying broker."""
        return getattr(self._broker, name)

    async def startup(self) -> None:
        """Start the broker and initialize Mageflow."""
        from mageflow.startup import init_mageflow

        await self._broker.startup()
        await init_mageflow()

    async def shutdown(self) -> None:
        """Shutdown the broker and teardown Mageflow."""
        from mageflow.startup import teardown_mageflow

        await self._broker.shutdown()
        await teardown_mageflow()
