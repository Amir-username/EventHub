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


def _create_ticket_type(client, admin_token, event_id, **overrides):
    data = {
        "event_id": event_id,
        "name": "VIP",
        "price_cents": 5000,
        "currency": "IRR",
        "total_quantity": 100,
        "sales_start_at": "2027-01-01T00:00:00+00:00",
        "sales_end_at": "2027-12-31T23:59:59+00:00",
    }
    data.update(overrides)
    r = client.post("/ticket-types", json=data, headers=auth_header(admin_token))
    return r.json()


def _create_reservation(
    client, token, ticket_type_id, *, quantity=2, idempotency_key=None
):
    payload = {
        "ticket_type_id": ticket_type_id,
        "quantity": quantity,
        "idempotency_key": idempotency_key or f"idem-{ticket_type_id}-{quantity}",
    }
    return client.post("/reservations", json=payload, headers=auth_header(token))


def _setup_event_and_ticket_type(client, admin_token, total_quantity=100):
    venue_id = _create_venue(client, admin_token)
    event_id = _create_published_event(client, admin_token, venue_id)
    tt = _create_ticket_type(
        client, admin_token, event_id, total_quantity=total_quantity
    )
    return event_id, tt["id"]


# ------------------------------------------------------------------ #
# 1. Customer creates reservation → 201, all fields correct
# ------------------------------------------------------------------ #


def test_create_reservation_returns_201(app_client, admin_token, customer_token):
    _, tt_id = _setup_event_and_ticket_type(app_client, admin_token)

    resp = _create_reservation(
        app_client, customer_token, tt_id, idempotency_key="req-1"
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["user_id"] > 0
    assert body["ticket_type_id"] == tt_id
    assert body["quantity"] == 2
    assert body["status"] == "pending"
    assert body["idempotency_key"] == "req-1"
    assert body["expires_at"] is not None
    assert body["created_at"] is not None
    assert body["ticket_type"]["id"] == tt_id
    assert body["ticket_type"]["name"] == "VIP"
    assert body["ticket_type"]["price_cents"] == 5000
    assert body["ticket_type"]["event"]["id"] > 0


# ------------------------------------------------------------------ #
# 2. Idempotency: same key returns existing reservation → 201
# ------------------------------------------------------------------ #


def test_create_reservation_idempotent(app_client, admin_token, customer_token):
    _, tt_id = _setup_event_and_ticket_type(app_client, admin_token, total_quantity=100)

    key = "idem-dup-1"
    resp1 = _create_reservation(
        app_client, customer_token, tt_id, quantity=3, idempotency_key=key
    )
    resp2 = _create_reservation(
        app_client, customer_token, tt_id, quantity=3, idempotency_key=key
    )

    assert resp1.status_code == 201
    assert resp2.status_code == 201
    assert resp1.json()["id"] == resp2.json()["id"]


# ------------------------------------------------------------------ #
# 3. Idempotency key used on expired reservation → 409
# ------------------------------------------------------------------ #


def test_create_reservation_reuses_idempotency_of_terminal_state_409(
    app_client, admin_token, customer_token
):
    _, tt_id = _setup_event_and_ticket_type(app_client, admin_token, total_quantity=100)

    # Create and cancel
    key = "idem-terminal-1"
    created = _create_reservation(
        app_client, customer_token, tt_id, quantity=1, idempotency_key=key
    ).json()
    res_id = created["id"]
    app_client.post(
        f"/reservations/mine/{res_id}/cancel", headers=auth_header(customer_token)
    )

    # Reuse the key
    resp = _create_reservation(
        app_client, customer_token, tt_id, quantity=1, idempotency_key=key
    )
    assert resp.status_code == 409


# ------------------------------------------------------------------ #
# 4. Sold-out: not enough tickets → 422
# ------------------------------------------------------------------ #


def test_create_reservation_sold_out(app_client, admin_token, customer_token):
    _, tt_id = _setup_event_and_ticket_type(app_client, admin_token, total_quantity=5)

    resp = _create_reservation(
        app_client, customer_token, tt_id, quantity=10, idempotency_key="req-soldout"
    )
    assert resp.status_code == 422
    assert "not enough" in resp.json()["detail"].lower()


# ------------------------------------------------------------------ #
# 5. Non-existent ticket type → 404
# ------------------------------------------------------------------ #


def test_create_reservation_nonexistent_ticket_type(app_client, customer_token):
    resp = _create_reservation(
        app_client, customer_token, 99999, idempotency_key="req-ghost"
    )
    assert resp.status_code == 404


# ------------------------------------------------------------------ #
# 6. Sales not started → 422
# ------------------------------------------------------------------ #


def test_create_reservation_sales_not_started(app_client, admin_token, customer_token):
    venue_id = _create_venue(app_client, admin_token)
    event_id = _create_published_event(app_client, admin_token, venue_id)
    tt = _create_ticket_type(
        app_client,
        admin_token,
        event_id,
        sales_start_at="2028-01-01T00:00:00+00:00",
        sales_end_at="2028-12-31T23:59:59+00:00",
    )

    resp = _create_reservation(
        app_client, customer_token, tt["id"], idempotency_key="req-future"
    )
    assert resp.status_code == 422
    assert "sales have not started" in resp.json()["detail"].lower()


# ------------------------------------------------------------------ #
# 7. Sales ended → 422
# ------------------------------------------------------------------ #


def test_create_reservation_sales_ended(app_client, admin_token, customer_token):
    venue_id = _create_venue(app_client, admin_token)
    event_id = _create_published_event(app_client, admin_token, venue_id)
    tt = _create_ticket_type(
        app_client,
        admin_token,
        event_id,
        sales_start_at="2020-01-01T00:00:00+00:00",
        sales_end_at="2020-12-31T23:59:59+00:00",
    )

    resp = _create_reservation(
        app_client, customer_token, tt["id"], idempotency_key="req-past"
    )
    assert resp.status_code == 422
    assert "sales have ended" in resp.json()["detail"].lower()


# ------------------------------------------------------------------ #
# 8. Unauthenticated → 401
# ------------------------------------------------------------------ #


def test_create_reservation_unauthenticated(app_client, admin_token):
    _, tt_id = _setup_event_and_ticket_type(app_client, admin_token)

    payload = {
        "ticket_type_id": tt_id,
        "quantity": 1,
        "idempotency_key": "req-noauth",
    }
    resp = app_client.post("/reservations", json=payload)
    assert resp.status_code == 401


# ------------------------------------------------------------------ #
# 9. Invalid payload (quantity=0) → 422 (Pydantic)
# ------------------------------------------------------------------ #


def test_create_reservation_invalid_quantity(app_client, customer_token):
    payload = {
        "ticket_type_id": 1,
        "quantity": 0,
        "idempotency_key": "req-zero",
    }
    resp = app_client.post(
        "/reservations", json=payload, headers=auth_header(customer_token)
    )
    assert resp.status_code == 422


# ------------------------------------------------------------------ #
# 10. Customer lists own reservations → 200
# ------------------------------------------------------------------ #


def test_list_my_reservations(app_client, admin_token, customer_token):
    _, tt_id = _setup_event_and_ticket_type(app_client, admin_token, total_quantity=100)

    _create_reservation(app_client, customer_token, tt_id, idempotency_key="req-mine-1")
    _create_reservation(app_client, customer_token, tt_id, idempotency_key="req-mine-2")

    resp = app_client.get("/reservations/mine", headers=auth_header(customer_token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert len(body["items"]) == 2
    assert body["offset"] == 0
    assert body["limit"] == 20
    # Should have ticket_type nested but NOT user
    for item in body["items"]:
        assert "ticket_type" in item
        assert "user" not in item


# ------------------------------------------------------------------ #
# 11. List mine with status filter
# ------------------------------------------------------------------ #


def test_list_my_reservations_filter_by_status(app_client, admin_token, customer_token):
    _, tt_id = _setup_event_and_ticket_type(app_client, admin_token, total_quantity=100)

    r1 = _create_reservation(
        app_client, customer_token, tt_id, idempotency_key="req-filter-1"
    ).json()
    # Cancel one
    app_client.post(
        f"/reservations/mine/{r1['id']}/cancel", headers=auth_header(customer_token)
    )
    _create_reservation(
        app_client, customer_token, tt_id, idempotency_key="req-filter-2"
    )

    resp = app_client.get(
        "/reservations/mine",
        params={"status_filter": "pending"},
        headers=auth_header(customer_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["status"] == "pending"


# ------------------------------------------------------------------ #
# 12. Customer gets own single reservation → 200
# ------------------------------------------------------------------ #


def test_get_my_reservation(app_client, admin_token, customer_token):
    _, tt_id = _setup_event_and_ticket_type(app_client, admin_token, total_quantity=100)

    created = _create_reservation(
        app_client, customer_token, tt_id, idempotency_key="req-get-1"
    ).json()
    res_id = created["id"]

    resp = app_client.get(
        f"/reservations/mine/{res_id}", headers=auth_header(customer_token)
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == res_id
    assert body["ticket_type"]["id"] == tt_id


# ------------------------------------------------------------------ #
# 13. Customer cannot see another user's reservation → 404
# ------------------------------------------------------------------ #


def test_get_my_reservation_wrong_user_404(app_client, admin_token, customer_token):
    _, tt_id = _setup_event_and_ticket_type(app_client, admin_token, total_quantity=100)

    created = _create_reservation(
        app_client, customer_token, tt_id, idempotency_key="req-own-1"
    ).json()
    res_id = created["id"]

    # Create a second customer
    import asyncio
    from datetime import UTC, datetime

    from sqlalchemy import insert

    from app.core.security import create_access_token, hash_password
    from app.models.user import User, UserRole

    async def _make_user():

        from app.config import get_settings

        # Need the real pg_url — use the app's overridden setting
        settings = get_settings()
        from sqlalchemy.ext.asyncio import create_async_engine

        engine = create_async_engine(settings.database_url, echo=False)
        async with engine.begin() as conn:
            hashed = hash_password("OtherPass1!")
            result = await conn.execute(
                insert(User)
                .values(
                    email="other@integration.test",
                    hashed_password=hashed,
                    full_name="Other Customer",
                    role=UserRole.CUSTOMER,
                    created_at=datetime.now(UTC),
                )
                .returning(User.id)
            )
            uid = result.scalar_one()
        await engine.dispose()
        return create_access_token(
            data={
                "sub": str(uid),
                "email": "other@integration.test",
                "role": "customer",
            }
        )

    other_token = asyncio.run(_make_user())

    resp = app_client.get(
        f"/reservations/mine/{res_id}", headers=auth_header(other_token)
    )
    assert resp.status_code == 404


# ------------------------------------------------------------------ #
# 14. Customer cancels own pending reservation → 200
# ------------------------------------------------------------------ #


def test_cancel_my_reservation(app_client, admin_token, customer_token):
    _, tt_id = _setup_event_and_ticket_type(app_client, admin_token, total_quantity=100)

    created = _create_reservation(
        app_client, customer_token, tt_id, quantity=5, idempotency_key="req-cancel-1"
    ).json()
    res_id = created["id"]

    resp = app_client.post(
        f"/reservations/mine/{res_id}/cancel", headers=auth_header(customer_token)
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == res_id
    assert body["status"] == "cancelled"


# ------------------------------------------------------------------ #
# 15. Cancel already cancelled reservation → 422
# ------------------------------------------------------------------ #


def test_cancel_already_cancelled_422(app_client, admin_token, customer_token):
    _, tt_id = _setup_event_and_ticket_type(app_client, admin_token, total_quantity=100)

    created = _create_reservation(
        app_client, customer_token, tt_id, idempotency_key="req-dblcancel"
    ).json()
    res_id = created["id"]

    app_client.post(
        f"/reservations/mine/{res_id}/cancel", headers=auth_header(customer_token)
    )

    resp = app_client.post(
        f"/reservations/mine/{res_id}/cancel", headers=auth_header(customer_token)
    )
    assert resp.status_code == 422


# ------------------------------------------------------------------ #
# 16. Cancel non-existent reservation → 404
# ------------------------------------------------------------------ #


def test_cancel_nonexistent_404(app_client, customer_token):
    resp = app_client.post(
        "/reservations/mine/99999/cancel", headers=auth_header(customer_token)
    )
    assert resp.status_code == 404


# ------------------------------------------------------------------ #
# 17. Admin lists all reservations → 200, includes user info
# ------------------------------------------------------------------ #


def test_admin_list_all_reservations(app_client, admin_token, customer_token):
    _, tt_id = _setup_event_and_ticket_type(app_client, admin_token, total_quantity=100)

    _create_reservation(
        app_client, customer_token, tt_id, idempotency_key="req-admin-1"
    )
    _create_reservation(
        app_client, customer_token, tt_id, idempotency_key="req-admin-2"
    )

    resp = app_client.get("/reservations", headers=auth_header(admin_token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert len(body["items"]) == 2
    # Admin response includes user info
    for item in body["items"]:
        assert "user" in item
        assert item["user"]["email"] == "customer@integration.test"


# ------------------------------------------------------------------ #
# 18. Admin lists with status filter
# ------------------------------------------------------------------ #


def test_admin_list_filter_by_status(app_client, admin_token, customer_token):
    _, tt_id = _setup_event_and_ticket_type(app_client, admin_token, total_quantity=100)

    r1 = _create_reservation(
        app_client, customer_token, tt_id, idempotency_key="req-af-1"
    ).json()
    app_client.post(
        f"/reservations/mine/{r1['id']}/cancel", headers=auth_header(customer_token)
    )
    _create_reservation(app_client, customer_token, tt_id, idempotency_key="req-af-2")

    resp = app_client.get(
        "/reservations",
        params={"status_filter": "cancelled"},
        headers=auth_header(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["status"] == "cancelled"


# ------------------------------------------------------------------ #
# 19. Admin lists with ticket_type_id filter
# ------------------------------------------------------------------ #


def test_admin_list_filter_by_ticket_type(app_client, admin_token, customer_token):
    venue_id = _create_venue(app_client, admin_token)
    event_id = _create_published_event(app_client, admin_token, venue_id)
    tt1 = _create_ticket_type(
        app_client, admin_token, event_id, name="VIP", total_quantity=100
    )
    tt2 = _create_ticket_type(
        app_client, admin_token, event_id, name="Standard", total_quantity=100
    )

    _create_reservation(
        app_client, customer_token, tt1["id"], idempotency_key="req-tt1"
    )
    _create_reservation(
        app_client, customer_token, tt2["id"], idempotency_key="req-tt2"
    )

    resp = app_client.get(
        "/reservations",
        params={"ticket_type_id": tt1["id"]},
        headers=auth_header(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["ticket_type"]["name"] == "VIP"


# ------------------------------------------------------------------ #
# 20. Customer cannot access admin list → 403
# ------------------------------------------------------------------ #


def test_admin_list_rejects_customer(app_client, customer_token):
    resp = app_client.get("/reservations", headers=auth_header(customer_token))
    assert resp.status_code == 403


# ------------------------------------------------------------------ #
# 21. Admin gets single reservation → 200, includes user
# ------------------------------------------------------------------ #


def test_admin_get_reservation(app_client, admin_token, customer_token):
    _, tt_id = _setup_event_and_ticket_type(app_client, admin_token, total_quantity=100)

    created = _create_reservation(
        app_client, customer_token, tt_id, idempotency_key="req-admin-get"
    ).json()
    res_id = created["id"]

    resp = app_client.get(f"/reservations/{res_id}", headers=auth_header(admin_token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == res_id
    assert "user" in body
    assert body["user"]["email"] == "customer@integration.test"


# ------------------------------------------------------------------ #
# 22. Admin get non-existent → 404
# ------------------------------------------------------------------ #


def test_admin_get_nonexistent_404(app_client, admin_token):
    resp = app_client.get("/reservations/99999", headers=auth_header(admin_token))
    assert resp.status_code == 404


# ------------------------------------------------------------------ #
# 23. Admin confirms pending reservation → 200
# ------------------------------------------------------------------ #


def test_admin_confirm_reservation(app_client, admin_token, customer_token):
    _, tt_id = _setup_event_and_ticket_type(app_client, admin_token, total_quantity=100)

    created = _create_reservation(
        app_client, customer_token, tt_id, quantity=3, idempotency_key="req-confirm-1"
    ).json()
    res_id = created["id"]

    resp = app_client.post(
        f"/reservations/{res_id}/confirm", headers=auth_header(admin_token)
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == res_id
    assert body["status"] == "confirmed"
    assert "user" in body


# ------------------------------------------------------------------ #
# 24. Confirm already confirmed → 422
# ------------------------------------------------------------------ #


def test_admin_confirm_already_confirmed_422(app_client, admin_token, customer_token):
    _, tt_id = _setup_event_and_ticket_type(app_client, admin_token, total_quantity=100)

    created = _create_reservation(
        app_client, customer_token, tt_id, idempotency_key="req-dblconfirm"
    ).json()
    res_id = created["id"]

    app_client.post(f"/reservations/{res_id}/confirm", headers=auth_header(admin_token))

    resp = app_client.post(
        f"/reservations/{res_id}/confirm", headers=auth_header(admin_token)
    )
    assert resp.status_code == 422


# ------------------------------------------------------------------ #
# 25. Confirm non-existent → 404
# ------------------------------------------------------------------ #


def test_admin_confirm_nonexistent_404(app_client, admin_token):
    resp = app_client.post(
        "/reservations/99999/confirm", headers=auth_header(admin_token)
    )
    assert resp.status_code == 404


# ------------------------------------------------------------------ #
# 26. Counter consistency: reserved_quantity increases on create
# ------------------------------------------------------------------ #


def test_reserved_quantity_increases(app_client, admin_token, customer_token):
    _, tt_id = _setup_event_and_ticket_type(app_client, admin_token, total_quantity=100)

    # Check initial
    tt = app_client.get(f"/ticket-types/public/{tt_id}").json()
    assert tt["reserved_quantity"] == 0
    assert tt["sold_quantity"] == 0

    _create_reservation(
        app_client, customer_token, tt_id, quantity=7, idempotency_key="req-counter-1"
    )

    tt = app_client.get(f"/ticket-types/public/{tt_id}").json()
    assert tt["reserved_quantity"] == 7
    assert tt["sold_quantity"] == 0


# ------------------------------------------------------------------ #
# 27. Counter consistency: reserved decreases, sold increases on confirm
# ------------------------------------------------------------------ #


def test_counters_on_confirm(app_client, admin_token, customer_token):
    _, tt_id = _setup_event_and_ticket_type(app_client, admin_token, total_quantity=100)

    created = _create_reservation(
        app_client, customer_token, tt_id, quantity=4, idempotency_key="req-cnt-cfm"
    ).json()
    app_client.post(
        f"/reservations/{created['id']}/confirm", headers=auth_header(admin_token)
    )

    tt = app_client.get(f"/ticket-types/public/{tt_id}").json()
    assert tt["reserved_quantity"] == 0
    assert tt["sold_quantity"] == 4


# ------------------------------------------------------------------ #
# 28. Counter consistency: reserved decreases on cancel
# ------------------------------------------------------------------ #


def test_counters_on_cancel(app_client, admin_token, customer_token):
    _, tt_id = _setup_event_and_ticket_type(app_client, admin_token, total_quantity=100)

    created = _create_reservation(
        app_client, customer_token, tt_id, quantity=3, idempotency_key="req-cnt-can"
    ).json()
    app_client.post(
        f"/reservations/mine/{created['id']}/cancel",
        headers=auth_header(customer_token),
    )

    tt = app_client.get(f"/ticket-types/public/{tt_id}").json()
    assert tt["reserved_quantity"] == 0
    assert tt["sold_quantity"] == 0
