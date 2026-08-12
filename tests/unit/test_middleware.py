"""Tests for custom middleware — no database needed."""

from starlette.testclient import TestClient

from app.factory import create_app

# ── RequestID Middleware ─────────────────────────────────────────────


def test_request_id_generated_when_not_provided():
    app = create_app()
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/events/")
    request_id = response.headers.get("X-Request-ID")
    assert request_id is not None
    # UUID4 format
    import re

    assert re.match(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
        request_id,
    )


def test_request_id_echoes_client_header():
    app = create_app()
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/events/", headers={"X-Request-ID": "trace-abc-123"})
    assert response.headers["X-Request-ID"] == "trace-abc-123"


def test_request_id_different_per_request():
    app = create_app()
    client = TestClient(app, raise_server_exceptions=False)
    ids = set()
    for _ in range(10):
        response = client.get("/events/")
        ids.add(response.headers["X-Request-ID"])
    assert len(ids) == 10


# ── Timing Middleware ────────────────────────────────────────────────


def test_response_time_header_present():
    app = create_app()
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/events/")
    header = response.headers.get("X-Response-Time")
    assert header is not None
    assert header.endswith("ms")
    value = float(header.replace("ms", ""))
    assert value >= 0


# ── Rate Limit Middleware ────────────────────────────────────────────


# def test_rate_limit_429_after_threshold():
#     """Send many requests to trigger rate limit."""
#     app = create_app()
#     client = TestClient(app, raise_server_exceptions=False)
#
#     status_codes = []
#     for _ in range(110):
#         response = client.get("/events/")
#         status_codes.append(response.status_code)
#
#     # At least one 429 should appear
#     assert 429 in status_codes
#
#
# def test_rate_limit_includes_retry_after():
#     app = create_app()
#     client = TestClient(app, raise_server_exceptions=False)
#
#     # Bypass rate limit by disabling it
#     from app.config import Settings
#
#     app_no_limit = create_app(Settings(rate_limit_enabled=False))
#     client_no_limit = TestClient(app_no_limit, raise_server_exceptions=False)
#
#     for _ in range(110):
#         response = client_no_limit.get("/events/")
#         assert response.status_code == 200
#     assert "Retry-After" not in response.headers
