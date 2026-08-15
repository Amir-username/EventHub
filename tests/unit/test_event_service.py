"""Unit tests for EventService business logic.

Tests validation rules (ends_at > starts_at, venue existence, status parsing)
and CRUD operations through the service layer.
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import EventStatus
from app.models.user import UserRole
from app.schemas.event import EventCreate, EventUpdate
from app.services.event_service import EventService

# ── Create Event ─────────────────────────────────────────────────────


async def test_create_event_success(
    db_session: AsyncSession, user_factory, venue_factory
):
    admin = await user_factory(role=UserRole.ADMIN)
    venue = await venue_factory(created_by=admin.id)

    svc = EventService(db_session)
    starts = datetime.now(UTC) + timedelta(days=1)
    ends = starts + timedelta(hours=2)

    event = await svc.create_event(
        EventCreate(
            title="Test Concert",
            description="A great show",
            venue_id=venue.id,
            starts_at=starts,
            ends_at=ends,
            status="published",
        ),
        created_by=admin.id,
    )

    assert event.id is not None
    assert event.title == "Test Concert"
    assert event.status == EventStatus.PUBLISHED


async def test_create_event_rejects_ends_before_starts(
    db_session: AsyncSession, user_factory, venue_factory
):
    admin = await user_factory(role=UserRole.ADMIN)
    venue = await venue_factory(created_by=admin.id)

    svc = EventService(db_session)
    starts = datetime.now(UTC) + timedelta(days=1)
    ends = starts - timedelta(hours=1)  # INVALID

    with pytest.raises(ValueError, match="ends_at must be after starts_at"):
        await svc.create_event(
            EventCreate(
                title="Bad Event",
                description="Invalid times",
                venue_id=venue.id,
                starts_at=starts,
                ends_at=ends,
                status="draft",
            ),
            created_by=admin.id,
        )


async def test_create_event_rejects_nonexistent_venue(
    db_session: AsyncSession, user_factory
):
    admin = await user_factory(role=UserRole.ADMIN)

    svc = EventService(db_session)
    starts = datetime.now(UTC) + timedelta(days=1)
    ends = starts + timedelta(hours=2)

    with pytest.raises(ValueError, match="Venue not found"):
        await svc.create_event(
            EventCreate(
                title="No Venue",
                description="No venue attached",
                venue_id=9999,
                starts_at=starts,
                ends_at=ends,
                status="draft",
            ),
            created_by=admin.id,
        )


# ── Get Event ────────────────────────────────────────────────────────


async def test_get_public_event_success(db_session: AsyncSession, event_factory):
    event = await event_factory(status=EventStatus.PUBLISHED)

    svc = EventService(db_session)
    result = await svc.get_public(event.id)

    assert result.id == event.id
    assert result.title == event.title


async def test_get_public_event_rejects_draft(db_session: AsyncSession, event_factory):
    event = await event_factory(status=EventStatus.DRAFT)

    svc = EventService(db_session)
    with pytest.raises(ValueError, match="Event not found"):
        await svc.get_public(event.id)


async def test_get_public_event_rejects_nonexistent(db_session: AsyncSession):
    svc = EventService(db_session)
    with pytest.raises(ValueError, match="Event not found"):
        await svc.get_public(9999)


# ── Update Event ─────────────────────────────────────────────────────


async def test_update_event_title(db_session: AsyncSession, event_factory):
    event = await event_factory(title="Old Title")

    svc = EventService(db_session)
    updated = await svc.update_event(event.id, EventUpdate(title="New Title"))

    assert updated.title == "New Title"


async def test_update_event_rejects_invalid_status(
    db_session: AsyncSession, event_factory
):
    event = await event_factory()

    svc = EventService(db_session)
    with pytest.raises(ValueError, match="Invalid status"):
        await svc.update_event(event.id, EventUpdate(status="nonexistent_status"))


# ── Delete Event ─────────────────────────────────────────────────────


async def test_delete_event_success(db_session: AsyncSession, event_factory):
    event = await event_factory()

    svc = EventService(db_session)
    await svc.delete_event(event.id)

    # Verify it's gone
    with pytest.raises(ValueError, match="Event not found"):
        await svc.get_event(event.id)


async def test_delete_event_rejects_nonexistent(db_session: AsyncSession):
    svc = EventService(db_session)
    with pytest.raises(ValueError, match="Event not found"):
        await svc.delete_event(9999)


# ── List ─────────────────────────────────────────────────────────────


async def test_list_public_only_returns_published(
    db_session: AsyncSession, event_factory
):
    await event_factory(title="Published Event", status=EventStatus.PUBLISHED)
    await event_factory(title="Draft Event", status=EventStatus.DRAFT)

    svc = EventService(db_session)
    items, total = await svc.list_public()

    assert total == 1
    assert items[0].title == "Published Event"


async def test_list_all_includes_drafts_for_admin(
    db_session: AsyncSession, event_factory
):
    await event_factory(title="Published Event", status=EventStatus.PUBLISHED)
    await event_factory(title="Draft Event", status=EventStatus.DRAFT)

    svc = EventService(db_session)
    _items, total = await svc.list_all()

    assert total == 2


async def test_create_event_rejects_equal_starts_and_ends(
    db_session: AsyncSession, user_factory, venue_factory
):
    """ends_at == starts_at should also be rejected (code uses <=)."""
    admin = await user_factory(role=UserRole.ADMIN)
    venue = await venue_factory(created_by=admin.id)

    svc = EventService(db_session)
    moment = datetime.now(UTC) + timedelta(days=1)

    with pytest.raises(ValueError, match="ends_at must be after starts_at"):
        await svc.create_event(
            EventCreate(
                title="Same Time",
                venue_id=venue.id,
                starts_at=moment,
                ends_at=moment,
                status="draft",
            ),
            created_by=admin.id,
        )


async def test_create_event_default_status_is_draft(
    db_session: AsyncSession, user_factory, venue_factory
):
    """When status is not provided, it defaults to 'draft'."""
    admin = await user_factory(role=UserRole.ADMIN)
    venue = await venue_factory(created_by=admin.id)

    svc = EventService(db_session)
    starts = datetime.now(UTC) + timedelta(days=1)
    ends = starts + timedelta(hours=2)

    event = await svc.create_event(
        EventCreate(
            title="No Status",
            venue_id=venue.id,
            starts_at=starts,
            ends_at=ends,
            # status omitted — defaults to "draft"
        ),
        created_by=admin.id,
    )

    assert event.status == EventStatus.DRAFT


async def test_update_event_venue_to_nonexistent(
    db_session: AsyncSession, event_factory
):
    """Changing venue_id to a non-existent venue should fail."""
    event = await event_factory()

    svc = EventService(db_session)
    with pytest.raises(ValueError, match="Venue not found"):
        await svc.update_event(event.id, EventUpdate(venue_id=9999))


async def test_update_event_cross_field_time_validation(
    db_session: AsyncSession, event_factory
):
    """Changing only ends_at to before the existing starts_at should fail."""
    now = datetime.now(UTC)
    event = await event_factory(
        starts_at=now + timedelta(days=5),
        ends_at=now + timedelta(days=7),
    )

    svc = EventService(db_session)
    with pytest.raises(ValueError, match="ends_at must be after starts_at"):
        await svc.update_event(
            event.id,
            EventUpdate(ends_at=now + timedelta(days=3)),
        )


async def test_update_event_none_fields_ignored(
    db_session: AsyncSession, event_factory
):
    """Sending all-None update should not change anything."""
    event = await event_factory(title="Stable", description="Original")

    svc = EventService(db_session)
    updated = await svc.update_event(event.id, EventUpdate())

    assert updated.title == "Stable"
    assert updated.description == "Original"


async def test_update_event_rejects_nonexistent(db_session: AsyncSession):
    svc = EventService(db_session)
    with pytest.raises(ValueError, match="Event not found"):
        await svc.update_event(9999, EventUpdate(title="X"))


async def test_get_event_success(db_session: AsyncSession, event_factory):
    event = await event_factory(status=EventStatus.DRAFT)

    svc = EventService(db_session)
    result = await svc.get_event(event.id)

    assert result.id == event.id
    # Admin get_event returns drafts too
    assert result.status == EventStatus.DRAFT


async def test_get_event_rejects_nonexistent(db_session: AsyncSession):
    svc = EventService(db_session)
    with pytest.raises(ValueError, match="Event not found"):
        await svc.get_event(9999)


async def test_list_all_filter_by_status(db_session: AsyncSession, event_factory):
    await event_factory(title="Pub A", status=EventStatus.PUBLISHED)
    await event_factory(title="Pub B", status=EventStatus.PUBLISHED)
    await event_factory(title="Draft", status=EventStatus.DRAFT)

    svc = EventService(db_session)
    items, total = await svc.list_all(status=EventStatus.DRAFT)

    assert total == 1
    assert items[0].title == "Draft"


async def test_list_public_search(db_session: AsyncSession, event_factory):
    await event_factory(title="Summer Jazz Night", status=EventStatus.PUBLISHED)
    await event_factory(title="Winter Rock Show", status=EventStatus.PUBLISHED)

    svc = EventService(db_session)
    items, total = await svc.list_public(search="Jazz")

    assert total == 1
    assert items[0].title == "Summer Jazz Night"


async def test_list_pagination(db_session: AsyncSession, event_factory):
    for i in range(5):
        await event_factory(title=f"Event {i}", status=EventStatus.PUBLISHED)

    svc = EventService(db_session)
    items, total = await svc.list_public(offset=2, limit=2)

    assert total == 5
    assert len(items) == 2
