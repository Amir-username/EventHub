from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import EventStatus
from app.models.venue import Venue
from app.repositories.event_repository import EventRepository
from app.schemas.event import EventCreate, EventUpdate


class EventService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = EventRepository(db)

    # ── Public reads ───────────────────────────────────────────────

    async def list_public(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        search: str | None = None,
    ) -> tuple[list, int]:
        return await self.repo.list_public(offset=offset, limit=limit, search=search)

    async def get_public(self, event_id: int):
        event = await self.repo.get_by_id(event_id)
        if not event:
            raise ValueError("Event not found")
        if event.status != EventStatus.PUBLISHED:
            raise ValueError("Event not found")
        return event

    # ── Admin reads ────────────────────────────────────────────────

    async def list_all(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        status: EventStatus | None = None,
        search: str | None = None,
    ) -> tuple[list, int]:
        return await self.repo.list_all(
            offset=offset, limit=limit, status=status, search=search
        )

    async def get_event(self, event_id: int):
        event = await self.repo.get_by_id(event_id)
        if not event:
            raise ValueError("Event not found")
        return event

    # ── Admin writes ───────────────────────────────────────────────

    async def create_event(self, data: EventCreate, created_by: int):
        if data.ends_at <= data.starts_at:
            raise ValueError("ends_at must be after starts_at")

        # Validate venue exists
        venue = (
            await self.db.execute(select(Venue).where(Venue.id == data.venue_id))
        ).scalar_one_or_none()
        if not venue:
            raise ValueError("Venue not found")

        status = EventStatus(data.status)
        return await self.repo.create(
            venue_id=data.venue_id,
            title=data.title,
            description=data.description,
            starts_at=data.starts_at,
            ends_at=data.ends_at,
            created_by=created_by,
            status=status,
        )

    async def update_event(self, event_id: int, data: EventUpdate):
        event = await self.repo.get_by_id(event_id)
        if not event:
            raise ValueError("Event not found")

        fields: dict = {}
        if data.venue_id is not None:
            venue = (
                await self.db.execute(select(Venue).where(Venue.id == data.venue_id))
            ).scalar_one_or_none()
            if not venue:
                raise ValueError("Venue not found")
            fields["venue_id"] = data.venue_id
        if data.title is not None:
            fields["title"] = data.title
        if data.description is not None:
            fields["description"] = data.description
        if data.starts_at is not None:
            fields["starts_at"] = data.starts_at
        if data.ends_at is not None:
            fields["ends_at"] = data.ends_at
        if data.status is not None:
            fields["status"] = EventStatus(data.status)

        # Cross-field validation
        new_start = fields.get("starts_at", event.starts_at)
        new_end = fields.get("ends_at", event.ends_at)
        if new_end <= new_start:
            raise ValueError("ends_at must be after starts_at")

        return await self.repo.update(event, **fields)

    async def delete_event(self, event_id: int):
        event = await self.repo.get_by_id(event_id)
        if not event:
            raise ValueError("Event not found")
        await self.repo.delete(event)
