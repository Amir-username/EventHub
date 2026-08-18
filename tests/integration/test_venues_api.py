from tests.integration.conftest import auth_header

# ------------------------------------------------------------------ #
# 1. Public list – empty DB
# ------------------------------------------------------------------ #


def test_public_list_returns_empty(app_client):
    resp = app_client.get("/venues/public")
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["offset"] == 0
    assert data["limit"] > 0


# ------------------------------------------------------------------ #
# 2. Admin creates a venue → 201
# ------------------------------------------------------------------ #


def test_create_venue_returns_201(app_client, admin_token):
    payload = {
        "name": "Grand Arena",
        "address": "123 Main St",
        "city": "Springfield",
        "capacity": 5000,
    }
    resp = app_client.post("/venues", json=payload, headers=auth_header(admin_token))
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Grand Arena"
    assert body["address"] == "123 Main St"
    assert body["city"] == "Springfield"
    assert body["capacity"] == 5000
    assert body["created_by"] > 0
    assert "id" in body
    assert isinstance(body["creator"], dict)
    assert body["creator"]["id"] == body["created_by"]
    assert "full_name" in body["creator"]


# ------------------------------------------------------------------ #
# 3. Customer cannot create a venue → 403
# ------------------------------------------------------------------ #


def test_create_venue_rejects_customer(app_client, customer_token):
    payload = {
        "name": "Denied Hall",
        "address": "456 Blocked Ave",
        "city": "Nowhere",
        "capacity": 100,
    }
    resp = app_client.post("/venues", json=payload, headers=auth_header(customer_token))
    assert resp.status_code == 403


# ------------------------------------------------------------------ #
# 4. No auth → 401
# ------------------------------------------------------------------ #


def test_create_venue_without_auth(app_client):
    payload = {
        "name": "No Auth Venue",
        "address": "789 Anonymous Blvd",
        "city": "Ghost Town",
        "capacity": 200,
    }
    resp = app_client.post("/venues", json=payload)
    assert resp.status_code == 401


# ------------------------------------------------------------------ #
# 5. Public list after creating one venue → total=1
# ------------------------------------------------------------------ #


def test_public_list_after_create(app_client, admin_token):
    payload = {
        "name": "Listed Venue",
        "address": "10 Public Sq",
        "city": "Metropolis",
        "capacity": 300,
    }
    app_client.post("/venues", json=payload, headers=auth_header(admin_token))

    resp = app_client.get("/venues/public")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["name"] == "Listed Venue"


# ------------------------------------------------------------------ #
# 6. Public get by ID
# ------------------------------------------------------------------ #


def test_public_get_by_id(app_client, admin_token):
    payload = {
        "name": "Findable Venue",
        "address": "77 Search St",
        "city": "Searchville",
        "capacity": 800,
    }
    created = app_client.post(
        "/venues", json=payload, headers=auth_header(admin_token)
    ).json()
    venue_id = created["id"]

    resp = app_client.get(f"/venues/public/{venue_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == venue_id
    assert body["name"] == "Findable Venue"
    assert body["city"] == "Searchville"
    assert body["capacity"] == 800


# ------------------------------------------------------------------ #
# 7. Public get non-existent → 404
# ------------------------------------------------------------------ #


def test_public_get_nonexistent(app_client):
    resp = app_client.get("/venues/public/99999")
    assert resp.status_code == 404
    assert "detail" in resp.json()


# ------------------------------------------------------------------ #
# 8. Admin list – two venues
# ------------------------------------------------------------------ #


def test_admin_list(app_client, admin_token):
    headers = auth_header(admin_token)
    for i in range(2):
        payload = {
            "name": f"Admin Venue {i}",
            "address": f"{i} Admin Rd",
            "city": "Capital City",
            "capacity": 100 + i * 50,
        }
        app_client.post("/venues", json=payload, headers=headers)

    resp = app_client.get("/venues", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


# ------------------------------------------------------------------ #
# 9. Customer cannot access admin list → 403
# ------------------------------------------------------------------ #


def test_admin_list_rejects_customer(app_client, customer_token):
    resp = app_client.get("/venues", headers=auth_header(customer_token))
    assert resp.status_code == 403


# ------------------------------------------------------------------ #
# 10. Admin get by ID
# ------------------------------------------------------------------ #


def test_admin_get_by_id(app_client, admin_token):
    headers = auth_header(admin_token)
    payload = {
        "name": "Admin Detail Venue",
        "address": "42 Detail Lane",
        "city": "Detailburg",
        "capacity": 1200,
    }
    created = app_client.post("/venues", json=payload, headers=headers).json()
    venue_id = created["id"]

    resp = app_client.get(f"/venues/{venue_id}", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == venue_id
    assert body["name"] == "Admin Detail Venue"
    assert body["address"] == "42 Detail Lane"
    assert body["city"] == "Detailburg"
    assert body["capacity"] == 1200


# ------------------------------------------------------------------ #
# 11. Update venue (PATCH)
# ------------------------------------------------------------------ #


def test_update_venue(app_client, admin_token):
    headers = auth_header(admin_token)
    payload = {
        "name": "Original Name",
        "address": "1 Update Ave",
        "city": "Updateville",
        "capacity": 400,
    }
    created = app_client.post("/venues", json=payload, headers=headers).json()
    venue_id = created["id"]

    patch = {"name": "Renamed Arena"}
    resp = app_client.patch(f"/venues/{venue_id}", json=patch, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == venue_id
    assert body["name"] == "Renamed Arena"
    # unchanged fields remain
    assert body["address"] == "1 Update Ave"
    assert body["city"] == "Updateville"
    assert body["capacity"] == 400


# ------------------------------------------------------------------ #
# 12. Delete venue → 204, then 404
# ------------------------------------------------------------------ #


def test_delete_venue(app_client, admin_token):
    headers = auth_header(admin_token)
    payload = {
        "name": "Doomed Venue",
        "address": "99 End Rd",
        "city": "Oblivion",
        "capacity": 50,
    }
    created = app_client.post("/venues", json=payload, headers=headers).json()
    venue_id = created["id"]

    resp = app_client.delete(f"/venues/{venue_id}", headers=headers)
    assert resp.status_code == 204

    # confirm gone via admin endpoint
    resp = app_client.get(f"/venues/{venue_id}", headers=headers)
    assert resp.status_code == 404

    # confirm gone via public endpoint
    resp = app_client.get(f"/venues/public/{venue_id}")
    assert resp.status_code == 404


# ------------------------------------------------------------------ #
# 13. Search venues by name substring
# ------------------------------------------------------------------ #


def test_search_venues(app_client, admin_token):
    headers = auth_header(admin_token)
    venues = [
        {
            "name": "Alpha Concert Hall",
            "address": "1 Alpha St",
            "city": "A City",
            "capacity": 500,
        },
        {
            "name": "Beta Convention Center",
            "address": "2 Beta St",
            "city": "B City",
            "capacity": 1000,
        },
    ]
    for v in venues:
        app_client.post("/venues", json=v, headers=headers)

    # search for "Concert"
    resp = app_client.get("/venues/public", params={"search": "Concert"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["name"] == "Alpha Concert Hall"

    # search for "Convention"
    resp = app_client.get("/venues/public", params={"search": "Convention"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["name"] == "Beta Convention Center"

    # search for partial match "Center" should match Beta
    resp = app_client.get("/venues/public", params={"search": "Center"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["name"] == "Beta Convention Center"

    # search with no matches
    resp = app_client.get("/venues/public", params={"search": "zzz_nonexistent"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []
