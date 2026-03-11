import importlib
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]

import pytest


def _find_pyproject(rootdir: Path) -> Path | None:
    candidate = rootdir / "pyproject.toml"
    if candidate.exists():
        return candidate
    fallback = Path.cwd() / "pyproject.toml"
    if fallback.exists():
        return fallback
    return None


def _read_testing_config(rootdir: Path) -> dict:
    path = _find_pyproject(rootdir)
    if path is None:
        return {}
    with open(path, "rb") as f:
        data = tomllib.load(f)
    return data.get("tool", {}).get("mageflow", {}).get("testing", {})


def _load_client(dotted_path: str):
    try:
        if ":" in dotted_path:
            module_path, attr = dotted_path.rsplit(":", 1)
        else:
            module_path, _, attr = dotted_path.rpartition(".")
        module = importlib.import_module(module_path)
        return getattr(module, attr)
    except (ImportError, AttributeError) as e:
        raise pytest.UsageError(
            f"Could not load mageflow client from '{dotted_path}': {e}"
        )
