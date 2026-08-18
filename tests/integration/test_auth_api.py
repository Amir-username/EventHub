"""Integration tests for /auth routes against a real PostgreSQL testcontainer."""

from tests.integration.conftest import auth_header

# ── Registration ─────────────────────────────────────────────────────


def test_register_success(app_client):
    """Valid registration returns 201 with user data, role=customer."""
    resp = app_client.post(
        "/auth/register",
        json={
            "email": "newuser@example.com",
            "password": "StrongPass1!",
            "confirm_pass": "StrongPass1!",
        },
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "newuser@example.com"
    assert body["role"] == "customer"
    assert "id" in body
    assert "created_at" in body


def test_register_duplicate_email_returns_409(app_client):
    """Registering the same email twice yields 409 Conflict."""
    payload = {
        "email": "dup@example.com",
        "password": "StrongPass1!",
        "confirm_pass": "StrongPass1!",
    }
    first = app_client.post("/auth/register", json=payload)
    assert first.status_code == 201

    second = app_client.post("/auth/register", json=payload)
    assert second.status_code == 409
    assert "detail" in second.json()


def test_register_password_mismatch_returns_422(app_client):
    """password != confirm_pass triggers 422 validation error."""
    resp = app_client.post(
        "/auth/register",
        json={
            "email": "mismatch@example.com",
            "password": "StrongPass1!",
            "confirm_pass": "Different2!",
        },
    )

    assert resp.status_code == 422


# ── Login ─────────────────────────────────────────────────────────────


def test_login_success(app_client):
    """Register then login — verify 200 with both tokens and token_type=bearer."""
    # Register first
    app_client.post(
        "/auth/register",
        json={
            "email": "loginuser@example.com",
            "password": "LoginPass1!",
            "confirm_pass": "LoginPass1!",
        },
    )

    resp = app_client.post(
        "/auth/login",
        json={"email": "loginuser@example.com", "password": "LoginPass1!"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["token_type"] == "bearer"


def test_login_wrong_password_returns_401(app_client):
    """Login with a wrong password returns 401."""
    app_client.post(
        "/auth/register",
        json={
            "email": "wrongpass@example.com",
            "password": "CorrectPass1!",
            "confirm_pass": "CorrectPass1!",
        },
    )

    resp = app_client.post(
        "/auth/login",
        json={"email": "wrongpass@example.com", "password": "WrongPass1!"},
    )

    assert resp.status_code == 401


def test_login_nonexistent_email_returns_401(app_client):
    """Login with an email that was never registered returns 401."""
    resp = app_client.post(
        "/auth/login",
        json={"email": "ghost@example.com", "password": "DoesntMatter1!"},
    )

    assert resp.status_code == 401


# ── OAuth2 token endpoint ─────────────────────────────────────────────


def test_token_endpoint_returns_token_pair(app_client):
    """OAuth2 form-based /auth/token returns a TokenPair."""
    app_client.post(
        "/auth/register",
        json={
            "email": "oauthuser@example.com",
            "password": "OAuthPass1!",
            "confirm_pass": "OAuthPass1!",
        },
    )

    resp = app_client.post(
        "/auth/token",
        data={"username": "oauthuser@example.com", "password": "OAuthPass1!"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["token_type"] == "bearer"


# ── Refresh ───────────────────────────────────────────────────────────


def test_refresh_returns_new_tokens(app_client):
    """A valid refresh token yields a fresh TokenPair."""
    # Register and login to obtain tokens
    app_client.post(
        "/auth/register",
        json={
            "email": "refreshuser@example.com",
            "password": "RefreshPass1!",
            "confirm_pass": "RefreshPass1!",
        },
    )
    login_resp = app_client.post(
        "/auth/login",
        json={"email": "refreshuser@example.com", "password": "RefreshPass1!"},
    )
    refresh_tok = login_resp.json()["refresh_token"]
    original_access = login_resp.json()["access_token"]

    resp = app_client.post(f"/auth/refresh?refresh_token={refresh_tok}")

    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["token_type"] == "bearer"
    # The new access token should differ from the original
    assert body["access_token"] != original_access


def test_refresh_rejects_access_token(app_client):
    """Passing an access token to /auth/refresh returns 401."""
    app_client.post(
        "/auth/register",
        json={
            "email": "refreshbad@example.com",
            "password": "RefreshBad1!",
            "confirm_pass": "RefreshBad1!",
        },
    )
    login_resp = app_client.post(
        "/auth/login",
        json={"email": "refreshbad@example.com", "password": "RefreshBad1!"},
    )
    access_tok = login_resp.json()["access_token"]

    resp = app_client.post(f"/auth/refresh?refresh_token={access_tok}")

    assert resp.status_code == 401


# ── Current user (/auth/me) ───────────────────────────────────────────


def test_me_returns_current_user(app_client):
    """GET /auth/me with a valid Bearer token returns the user's profile."""
    app_client.post(
        "/auth/register",
        json={
            "email": "meuser@example.com",
            "password": "MePass1!",
            "confirm_pass": "MePass1!",
            "full_name": "Me User",
        },
    )
    login_resp = app_client.post(
        "/auth/login",
        json={"email": "meuser@example.com", "password": "MePass1!"},
    )
    token = login_resp.json()["access_token"]

    resp = app_client.get("/auth/me", headers=auth_header(token))

    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == "meuser@example.com"
    assert body["full_name"] == "Me User"
    assert body["role"] == "customer"
    assert "id" in body


def test_me_without_token_returns_401(app_client):
    """GET /auth/me with no Authorization header returns 401."""
    resp = app_client.get("/auth/me")

    assert resp.status_code == 401


def test_me_with_invalid_token_returns_401(app_client):
    """GET /auth/me with a garbage token returns 401."""
    resp = app_client.get("/auth/me", headers=auth_header("this.is.not.a.real.token"))

    assert resp.status_code == 401
