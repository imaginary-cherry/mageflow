import os
from enum import Enum


class BackendOptions(str, Enum):
    TESTCONTAINERS = "testcontainers"
    FAKE_REDIS = "fakeredis"


def _get_backend(config: dict | None = None) -> BackendOptions:
    """
    Return the configured Redis backend: 'testcontainers' (default) or 'fakeredis'.

    Checks MAGEFLOW_TESTING_BACKEND env var first, then falls back to provided config.
    """
    env_backend = os.environ.get("MAGEFLOW_TESTING_BACKEND")
    if not env_backend and config:
        env_backend = config.get("backend", "testcontainers")
    if not env_backend:
        env_backend = "testcontainers"
    if env_backend == "fakeredis":
        return BackendOptions.FAKE_REDIS
    return BackendOptions.TESTCONTAINERS
