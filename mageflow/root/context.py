from contextlib import contextmanager
from contextvars import ContextVar
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from mageflow.swarm.model import SwarmTaskSignature

current_root_swarm: ContextVar[Optional["SwarmTaskSignature"]] = ContextVar(
    "current_root_swarm", default=None
)


@contextmanager
def without_root_swarm():
    token = current_root_swarm.set(None)
    try:
        yield
    finally:
        current_root_swarm.reset(token)
