"""Unit tests for ReservationService business logic.

Tests service-level validation: quantity checks, ownership guards,
not-found errors, and listing/filtering delegation.

Repository-level concerns (locking, idempotency, counter atomics,
sale-window enforcement) are covered by integration tests against
real PostgreSQL.
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reservation import ReservationStatus
from app.services.reservation_service import ReservationService

# ── create_reservation ──────────────────────────────────────────────


async def test_create_reservation_success(
    db_session: AsyncSession, user_factory, ticket_type_factory
):
    user = await user_factory()
    tt = await ticket_type_factory(total_quantity=50)

    svc = ReservationService(db_session)
    reservation = await svc.create_reservation(
        user_id=user.id,
        ticket_type_id=tt.id,
        quantity=3,
        idempotency_key="unique-key-1",
    )

    assert reservation.id is not None
    assert reservation.user_id == user.id
    assert reservation.ticket_type_id == tt.id
    assert reservation.quantity == 3
    assert reservation.status == ReservationStatus.PENDING
    assert reservation.idempotency_key == "unique-key-1"
    assert reservation.expires_at > datetime.now(UTC)


async def test_create_reservation_rejects_zero_quantity(
    db_session: AsyncSession, user_factory, ticket_type_factory
):
    user = await user_factory()
    tt = await ticket_type_factory()

    svc = ReservationService(db_session)
    with pytest.raises(ValueError, match="Quantity must be at least 1"):
        await svc.create_reservation(
            user_id=user.id,
            ticket_type_id=tt.id,
            quantity=0,
            idempotency_key="key-zero",
        )


async def test_create_reservation_rejects_negative_quantity(
    db_session: AsyncSession, user_factory, ticket_type_factory
):
    user = await user_factory()
    tt = await ticket_type_factory()

    svc = ReservationService(db_session)
    with pytest.raises(ValueError, match="Quantity must be at least 1"):
        await svc.create_reservation(
            user_id=user.id,
            ticket_type_id=tt.id,
            quantity=-5,
            idempotency_key="key-neg",
        )


async def test_create_reservation_computes_expires_at(
    db_session: AsyncSession, user_factory, ticket_type_factory
):
    """expires_at should be approximately now + reservation_window_minutes."""
    user = await user_factory()
    tt = await ticket_type_factory()

    svc = ReservationService(db_session)
    before = datetime.now(UTC)
    reservation = await svc.create_reservation(
        user_id=user.id,
        ticket_type_id=tt.id,
        quantity=1,
        idempotency_key="key-expiry",
    )
    after = datetime.now(UTC)

    # Default window is 10 minutes
    expected_min = before + timedelta(minutes=10)
    expected_max = after + timedelta(minutes=10)
    assert expected_min <= reservation.expires_at <= expected_max


async def test_create_reservation_rejects_nonexistent_ticket_type(
    db_session: AsyncSession, user_factory
):
    user = await user_factory()

    svc = ReservationService(db_session)
    with pytest.raises(ValueError, match="Ticket type not found"):
        await svc.create_reservation(
            user_id=user.id,
            ticket_type_id=9999,
            quantity=1,
            idempotency_key="key-no-tt",
        )


async def test_create_reservation_rejects_sold_out(
    db_session: AsyncSession, user_factory, ticket_type_factory
):
    user = await user_factory()
    tt = await ticket_type_factory(total_quantity=5)

    svc = ReservationService(db_session)
    # Reserve all 5
    await svc.create_reservation(
        user_id=user.id,
        ticket_type_id=tt.id,
        quantity=5,
        idempotency_key="key-fill",
    )
    # 6th should fail
    with pytest.raises(ValueError, match="Not enough tickets available"):
        await svc.create_reservation(
            user_id=user.id,
            ticket_type_id=tt.id,
            quantity=1,
            idempotency_key="key-overflow",
        )


# ── get_reservation ─────────────────────────────────────────────────


async def test_get_reservation_success(
    db_session: AsyncSession, user_factory, ticket_type_factory
):
    user = await user_factory()
    tt = await ticket_type_factory()

    svc = ReservationService(db_session)
    created = await svc.create_reservation(
        user_id=user.id,
        ticket_type_id=tt.id,
        quantity=2,
        idempotency_key="key-get",
    )

    fetched = await svc.get_reservation(created.id)
    assert fetched.id == created.id
    assert fetched.status == ReservationStatus.PENDING


async def test_get_reservation_not_found(db_session: AsyncSession):
    svc = ReservationService(db_session)
    with pytest.raises(ValueError, match="Reservation not found"):
        await svc.get_reservation(9999)


# ── cancel_reservation ──────────────────────────────────────────────


async def test_cancel_reservation_success(
    db_session: AsyncSession, user_factory, ticket_type_factory
):
    user = await user_factory()
    tt = await ticket_type_factory(total_quantity=50)

    svc = ReservationService(db_session)
    reservation = await svc.create_reservation(
        user_id=user.id,
        ticket_type_id=tt.id,
        quantity=3,
        idempotency_key="key-cancel",
    )

    cancelled = await svc.cancel_reservation(reservation.id, user_id=user.id)
    assert cancelled.status == ReservationStatus.CANCELLED


async def test_cancel_reservation_not_found(db_session: AsyncSession):
    svc = ReservationService(db_session)
    with pytest.raises(ValueError, match="Reservation not found"):
        await svc.cancel_reservation(9999, user_id=1)


async def test_cancel_reservation_wrong_owner(
    db_session: AsyncSession, user_factory, ticket_type_factory
):
    owner = await user_factory(email="owner@test.com")
    other = await user_factory(email="other@test.com")
    tt = await ticket_type_factory(total_quantity=50)

    svc = ReservationService(db_session)
    reservation = await svc.create_reservation(
        user_id=owner.id,
        ticket_type_id=tt.id,
        quantity=1,
        idempotency_key="key-ownership",
    )

    with pytest.raises(ValueError, match="Not your reservation"):
        await svc.cancel_reservation(reservation.id, user_id=other.id)


async def test_cancel_reservation_non_pending_fails(
    db_session: AsyncSession, user_factory, ticket_type_factory
):
    """Cancelling an already-cancelled reservation should fail."""
    user = await user_factory()
    tt = await ticket_type_factory(total_quantity=50)

    svc = ReservationService(db_session)
    reservation = await svc.create_reservation(
        user_id=user.id,
        ticket_type_id=tt.id,
        quantity=1,
        idempotency_key="key-double-cancel",
    )
    # Cancel once — succeeds
    await svc.cancel_reservation(reservation.id, user_id=user.id)
    # Cancel again — should fail because status is now CANCELLED
    with pytest.raises(
        ValueError, match="Cannot cancel a reservation with status 'cancelled'"
    ):
        await svc.cancel_reservation(reservation.id, user_id=user.id)


# ── confirm_reservation ─────────────────────────────────────────────


async def test_confirm_reservation_success(
    db_session: AsyncSession, user_factory, ticket_type_factory
):
    user = await user_factory()
    tt = await ticket_type_factory(total_quantity=50)

    svc = ReservationService(db_session)
    reservation = await svc.create_reservation(
        user_id=user.id,
        ticket_type_id=tt.id,
        quantity=2,
        idempotency_key="key-confirm",
    )

    confirmed = await svc.confirm_reservation(reservation.id)
    assert confirmed.status == ReservationStatus.CONFIRMED


async def test_confirm_reservation_not_found(db_session: AsyncSession):
    svc = ReservationService(db_session)
    with pytest.raises(ValueError, match="Reservation not found"):
        await svc.confirm_reservation(9999)


async def test_confirm_reservation_non_pending_fails(
    db_session: AsyncSession, user_factory, ticket_type_factory
):
    user = await user_factory()
    tt = await ticket_type_factory(total_quantity=50)

    svc = ReservationService(db_session)
    reservation = await svc.create_reservation(
        user_id=user.id,
        ticket_type_id=tt.id,
        quantity=1,
        idempotency_key="key-confirm-cancelled",
    )
    await svc.cancel_reservation(reservation.id, user_id=user.id)

    with pytest.raises(
        ValueError, match="Cannot confirm a reservation with status 'cancelled'"
    ):
        await svc.confirm_reservation(reservation.id)


# ── expire_reservation ──────────────────────────────────────────────


async def test_expire_reservation_success(
    db_session: AsyncSession, user_factory, ticket_type_factory
):
    user = await user_factory()
    tt = await ticket_type_factory(total_quantity=50)

    svc = ReservationService(db_session)
    reservation = await svc.create_reservation(
        user_id=user.id,
        ticket_type_id=tt.id,
        quantity=1,
        idempotency_key="key-expire",
    )

    expired = await svc.expire_reservation(reservation.id)
    assert expired.status == ReservationStatus.EXPIRED


async def test_expire_reservation_not_found(db_session: AsyncSession):
    svc = ReservationService(db_session)
    with pytest.raises(ValueError, match="Reservation not found"):
        await svc.expire_reservation(9999)


async def test_expire_reservation_non_pending_is_noop(
    db_session: AsyncSession, user_factory, ticket_type_factory
):
    """Expiring an already-confirmed reservation should silently return it unchanged."""
    user = await user_factory()
    tt = await ticket_type_factory(total_quantity=50)

    svc = ReservationService(db_session)
    reservation = await svc.create_reservation(
        user_id=user.id,
        ticket_type_id=tt.id,
        quantity=1,
        idempotency_key="key-expire-confirmed",
    )
    await svc.confirm_reservation(reservation.id)

    # Should NOT raise — expire silently skips non-pending
    result = await svc.expire_reservation(reservation.id)
    assert result.status == ReservationStatus.CONFIRMED


# ── list_my_reservations ────────────────────────────────────────────


async def test_list_my_reservations_returns_own_only(
    db_session: AsyncSession, user_factory, ticket_type_factory
):
    user1 = await user_factory(email="user1@test.com")
    user2 = await user_factory(email="user2@test.com")
    tt = await ticket_type_factory(total_quantity=100)

    svc = ReservationService(db_session)
    await svc.create_reservation(
        user_id=user1.id,
        ticket_type_id=tt.id,
        quantity=1,
        idempotency_key="list-u1-a",
    )
    await svc.create_reservation(
        user_id=user1.id,
        ticket_type_id=tt.id,
        quantity=2,
        idempotency_key="list-u1-b",
    )
    await svc.create_reservation(
        user_id=user2.id,
        ticket_type_id=tt.id,
        quantity=1,
        idempotency_key="list-u2-a",
    )

    items, total = await svc.list_my_reservations(user_id=user1.id)
    assert total == 2
    assert all(r.user_id == user1.id for r in items)


async def test_list_my_reservations_filters_by_status(
    db_session: AsyncSession, user_factory, ticket_type_factory
):
    user = await user_factory()
    tt = await ticket_type_factory(total_quantity=100)

    svc = ReservationService(db_session)
    r1 = await svc.create_reservation(
        user_id=user.id,
        ticket_type_id=tt.id,
        quantity=1,
        idempotency_key="filter-pending",
    )
    r2 = await svc.create_reservation(
        user_id=user.id,
        ticket_type_id=tt.id,
        quantity=1,
        idempotency_key="filter-cancel",
    )
    await svc.cancel_reservation(r2.id, user_id=user.id)

    items, total = await svc.list_my_reservations(
        user_id=user.id,
        status=ReservationStatus.PENDING,
    )
    assert total == 1
    assert items[0].id == r1.id

    items_cancelled, total_c = await svc.list_my_reservations(
        user_id=user.id,
        status=ReservationStatus.CANCELLED,
    )
    assert total_c == 1
    assert items_cancelled[0].id == r2.id


# ── list_all_reservations ───────────────────────────────────────────


async def test_list_all_reservations_returns_all(
    db_session: AsyncSession, user_factory, ticket_type_factory
):
    u1 = await user_factory(email="la-user1@test.com")
    u2 = await user_factory(email="la-user2@test.com")
    tt = await ticket_type_factory(total_quantity=100)

    svc = ReservationService(db_session)
    await svc.create_reservation(
        user_id=u1.id,
        ticket_type_id=tt.id,
        quantity=1,
        idempotency_key="all-a",
    )
    await svc.create_reservation(
        user_id=u2.id,
        ticket_type_id=tt.id,
        quantity=2,
        idempotency_key="all-b",
    )

    _items, total = await svc.list_all_reservations()
    assert total == 2


async def test_list_all_filters_by_status(
    db_session: AsyncSession, user_factory, ticket_type_factory
):
    user = await user_factory()
    tt = await ticket_type_factory(total_quantity=100)

    svc = ReservationService(db_session)
    _r1 = await svc.create_reservation(
        user_id=user.id,
        ticket_type_id=tt.id,
        quantity=1,
        idempotency_key="all-status-p",
    )
    r2 = await svc.create_reservation(
        user_id=user.id,
        ticket_type_id=tt.id,
        quantity=1,
        idempotency_key="all-status-c",
    )
    await svc.cancel_reservation(r2.id, user_id=user.id)

    items, total = await svc.list_all_reservations(
        status=ReservationStatus.CANCELLED,
    )
    assert total == 1
    assert items[0].id == r2.id


async def test_list_all_filters_by_user_id(
    db_session: AsyncSession, user_factory, ticket_type_factory
):
    u1 = await user_factory(email="filter-u1@test.com")
    u2 = await user_factory(email="filter-u2@test.com")
    tt = await ticket_type_factory(total_quantity=100)

    svc = ReservationService(db_session)
    await svc.create_reservation(
        user_id=u1.id,
        ticket_type_id=tt.id,
        quantity=1,
        idempotency_key="all-user-a",
    )
    await svc.create_reservation(
        user_id=u2.id,
        ticket_type_id=tt.id,
        quantity=1,
        idempotency_key="all-user-b",
    )

    items, total = await svc.list_all_reservations(user_id=u1.id)
    assert total == 1
    assert items[0].user_id == u1.id


async def test_list_all_filters_by_ticket_type_id(
    db_session: AsyncSession, user_factory, ticket_type_factory
):
    user = await user_factory()
    tt1 = await ticket_type_factory(name="TypeA", total_quantity=100)
    tt2 = await ticket_type_factory(name="TypeB", total_quantity=100)

    svc = ReservationService(db_session)
    await svc.create_reservation(
        user_id=user.id,
        ticket_type_id=tt1.id,
        quantity=1,
        idempotency_key="all-tt-a",
    )
    await svc.create_reservation(
        user_id=user.id,
        ticket_type_id=tt2.id,
        quantity=1,
        idempotency_key="all-tt-b",
    )

    items, total = await svc.list_all_reservations(ticket_type_id=tt1.id)
    assert total == 1
    assert items[0].ticket_type_id == tt1.id
