"""Unit tests for TicketTypeService business logic.

Tests CRUD, sales_end_at > sales_start_at validation, draft-event guard
on public reads, and cross-field validation on updates.
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import EventStatus
from app.schemas.ticket_type import TicketTypeCreate, TicketTypeUpdate
from app.services.ticket_type_service import TicketTypeService

# ── Create TicketType ───────────────────────────────────────────────


async def test_create_ticket_type_success(db_session: AsyncSession, event_factory):
    event = await event_factory(status=EventStatus.PUBLISHED)
    now = datetime.now(UTC)

    svc = TicketTypeService(db_session)
    tt = await svc.create_ticket_type(
        TicketTypeCreate(
            event_id=event.id,
            name="VIP",
            price_cents=15000,
            currency="USD",
            total_quantity=100,
            sales_start_at=now - timedelta(days=1),
            sales_end_at=now + timedelta(days=30),
        )
    )

    assert tt.id is not None
    assert tt.name == "VIP"
    assert tt.price_cents == 15000
    assert tt.currency == "USD"
    assert tt.total_quantity == 100
    assert tt.reserved_quantity == 0
    assert tt.sold_quantity == 0


async def test_create_ticket_type_rejects_sales_end_before_start(
    db_session: AsyncSession, event_factory
):
    event = await event_factory(status=EventStatus.PUBLISHED)
    now = datetime.now(UTC)

    svc = TicketTypeService(db_session)
    with pytest.raises(ValueError, match="sales_end_at must be after sales_start_at"):
        await svc.create_ticket_type(
            TicketTypeCreate(
                event_id=event.id,
                name="Bad",
                price_cents=5000,
                total_quantity=50,
                sales_start_at=now + timedelta(days=10),
                sales_end_at=now + timedelta(days=5),  # before start
            )
        )


async def test_create_ticket_type_rejects_equal_start_and_end(
    db_session: AsyncSession, event_factory
):
    """ends_at == starts_at should also be rejected (code uses <=)."""
    event = await event_factory(status=EventStatus.PUBLISHED)
    moment = datetime.now(UTC) + timedelta(days=5)

    svc = TicketTypeService(db_session)
    with pytest.raises(ValueError, match="sales_end_at must be after sales_start_at"):
        await svc.create_ticket_type(
            TicketTypeCreate(
                event_id=event.id,
                name="Bad",
                price_cents=5000,
                total_quantity=50,
                sales_start_at=moment,
                sales_end_at=moment,  # same instant
            )
        )


async def test_create_ticket_type_rejects_nonexistent_event(db_session: AsyncSession):
    now = datetime.now(UTC)

    svc = TicketTypeService(db_session)
    with pytest.raises(ValueError, match="Event not found"):
        await svc.create_ticket_type(
            TicketTypeCreate(
                event_id=9999,
                name="Orphan",
                price_cents=5000,
                total_quantity=50,
                sales_start_at=now - timedelta(days=1),
                sales_end_at=now + timedelta(days=30),
            )
        )


# ── Public Reads ────────────────────────────────────────────────────


async def test_get_public_ticket_type_success(
    db_session: AsyncSession, ticket_type_factory
):
    tt = await ticket_type_factory()

    svc = TicketTypeService(db_session)
    result = await svc.get_public(tt.id)

    assert result.id == tt.id
    assert result.name == tt.name


async def test_get_public_ticket_type_rejects_draft_event(
    db_session: AsyncSession, event_factory, ticket_type_factory
):
    draft_event = await event_factory(status=EventStatus.DRAFT)
    tt = await ticket_type_factory(event_id=draft_event.id)

    svc = TicketTypeService(db_session)
    with pytest.raises(ValueError, match="Ticket type not found"):
        await svc.get_public(tt.id)


async def test_get_public_ticket_type_rejects_nonexistent(db_session: AsyncSession):
    svc = TicketTypeService(db_session)
    with pytest.raises(ValueError, match="Ticket type not found"):
        await svc.get_public(9999)


async def test_list_public_by_event_success(
    db_session: AsyncSession, event_factory, ticket_type_factory
):
    event = await event_factory(status=EventStatus.PUBLISHED)
    await ticket_type_factory(event_id=event.id, name="VIP")
    await ticket_type_factory(event_id=event.id, name="General")

    svc = TicketTypeService(db_session)
    _items, total = await svc.list_public_by_event(event.id)

    assert total == 2


async def test_list_public_by_event_rejects_draft_event(
    db_session: AsyncSession, event_factory, ticket_type_factory
):
    draft = await event_factory(status=EventStatus.DRAFT)
    await ticket_type_factory(event_id=draft.id)

    svc = TicketTypeService(db_session)
    with pytest.raises(ValueError, match="Event not found"):
        await svc.list_public_by_event(draft.id)


async def test_list_public_by_event_rejects_nonexistent_event(db_session: AsyncSession):
    svc = TicketTypeService(db_session)
    with pytest.raises(ValueError, match="Event not found"):
        await svc.list_public_by_event(9999)


# ── Admin Reads ─────────────────────────────────────────────────────


async def test_get_ticket_type_success(db_session: AsyncSession, ticket_type_factory):
    tt = await ticket_type_factory()

    svc = TicketTypeService(db_session)
    result = await svc.get_ticket_type(tt.id)

    assert result.id == tt.id


async def test_get_ticket_type_rejects_nonexistent(db_session: AsyncSession):
    svc = TicketTypeService(db_session)
    with pytest.raises(ValueError, match="Ticket type not found"):
        await svc.get_ticket_type(9999)


async def test_list_all_ticket_types(db_session: AsyncSession, ticket_type_factory):
    await ticket_type_factory(name="A")
    await ticket_type_factory(name="B")

    svc = TicketTypeService(db_session)
    _items, total = await svc.list_all()

    assert total == 2


async def test_list_all_filter_by_event(
    db_session: AsyncSession, event_factory, ticket_type_factory
):
    event1 = await event_factory()
    event2 = await event_factory()
    await ticket_type_factory(event_id=event1.id, name="T1")
    await ticket_type_factory(event_id=event1.id, name="T2")
    await ticket_type_factory(event_id=event2.id, name="T3")

    svc = TicketTypeService(db_session)
    _items, total = await svc.list_all(event_id=event1.id)

    assert total == 2


# ── Update TicketType ───────────────────────────────────────────────


async def test_update_ticket_type_name(db_session: AsyncSession, ticket_type_factory):
    tt = await ticket_type_factory(name="Old")

    svc = TicketTypeService(db_session)
    updated = await svc.update_ticket_type(tt.id, TicketTypeUpdate(name="New"))

    assert updated.name == "New"
    assert updated.price_cents == tt.price_cents  # unchanged


async def test_update_ticket_type_rejects_nonexistent(db_session: AsyncSession):
    svc = TicketTypeService(db_session)
    with pytest.raises(ValueError, match="Ticket type not found"):
        await svc.update_ticket_type(9999, TicketTypeUpdate(name="X"))


async def test_update_ticket_type_cross_field_validation(
    db_session: AsyncSession, ticket_type_factory
):
    """Changing sales_end_at to before the existing sales_start_at should fail."""
    now = datetime.now(UTC)
    tt = await ticket_type_factory(
        sales_start_at=now + timedelta(days=5),
        sales_end_at=now + timedelta(days=10),
    )

    svc = TicketTypeService(db_session)
    with pytest.raises(ValueError, match="sales_end_at must be after sales_start_at"):
        await svc.update_ticket_type(
            tt.id,
            TicketTypeUpdate(sales_end_at=now + timedelta(days=2)),
        )


async def test_update_ticket_type_none_fields_ignored(
    db_session: AsyncSession, ticket_type_factory
):
    """Sending all-None update should not change anything."""
    tt = await ticket_type_factory(name="Stable", price_cents=7777)

    svc = TicketTypeService(db_session)
    updated = await svc.update_ticket_type(tt.id, TicketTypeUpdate())

    assert updated.name == "Stable"
    assert updated.price_cents == 7777


# ── Delete TicketType ───────────────────────────────────────────────


async def test_delete_ticket_type_success(
    db_session: AsyncSession, ticket_type_factory
):
    tt = await ticket_type_factory()

    svc = TicketTypeService(db_session)
    await svc.delete_ticket_type(tt.id)

    with pytest.raises(ValueError, match="Ticket type not found"):
        await svc.get_ticket_type(tt.id)


async def test_delete_ticket_type_rejects_nonexistent(db_session: AsyncSession):
    svc = TicketTypeService(db_session)
    with pytest.raises(ValueError, match="Ticket type not found"):
        await svc.delete_ticket_type(9999)
