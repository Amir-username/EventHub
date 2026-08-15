"""Unit tests for VenueService business logic.

Tests CRUD operations, not-found errors, and search filtering.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.venue import VenueCreate, VenueUpdate
from app.services.venue_service import VenueService

# ── Create Venue ─────────────────────────────────────────────────────


async def test_create_venue_success(db_session: AsyncSession, user_factory):
    user = await user_factory()

    svc = VenueService(db_session)
    venue = await svc.create_venue(
        VenueCreate(
            name="Grand Hall",
            address="456 Main St",
            city="Tehran",
            capacity=500,
        ),
        created_by=user.id,
    )

    assert venue.id is not None
    assert venue.name == "Grand Hall"
    assert venue.city == "Tehran"
    assert venue.capacity == 500
    assert venue.created_by == user.id


# ── Get Venue ────────────────────────────────────────────────────────


async def test_get_public_venue_success(db_session: AsyncSession, venue_factory):
    venue = await venue_factory(name="Public Hall")

    svc = VenueService(db_session)
    result = await svc.get_public(venue.id)

    assert result.id == venue.id
    assert result.name == "Public Hall"


async def test_get_public_venue_rejects_nonexistent(db_session: AsyncSession):
    svc = VenueService(db_session)
    with pytest.raises(ValueError, match="Venue not found"):
        await svc.get_public(9999)


async def test_get_venue_success(db_session: AsyncSession, venue_factory):
    venue = await venue_factory(name="Admin View")

    svc = VenueService(db_session)
    result = await svc.get_venue(venue.id)

    assert result.id == venue.id


async def test_get_venue_rejects_nonexistent(db_session: AsyncSession):
    svc = VenueService(db_session)
    with pytest.raises(ValueError, match="Venue not found"):
        await svc.get_venue(9999)


# ── Update Venue ─────────────────────────────────────────────────────


async def test_update_venue_name(db_session: AsyncSession, venue_factory):
    venue = await venue_factory(name="Old Name")

    svc = VenueService(db_session)
    updated = await svc.update_venue(venue.id, VenueUpdate(name="New Name"))

    assert updated.name == "New Name"
    # Other fields unchanged
    assert updated.city == venue.city


async def test_update_venue_multiple_fields(db_session: AsyncSession, venue_factory):
    venue = await venue_factory(name="Old", city="OldCity", capacity=100)

    svc = VenueService(db_session)
    updated = await svc.update_venue(
        venue.id, VenueUpdate(name="New", city="NewCity", capacity=999)
    )

    assert updated.name == "New"
    assert updated.city == "NewCity"
    assert updated.capacity == 999


async def test_update_venue_rejects_nonexistent(db_session: AsyncSession):
    svc = VenueService(db_session)
    with pytest.raises(ValueError, match="Venue not found"):
        await svc.update_venue(9999, VenueUpdate(name="X"))


async def test_update_venue_none_fields_ignored(
    db_session: AsyncSession, venue_factory
):
    """Sending all-None update should not change anything."""
    venue = await venue_factory(name="Stable", city="StableCity")

    svc = VenueService(db_session)
    updated = await svc.update_venue(venue.id, VenueUpdate())

    assert updated.name == "Stable"
    assert updated.city == "StableCity"


# ── Delete Venue ─────────────────────────────────────────────────────


async def test_delete_venue_success(db_session: AsyncSession, venue_factory):
    venue = await venue_factory()

    svc = VenueService(db_session)
    await svc.delete_venue(venue.id)

    with pytest.raises(ValueError, match="Venue not found"):
        await svc.get_venue(venue.id)


async def test_delete_venue_rejects_nonexistent(db_session: AsyncSession):
    svc = VenueService(db_session)
    with pytest.raises(ValueError, match="Venue not found"):
        await svc.delete_venue(9999)


# ── List Venues ──────────────────────────────────────────────────────


async def test_list_public_returns_all_venues(db_session: AsyncSession, venue_factory):
    await venue_factory(name="Venue A")
    await venue_factory(name="Venue B")

    svc = VenueService(db_session)
    _items, total = await svc.list_public()

    assert total == 2


async def test_list_all_returns_all_venues(db_session: AsyncSession, venue_factory):
    await venue_factory(name="Venue A")
    await venue_factory(name="Venue B")
    await venue_factory(name="Venue C")

    svc = VenueService(db_session)
    _items, total = await svc.list_all()

    assert total == 3


async def test_list_public_search_by_name(db_session: AsyncSession, venue_factory):
    await venue_factory(name="Grand Opera House")
    await venue_factory(name="Small Club")

    svc = VenueService(db_session)
    items, total = await svc.list_public(search="opera")

    assert total == 1
    assert items[0].name == "Grand Opera House"


async def test_list_public_search_by_city(db_session: AsyncSession, venue_factory):
    await venue_factory(name="Hall A", city="Tehran")
    await venue_factory(name="Hall B", city="Isfahan")

    svc = VenueService(db_session)
    items, total = await svc.list_public(search="Isfahan")

    assert total == 1
    assert items[0].city == "Isfahan"


async def test_list_pagination_offset_limit(db_session: AsyncSession, venue_factory):
    for i in range(5):
        await venue_factory(name=f"Venue {i}")

    svc = VenueService(db_session)
    items, total = await svc.list_all(offset=2, limit=2)

    assert total == 5
    assert len(items) == 2
