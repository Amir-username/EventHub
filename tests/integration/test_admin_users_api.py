"""Integration tests for /admin/users routes against a real PostgreSQL testcontainer."""

from tests.integration.conftest import auth_header

# ── List users ───────────────────────────────────────────────────────


def test_list_users_returns_users(app_client, admin_token):
    """GET /admin/users returns all users with pagination metadata."""
    headers = auth_header(admin_token)

    # Create two users via the admin endpoint
    app_client.post(
        "/admin/users",
        headers=headers,
        json={"email": "user1@example.com", "password": "Pass1!xyz"},
    )
    app_client.post(
        "/admin/users",
        headers=headers,
        json={"email": "user2@example.com", "password": "Pass1!xyz"},
    )

    resp = app_client.get("/admin/users", headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    # 2 created + 1 fixture admin = 3
    assert body["total"] == 3
    assert body["offset"] == 0
    assert body["limit"] == 20
    assert len(body["items"]) == 3


def test_list_users_filter_by_role(app_client, admin_token):
    """GET /admin/users?role=customer returns only customer users."""
    headers = auth_header(admin_token)

    app_client.post(
        "/admin/users",
        headers=headers,
        json={"email": "cust_filter@example.com", "password": "Pass1!xyz"},
    )
    app_client.post(
        "/admin/users",
        headers=headers,
        json={
            "email": "adm_filter@example.com",
            "password": "Pass1!xyz",
            "role": "admin",
        },
    )

    resp = app_client.get("/admin/users", headers=headers, params={"role": "customer"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["email"] == "cust_filter@example.com"
    assert body["items"][0]["role"] == "customer"


def test_list_users_search_by_email(app_client, admin_token):
    """GET /admin/users?search=<substring> filters by email."""
    headers = auth_header(admin_token)

    app_client.post(
        "/admin/users",
        headers=headers,
        json={"email": "searchable_target@example.com", "password": "Pass1!xyz"},
    )
    app_client.post(
        "/admin/users",
        headers=headers,
        json={"email": "other_unrelated@example.com", "password": "Pass1!xyz"},
    )

    resp = app_client.get(
        "/admin/users", headers=headers, params={"search": "searchable"}
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["email"] == "searchable_target@example.com"


# ── Get user by ID ───────────────────────────────────────────────────


def test_get_user_by_id(app_client, admin_token):
    """GET /admin/users/{id} returns the correct user."""
    headers = auth_header(admin_token)

    create_resp = app_client.post(
        "/admin/users",
        headers=headers,
        json={
            "email": "getme@example.com",
            "password": "Pass1!xyz",
            "full_name": "Get Me User",
        },
    )
    user_id = create_resp.json()["id"]

    resp = app_client.get(f"/admin/users/{user_id}", headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == user_id
    assert body["email"] == "getme@example.com"
    assert body["full_name"] == "Get Me User"
    assert body["role"] == "customer"
    assert "created_at" in body


def test_get_nonexistent_user(app_client, admin_token):
    """GET /admin/users/9999 returns 404 when user does not exist."""
    headers = auth_header(admin_token)

    resp = app_client.get("/admin/users/9999", headers=headers)

    assert resp.status_code == 404
    assert "detail" in resp.json()


# ── Create user ──────────────────────────────────────────────────────


def test_create_user_returns_201(app_client, admin_token):
    """POST /admin/users creates a new user and returns 201 with defaults."""
    headers = auth_header(admin_token)

    resp = app_client.post(
        "/admin/users",
        headers=headers,
        json={
            "email": "new_admin_user@example.com",
            "password": "StrongPass1!",
            "full_name": "Brand New User",
        },
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "new_admin_user@example.com"
    assert body["full_name"] == "Brand New User"
    assert body["role"] == "customer"
    assert "id" in body
    assert "created_at" in body


def test_create_user_duplicate_email_returns_409(app_client, admin_token):
    """POST /admin/users with an existing email returns 409 Conflict."""
    headers = auth_header(admin_token)
    payload = {"email": "dup_admin@example.com", "password": "Pass1!xyz"}

    first = app_client.post("/admin/users", headers=headers, json=payload)
    assert first.status_code == 201

    second = app_client.post("/admin/users", headers=headers, json=payload)
    assert second.status_code == 409
    assert "detail" in second.json()


# ── Update user ──────────────────────────────────────────────────────


def test_update_user_email(app_client, admin_token):
    """PATCH /admin/users/{id} with a new email updates the user."""
    headers = auth_header(admin_token)

    create_resp = app_client.post(
        "/admin/users",
        headers=headers,
        json={"email": "change_me@example.com", "password": "Pass1!xyz"},
    )
    user_id = create_resp.json()["id"]

    resp = app_client.patch(
        f"/admin/users/{user_id}",
        headers=headers,
        json={"email": "changed@example.com"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == "changed@example.com"
    assert body["id"] == user_id


def test_update_user_password(app_client, admin_token):
    """PATCH /admin/users/{id} with a new password returns 200."""
    headers = auth_header(admin_token)

    create_resp = app_client.post(
        "/admin/users",
        headers=headers,
        json={"email": "pwuser@example.com", "password": "OldPass1!"},
    )
    user_id = create_resp.json()["id"]

    resp = app_client.patch(
        f"/admin/users/{user_id}",
        headers=headers,
        json={"password": "NewPass1!"},
    )

    assert resp.status_code == 200
    assert resp.json()["id"] == user_id


def test_update_user_role(app_client, admin_token):
    """PATCH /admin/users/{id} changes the user role to admin."""
    headers = auth_header(admin_token)

    create_resp = app_client.post(
        "/admin/users",
        headers=headers,
        json={"email": "promote_me@example.com", "password": "Pass1!xyz"},
    )
    user_id = create_resp.json()["id"]
    assert create_resp.json()["role"] == "customer"

    resp = app_client.patch(
        f"/admin/users/{user_id}",
        headers=headers,
        json={"role": "admin"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["role"] == "admin"
    assert body["id"] == user_id


# ── Delete user ──────────────────────────────────────────────────────


def test_delete_user(app_client, admin_token):
    """DELETE /admin/users/{id} removes the user; subsequent GET returns 404."""
    headers = auth_header(admin_token)

    create_resp = app_client.post(
        "/admin/users",
        headers=headers,
        json={"email": "doomed@example.com", "password": "Pass1!xyz"},
    )
    user_id = create_resp.json()["id"]

    del_resp = app_client.delete(f"/admin/users/{user_id}", headers=headers)
    assert del_resp.status_code == 204

    get_resp = app_client.get(f"/admin/users/{user_id}", headers=headers)
    assert get_resp.status_code == 404


def test_self_delete(app_client, admin_token):
    """Deleting your own user returns 404 (service raises ValueError for self-delete)."""
    headers = auth_header(admin_token)

    # Retrieve the current admin's user ID via /auth/me
    me_resp = app_client.get("/auth/me", headers=headers)
    assert me_resp.status_code == 200
    admin_id = me_resp.json()["id"]

    resp = app_client.delete(f"/admin/users/{admin_id}", headers=headers)

    assert resp.status_code == 404
    assert "detail" in resp.json()


# ── Authorization ────────────────────────────────────────────────────


def test_customer_rejected(app_client, customer_token):
    """A customer-role token gets 403 on GET /admin/users."""
    headers = auth_header(customer_token)

    resp = app_client.get("/admin/users", headers=headers)

    assert resp.status_code == 403
