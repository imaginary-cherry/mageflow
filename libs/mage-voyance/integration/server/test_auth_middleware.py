"""Tests for IPC token authentication middleware."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from visualizer.server import add_ipc_auth_middleware, register_api_routes


def _make_app(ipc_token: str | None) -> FastAPI:
    """Create a minimal FastAPI app with auth middleware and routes."""
    app = FastAPI()
    app.state.secrets = {"redisUrl": "redis://localhost:6379", "hatchetApiKey": ""}
    add_ipc_auth_middleware(app, ipc_token)
    register_api_routes(app)
    return app


def test_valid_token_passes():
    """Request with correct X-IPC-Token header gets 200."""
    app = _make_app("secret-token")
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/api/workflows", headers={"X-IPC-Token": "secret-token"})
    # May fail due to Redis not being available, but should NOT be 403
    assert resp.status_code != 403


def test_missing_token_returns_403():
    """Request without header gets 403."""
    app = _make_app("secret-token")
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/api/workflows")
    assert resp.status_code == 403


def test_invalid_token_returns_403():
    """Request with wrong token gets 403."""
    app = _make_app("secret-token")
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/api/workflows", headers={"X-IPC-Token": "wrong-token"})
    assert resp.status_code == 403


def test_health_endpoint_exempt():
    """GET /api/health without token gets 200 (not 403)."""
    app = _make_app("secret-token")
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/api/health")
    # Health should not return 403 even without token
    assert resp.status_code != 403


def test_no_middleware_when_token_none():
    """When ipc_token is None (dev mode), all requests pass without token."""
    app = _make_app(None)
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/api/workflows")
    # Should NOT be 403 in dev mode
    assert resp.status_code != 403
