"""Tests for stdin secret reading and dev fallback."""

import io
import json
import sys
from unittest.mock import patch, MagicMock

import pytest


def test_reads_json_from_stdin():
    """Mock sys.stdin with piped JSON line, verify secrets dict returned."""
    from visualizer.__main__ import read_stdin_secrets

    payload = {"secrets": {"redisUrl": "redis://prod:6379", "hatchetApiKey": "key123"}, "ipc_token": "tok-abc"}
    fake_stdin = io.StringIO(json.dumps(payload) + "\n")
    fake_stdin.isatty = lambda: False

    with patch("sys.stdin", fake_stdin):
        result = read_stdin_secrets()

    assert result["secrets"]["redisUrl"] == "redis://prod:6379"
    assert result["secrets"]["hatchetApiKey"] == "key123"


def test_extracts_token():
    """Mock sys.stdin with JSON containing ipc_token, verify token extracted."""
    from visualizer.__main__ import read_stdin_secrets

    payload = {"secrets": {"redisUrl": "redis://localhost:6379", "hatchetApiKey": ""}, "ipc_token": "my-token-42"}
    fake_stdin = io.StringIO(json.dumps(payload) + "\n")
    fake_stdin.isatty = lambda: False

    with patch("sys.stdin", fake_stdin):
        result = read_stdin_secrets()

    assert result["ipc_token"] == "my-token-42"


def test_blocks_until_secrets():
    """Verify readline() is called (blocks until newline received)."""
    from visualizer.__main__ import read_stdin_secrets

    payload = {"secrets": {"redisUrl": "redis://localhost:6379", "hatchetApiKey": ""}, "ipc_token": "t"}
    mock_stdin = MagicMock()
    mock_stdin.isatty.return_value = False
    mock_stdin.readline.return_value = json.dumps(payload) + "\n"

    with patch("sys.stdin", mock_stdin):
        read_stdin_secrets()

    mock_stdin.readline.assert_called_once()


def test_dev_fallback_on_tty(monkeypatch):
    """Mock sys.stdin.isatty() returning True, verify env vars used."""
    from visualizer.__main__ import read_stdin_secrets

    monkeypatch.setenv("REDIS_URL", "redis://dev:6379")
    monkeypatch.setenv("HATCHET_API_KEY", "dev-key")

    mock_stdin = MagicMock()
    mock_stdin.isatty.return_value = True

    with patch("sys.stdin", mock_stdin):
        result = read_stdin_secrets()

    assert result["secrets"]["redisUrl"] == "redis://dev:6379"
    assert result["secrets"]["hatchetApiKey"] == "dev-key"


def test_dev_fallback_token_is_none(monkeypatch):
    """In TTY mode, ipc_token must be None."""
    from visualizer.__main__ import read_stdin_secrets

    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    monkeypatch.setenv("HATCHET_API_KEY", "")

    mock_stdin = MagicMock()
    mock_stdin.isatty.return_value = True

    with patch("sys.stdin", mock_stdin):
        result = read_stdin_secrets()

    assert result["ipc_token"] is None


def test_raises_on_empty_stdin():
    """When readline() returns empty string, raise RuntimeError."""
    from visualizer.__main__ import read_stdin_secrets

    mock_stdin = MagicMock()
    mock_stdin.isatty.return_value = False
    mock_stdin.readline.return_value = ""

    with patch("sys.stdin", mock_stdin):
        with pytest.raises(RuntimeError, match="No secrets received on stdin"):
            read_stdin_secrets()
