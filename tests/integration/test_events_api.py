from tests.integration.conftest import auth_header

# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #


def _create_venue(client, token, name="Test Venue"):
    payload = {
        "name": name,
        "address": "123 Main St",
        "city": "Springfield",
        "capacity": 5000,
    }
    return client.post("/venues", json=payload, headers=auth_header(token)).json()


def _event_payload(venue_id, **overrides):
    data = {
        "title": "Test Event",
        "venue_id": venue_id,
        "starts_at": "2027-01-15T10:00:00+00:00",
        "ends_at": "2027-01-15T14:00:00+00:00",
    }
    data.update(overrides)
    return data


# ------------------------------------------------------------------ #
# 1. Public list – empty DB
# ------------------------------------------------------------------ #


def test_public_list_empty(app_client):
    resp = app_client.get("/events/public")
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["offset"] == 0
    assert data["limit"] > 0


# ------------------------------------------------------------------ #
# 2. Admin creates an event → 201
# ------------------------------------------------------------------ #


def test_create_event_returns_201(app_client, admin_token):
    headers = auth_header(admin_token)
    venue = _create_venue(app_client, admin_token)

    payload = _event_payload(venue["id"], title="Rock Festival", status="published")
    resp = app_client.post("/events", json=payload, headers=headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == "Rock Festival"
    assert body["venue_id"] == venue["id"]
    assert body["status"] == "published"
    assert body["starts_at"].startswith("2027-01-15")
    assert body["ends_at"].startswith("2027-01-15")
    assert "id" in body
    assert body["created_by"] > 0
    assert body["venue"]["id"] == venue["id"]
    assert body["venue"]["name"] == "Test Venue"
    assert body["venue"]["city"] == "Springfield"
    assert isinstance(body["creator"], dict)
    assert body["creator"]["id"] == body["created_by"]
    assert "full_name" in body["creator"]


# ------------------------------------------------------------------ #
# 3. Customer cannot create an event → 403
# ------------------------------------------------------------------ #


def test_create_event_rejects_customer(app_client, customer_token, admin_token):
    venue = _create_venue(app_client, admin_token)
    payload = _event_payload(venue["id"])
    resp = app_client.post("/events", json=payload, headers=auth_header(customer_token))
    assert resp.status_code == 403


# ------------------------------------------------------------------ #
# 4. Invalid times (ends_at before starts_at) → 422
# ------------------------------------------------------------------ #


def test_create_event_invalid_times(app_client, admin_token):
    venue = _create_venue(app_client, admin_token)
    payload = _event_payload(
        venue["id"],
        starts_at="2027-01-15T14:00:00+00:00",
        ends_at="2027-01-15T10:00:00+00:00",
    )
    resp = app_client.post("/events", json=payload, headers=auth_header(admin_token))
    assert resp.status_code == 422


# ------------------------------------------------------------------ #
# 5. Non-existent venue_id → 404
# ------------------------------------------------------------------ #


def test_create_event_nonexistent_venue(app_client, admin_token):
    payload = _event_payload(9999)
    resp = app_client.post("/events", json=payload, headers=auth_header(admin_token))
    assert resp.status_code == 404


# ------------------------------------------------------------------ #
# 6. Draft events hidden from public list
# ------------------------------------------------------------------ #


def test_draft_hidden_from_public(app_client, admin_token):
    venue = _create_venue(app_client, admin_token)
    payload = _event_payload(venue["id"], title="Secret Draft", status="draft")
    app_client.post("/events", json=payload, headers=auth_header(admin_token))

    resp = app_client.get("/events/public")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []


# ------------------------------------------------------------------ #
# 7. Published events visible in public list
# ------------------------------------------------------------------ #


def test_published_visible_in_public(app_client, admin_token):
    venue = _create_venue(app_client, admin_token)
    payload = _event_payload(venue["id"], title="Public Concert", status="published")
    app_client.post("/events", json=payload, headers=auth_header(admin_token))

    resp = app_client.get("/events/public")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["title"] == "Public Concert"
    assert data["items"][0]["status"] == "published"


# ------------------------------------------------------------------ #
# 8. Public get draft event → 404
# ------------------------------------------------------------------ #


def test_public_get_draft_returns_404(app_client, admin_token):
    venue = _create_venue(app_client, admin_token)
    payload = _event_payload(venue["id"], title="Hidden Draft", status="draft")
    created = app_client.post(
        "/events", json=payload, headers=auth_header(admin_token)
    ).json()
    draft_id = created["id"]

    resp = app_client.get(f"/events/public/{draft_id}")
    assert resp.status_code == 404


# ------------------------------------------------------------------ #
# 9. Admin list includes drafts and published
# ------------------------------------------------------------------ #


def test_admin_list_includes_drafts(app_client, admin_token):
    headers = auth_header(admin_token)
    venue = _create_venue(app_client, admin_token)

    app_client.post(
        "/events",
        json=_event_payload(venue["id"], title="Draft Event", status="draft"),
        headers=headers,
    )
    app_client.post(
        "/events",
        json=_event_payload(venue["id"], title="Published Event", status="published"),
        headers=headers,
    )

    resp = app_client.get("/events", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


# ------------------------------------------------------------------ #
# 10. Admin list filter by status
# ------------------------------------------------------------------ #


def test_admin_list_filter_by_status(app_client, admin_token):
    headers = auth_header(admin_token)
    venue = _create_venue(app_client, admin_token)

    app_client.post(
        "/events",
        json=_event_payload(venue["id"], title="Draft Only", status="draft"),
        headers=headers,
    )
    app_client.post(
        "/events",
        json=_event_payload(venue["id"], title="Published Only", status="published"),
        headers=headers,
    )

    resp = app_client.get("/events", params={"status": "draft"}, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["status"] == "draft"
    assert data["items"][0]["title"] == "Draft Only"


# ------------------------------------------------------------------ #
# 11. Admin get draft event → 200
# ------------------------------------------------------------------ #


def test_admin_get_draft(app_client, admin_token):
    headers = auth_header(admin_token)
    venue = _create_venue(app_client, admin_token)
    payload = _event_payload(venue["id"], title="Admin Draft", status="draft")
    created = app_client.post("/events", json=payload, headers=headers).json()
    draft_id = created["id"]

    resp = app_client.get(f"/events/{draft_id}", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == draft_id
    assert body["status"] == "draft"
    assert body["title"] == "Admin Draft"


# ------------------------------------------------------------------ #
# 12. Update event (PATCH)
# ------------------------------------------------------------------ #


def test_update_event(app_client, admin_token):
    headers = auth_header(admin_token)
    venue = _create_venue(app_client, admin_token)
    payload = _event_payload(venue["id"], title="Original Title")
    created = app_client.post("/events", json=payload, headers=headers).json()
    event_id = created["id"]

    patch = {"title": "Updated Title"}
    resp = app_client.patch(f"/events/{event_id}", json=patch, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == event_id
    assert body["title"] == "Updated Title"
    assert body["venue_id"] == venue["id"]


# ------------------------------------------------------------------ #
# 13. Delete event → 204, then 404
# ------------------------------------------------------------------ #


def test_delete_event(app_client, admin_token):
    headers = auth_header(admin_token)
    venue = _create_venue(app_client, admin_token)
    payload = _event_payload(venue["id"], title="Doomed Event")
    created = app_client.post("/events", json=payload, headers=headers).json()
    event_id = created["id"]

    resp = app_client.delete(f"/events/{event_id}", headers=headers)
    assert resp.status_code == 204

    resp = app_client.get(f"/events/{event_id}", headers=headers)
    assert resp.status_code == 404


# ------------------------------------------------------------------ #
# 14. Search events by title
# ------------------------------------------------------------------ #


def test_search_events(app_client, admin_token):
    headers = auth_header(admin_token)
    venue = _create_venue(app_client, admin_token)

    app_client.post(
        "/events",
        json=_event_payload(venue["id"], title="Rock Festival", status="published"),
        headers=headers,
    )
    app_client.post(
        "/events",
        json=_event_payload(venue["id"], title="Jazz Night", status="published"),
        headers=headers,
    )

    resp = app_client.get("/events", params={"search": "Rock"}, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "Rock Festival"

    resp = app_client.get("/events", params={"search": "Jazz"}, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "Jazz Night"

    resp = app_client.get(
        "/events", params={"search": "nonexistent_xyz"}, headers=headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []
