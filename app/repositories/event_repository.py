from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.event import Event, EventStatus


class EventRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, event_id: int) -> Event | None:
        result = await self.db.execute(
            select(Event)
            .options(selectinload(Event.venue), selectinload(Event.creator))
            .where(Event.id == event_id)
        )
        return result.scalar_one_or_none()

    async def list_public(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        status: EventStatus | None = None,
        search: str | None = None,
    ) -> tuple[list[Event], int]:
        """List only published events (public reads)."""
        base = select(Event).where(Event.status == EventStatus.PUBLISHED)
        count_q = (
            select(func.count())
            .select_from(Event)
            .where(Event.status == EventStatus.PUBLISHED)
        )

        if search:
            pattern = f"%{search}%"
            cond = Event.title.ilike(pattern) | Event.description.ilike(pattern)
            base = base.where(cond)
            count_q = count_q.where(cond)

        total = (await self.db.execute(count_q)).scalar_one()
        stmt = (
            base.options(selectinload(Event.venue), selectinload(Event.creator))
            .order_by(Event.starts_at.asc())
            .offset(offset)
            .limit(limit)
        )
        events = list((await self.db.execute(stmt)).scalars().all())
        return events, total

    async def list_all(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        status: EventStatus | None = None,
        search: str | None = None,
    ) -> tuple[list[Event], int]:
        """List all events regardless of status (admin reads)."""
        base = select(Event)
        count_q = select(func.count()).select_from(Event)

        if status is not None:
            base = base.where(Event.status == status)
            count_q = count_q.where(Event.status == status)
        if search:
            pattern = f"%{search}%"
            cond = Event.title.ilike(pattern) | Event.description.ilike(pattern)
            base = base.where(cond)
            count_q = count_q.where(cond)

        total = (await self.db.execute(count_q)).scalar_one()
        stmt = (
            base.options(selectinload(Event.venue), selectinload(Event.creator))
            .order_by(Event.id.desc())
            .offset(offset)
            .limit(limit)
        )
        events = list((await self.db.execute(stmt)).scalars().all())
        return events, total

    async def create(
        self,
        *,
        venue_id: int,
        title: str,
        starts_at: datetime,
        ends_at: datetime,
        created_by: int,
        description: str | None = None,
        status: EventStatus = EventStatus.DRAFT,
    ) -> Event:
        event = Event(
            venue_id=venue_id,
            title=title,
            description=description,
            starts_at=starts_at,
            ends_at=ends_at,
            status=status,
            created_by=created_by,
        )
        self.db.add(event)
        await self.db.commit()
        await self.db.refresh(event)
        return event

    async def update(self, event: Event, **fields) -> Event:
        for key, value in fields.items():
            if value is not None:
                setattr(event, key, value)
        self.db.add(event)
        await self.db.commit()
        await self.db.refresh(event)
        return event

    async def delete(self, event: Event) -> None:
        await self.db.delete(event)
        await self.db.commit()
