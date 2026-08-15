"""Tests for custom middleware — tested in isolation (no full app)."""

import re

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from app.middleware.rate_limit import (
    InMemoryRateLimitBackend,
    RateLimitMiddleware,
)
from app.middleware.request_id import RequestIDMiddleware
from app.middleware.timing import TimingMiddleware

# ── Tiny Starlette app for middleware tests ──────────────────────────


async def _ok(request):
    return JSONResponse({"status": "ok"})


def _make_app(*middlewares):
    """Build a minimal Starlette app with the given middleware stack."""
    app = Starlette(routes=[Route("/ping", _ok)])
    for mw in middlewares:
        app.add_middleware(mw)
    return app


# ── RequestID Middleware ─────────────────────────────────────────────


def test_request_id_generated_when_not_provided():
    app = _make_app(RequestIDMiddleware)
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/ping")
    request_id = response.headers.get("X-Request-ID")
    assert request_id is not None
    assert re.match(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
        request_id,
    )


def test_request_id_echoes_client_header():
    app = _make_app(RequestIDMiddleware)
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/ping", headers={"X-Request-ID": "trace-abc-123"})
    assert response.headers["X-Request-ID"] == "trace-abc-123"


def test_request_id_different_per_request():
    app = _make_app(RequestIDMiddleware)
    client = TestClient(app, raise_server_exceptions=False)
    ids = set()
    for _ in range(10):
        response = client.get("/ping")
        ids.add(response.headers["X-Request-ID"])
    assert len(ids) == 10


# ── Timing Middleware ────────────────────────────────────────────────


def test_response_time_header_present():
    app = _make_app(TimingMiddleware)
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/ping")
    header = response.headers.get("X-Response-Time")
    assert header is not None
    assert header.endswith("ms")
    value = float(header.replace("ms", ""))
    assert value >= 0


# ── Rate Limit Middleware ────────────────────────────────────────────


def test_rate_limit_returns_429_after_threshold():
    """After max_requests, subsequent requests get 429 with Retry-After."""
    backend = InMemoryRateLimitBackend()
    app = Starlette(routes=[Route("/ping", _ok)])
    app.add_middleware(
        RateLimitMiddleware,
        backend=backend,
        max_requests=5,
        window_seconds=60,
        enabled=True,
    )
    client = TestClient(app, raise_server_exceptions=False)

    # First 5 should succeed
    for _ in range(5):
        response = client.get("/ping")
        assert response.status_code == 200

    # 6th should be rate limited
    response = client.get("/ping")
    assert response.status_code == 429
    assert response.headers["Retry-After"] == "60"
    assert response.json()["detail"] == "Rate limit exceeded. Try again later."


def test_rate_limit_disabled_passes_all_requests():
    """When disabled, no requests are blocked and no Retry-After header."""
    backend = InMemoryRateLimitBackend()
    app = Starlette(routes=[Route("/ping", _ok)])
    app.add_middleware(
        RateLimitMiddleware,
        backend=backend,
        max_requests=5,
        window_seconds=60,
        enabled=False,
    )
    client = TestClient(app, raise_server_exceptions=False)

    for _ in range(20):
        response = client.get("/ping")
        assert response.status_code == 200
        assert "Retry-After" not in response.headers
