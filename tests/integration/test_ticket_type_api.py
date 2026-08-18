from tests.integration.conftest import auth_header

# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #


def _create_venue(client, admin_token):
    r = client.post(
        "/venues",
        json={"name": "TV", "address": "123 St", "city": "Tehran", "capacity": 100},
        headers=auth_header(admin_token),
    )
    return r.json()["id"]


def _create_published_event(client, admin_token, venue_id):
    payload = {
        "title": "Test Event",
        "venue_id": venue_id,
        "starts_at": "2027-06-01T10:00:00+00:00",
        "ends_at": "2027-06-01T12:00:00+00:00",
        "status": "published",
    }
    r = client.post("/events", json=payload, headers=auth_header(admin_token))
    return r.json()["id"]


def _create_draft_event(client, admin_token, venue_id):
    payload = {
        "title": "Draft Event",
        "venue_id": venue_id,
        "starts_at": "2027-06-01T10:00:00+00:00",
        "ends_at": "2027-06-01T12:00:00+00:00",
        "status": "draft",
    }
    r = client.post("/events", json=payload, headers=auth_header(admin_token))
    return r.json()["id"]


def _ticket_type_payload(event_id, **overrides):
    data = {
        "event_id": event_id,
        "name": "VIP",
        "price_cents": 5000,
        "currency": "IRR",
        "total_quantity": 100,
        "sales_start_at": "2027-01-01T00:00:00+00:00",
        "sales_end_at": "2027-05-31T23:59:59+00:00",
    }
    data.update(overrides)
    return data


# ------------------------------------------------------------------ #
# 1. Admin creates ticket type → 201, all fields correct
# ------------------------------------------------------------------ #


def test_create_ticket_type_returns_201(app_client, admin_token):
    headers = auth_header(admin_token)
    venue_id = _create_venue(app_client, admin_token)
    event_id = _create_published_event(app_client, admin_token, venue_id)

    payload = _ticket_type_payload(event_id)
    resp = app_client.post("/ticket-types", json=payload, headers=headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body["event_id"] == event_id
    assert body["name"] == "VIP"
    assert body["price_cents"] == 5000
    assert body["currency"] == "IRR"
    assert body["total_quantity"] == 100
    assert body["reserved_quantity"] == 0
    assert body["sold_quantity"] == 0
    assert body["sales_start_at"].startswith("2027-01-01")
    assert body["sales_end_at"].startswith("2027-05-31")
    assert "id" in body
    assert body["event"]["id"] == event_id
    assert body["event"]["title"] == "Test Event"
    assert body["event"]["status"] == "published"


# ------------------------------------------------------------------ #
# 2. Customer cannot create ticket type → 403
# ------------------------------------------------------------------ #


def test_create_ticket_type_rejects_customer(app_client, customer_token, admin_token):
    headers = auth_header(customer_token)
    venue_id = _create_venue(app_client, admin_token)
    event_id = _create_published_event(app_client, admin_token, venue_id)

    payload = _ticket_type_payload(event_id)
    resp = app_client.post("/ticket-types", json=payload, headers=headers)
    assert resp.status_code == 403


# ------------------------------------------------------------------ #
# 3. Invalid sales window (end before start) → 422
# ------------------------------------------------------------------ #


def test_create_ticket_type_invalid_sales_window(app_client, admin_token):
    headers = auth_header(admin_token)
    venue_id = _create_venue(app_client, admin_token)
    event_id = _create_published_event(app_client, admin_token, venue_id)

    payload = _ticket_type_payload(
        event_id,
        sales_start_at="2027-06-01T00:00:00+00:00",
        sales_end_at="2027-01-01T00:00:00+00:00",
    )
    resp = app_client.post("/ticket-types", json=payload, headers=headers)
    assert resp.status_code == 422


# ------------------------------------------------------------------ #
# 4. Non-existent event_id → 404
# ------------------------------------------------------------------ #


def test_create_ticket_type_nonexistent_event(app_client, admin_token):
    headers = auth_header(admin_token)

    payload = _ticket_type_payload(9999)
    resp = app_client.post("/ticket-types", json=payload, headers=headers)
    assert resp.status_code == 404


# ------------------------------------------------------------------ #
# 5. Public list by published event → 200, total=1
# ------------------------------------------------------------------ #


def test_public_list_by_event(app_client, admin_token):
    headers = auth_header(admin_token)
    venue_id = _create_venue(app_client, admin_token)
    event_id = _create_published_event(app_client, admin_token, venue_id)

    payload = _ticket_type_payload(event_id)
    app_client.post("/ticket-types", json=payload, headers=headers)

    resp = app_client.get(f"/ticket-types/public/events/{event_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["name"] == "VIP"
    assert data["offset"] == 0
    assert data["limit"] > 0


# ------------------------------------------------------------------ #
# 6. Public list rejects draft event → 404
# ------------------------------------------------------------------ #


def test_public_list_rejects_draft_event(app_client, admin_token):
    headers = auth_header(admin_token)
    venue_id = _create_venue(app_client, admin_token)
    draft_event_id = _create_draft_event(app_client, admin_token, venue_id)

    payload = _ticket_type_payload(draft_event_id)
    app_client.post("/ticket-types", json=payload, headers=headers)

    resp = app_client.get(f"/ticket-types/public/events/{draft_event_id}")
    assert resp.status_code == 404


# ------------------------------------------------------------------ #
# 7. Public get single ticket type (published event) → 200
# ------------------------------------------------------------------ #


def test_public_get_ticket_type(app_client, admin_token):
    headers = auth_header(admin_token)
    venue_id = _create_venue(app_client, admin_token)
    event_id = _create_published_event(app_client, admin_token, venue_id)

    payload = _ticket_type_payload(event_id, name="General")
    created = app_client.post("/ticket-types", json=payload, headers=headers).json()
    tt_id = created["id"]

    resp = app_client.get(f"/ticket-types/public/{tt_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == tt_id
    assert body["name"] == "General"
    assert body["price_cents"] == 5000
    assert body["event"]["id"] == event_id
    assert body["event"]["status"] == "published"


# ------------------------------------------------------------------ #
# 8. Public get ticket type for draft event → 404
# ------------------------------------------------------------------ #


def test_public_get_draft_event_ticket_type_404(app_client, admin_token):
    headers = auth_header(admin_token)
    venue_id = _create_venue(app_client, admin_token)
    draft_event_id = _create_draft_event(app_client, admin_token, venue_id)

    payload = _ticket_type_payload(draft_event_id, name="Draft TT")
    created = app_client.post("/ticket-types", json=payload, headers=headers).json()
    tt_id = created["id"]

    resp = app_client.get(f"/ticket-types/public/{tt_id}")
    assert resp.status_code == 404


# ------------------------------------------------------------------ #
# 9. Admin list all → 200, total=2
# ------------------------------------------------------------------ #


def test_admin_list_all(app_client, admin_token):
    headers = auth_header(admin_token)
    venue_id = _create_venue(app_client, admin_token)
    event_id = _create_published_event(app_client, admin_token, venue_id)

    app_client.post(
        "/ticket-types",
        json=_ticket_type_payload(event_id, name="VIP"),
        headers=headers,
    )
    app_client.post(
        "/ticket-types",
        json=_ticket_type_payload(event_id, name="Standard"),
        headers=headers,
    )

    resp = app_client.get("/ticket-types", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2
    names = {item["name"] for item in data["items"]}
    assert names == {"VIP", "Standard"}


# ------------------------------------------------------------------ #
# 10. Admin list filter by event_id
# ------------------------------------------------------------------ #


def test_admin_list_filter_by_event(app_client, admin_token):
    headers = auth_header(admin_token)
    venue_id = _create_venue(app_client, admin_token)
    event_id_1 = _create_published_event(app_client, admin_token, venue_id)
    event_id_2 = _create_published_event(app_client, admin_token, venue_id)

    app_client.post(
        "/ticket-types",
        json=_ticket_type_payload(event_id_1, name="Event1-TT"),
        headers=headers,
    )
    app_client.post(
        "/ticket-types",
        json=_ticket_type_payload(event_id_2, name="Event2-TT"),
        headers=headers,
    )

    resp = app_client.get(
        "/ticket-types", params={"event_id": event_id_1}, headers=headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["name"] == "Event1-TT"
    assert data["items"][0]["event_id"] == event_id_1


# ------------------------------------------------------------------ #
# 11. Update ticket type (PATCH name) → 200
# ------------------------------------------------------------------ #


def test_update_ticket_type(app_client, admin_token):
    headers = auth_header(admin_token)
    venue_id = _create_venue(app_client, admin_token)
    event_id = _create_published_event(app_client, admin_token, venue_id)

    created = app_client.post(
        "/ticket-types",
        json=_ticket_type_payload(event_id, name="Original"),
        headers=headers,
    ).json()
    tt_id = created["id"]

    resp = app_client.patch(
        f"/ticket-types/{tt_id}", json={"name": "Updated"}, headers=headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == tt_id
    assert body["name"] == "Updated"
    assert body["event_id"] == event_id
    assert body["price_cents"] == 5000


# ------------------------------------------------------------------ #
# 12. Delete ticket type → 204, then GET → 404
# ------------------------------------------------------------------ #


def test_delete_ticket_type(app_client, admin_token):
    headers = auth_header(admin_token)
    venue_id = _create_venue(app_client, admin_token)
    event_id = _create_published_event(app_client, admin_token, venue_id)

    created = app_client.post(
        "/ticket-types",
        json=_ticket_type_payload(event_id),
        headers=headers,
    ).json()
    tt_id = created["id"]

    resp = app_client.delete(f"/ticket-types/{tt_id}", headers=headers)
    assert resp.status_code == 204

    resp = app_client.get(f"/ticket-types/{tt_id}", headers=headers)
    assert resp.status_code == 404
