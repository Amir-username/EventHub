from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.venue import Venue


class VenueRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, venue_id: int) -> Venue | None:
        result = await self.db.execute(
            select(Venue)
            .options(selectinload(Venue.creator))
            .where(Venue.id == venue_id)
        )
        return result.scalar_one_or_none()

    async def list_all(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        search: str | None = None,
    ) -> tuple[list[Venue], int]:
        base = select(Venue)
        count_q = select(func.count()).select_from(Venue)

        if search:
            pattern = f"%{search}%"
            cond = Venue.name.ilike(pattern) | Venue.city.ilike(pattern)
            base = base.where(cond)
            count_q = count_q.where(cond)

        total = (await self.db.execute(count_q)).scalar_one()
        stmt = (
            base.options(selectinload(Venue.creator))
            .order_by(Venue.id.desc())
            .offset(offset)
            .limit(limit)
        )
        venues = list((await self.db.execute(stmt)).scalars().all())
        return venues, total

    async def create(
        self,
        *,
        name: str,
        address: str,
        city: str,
        capacity: int,
        created_by: int,
    ) -> Venue:
        venue = Venue(
            name=name,
            address=address,
            city=city,
            capacity=capacity,
            created_by=created_by,
        )
        self.db.add(venue)
        await self.db.commit()
        await self.db.refresh(venue)
        return venue

    async def update(self, venue: Venue, **fields) -> Venue:
        for key, value in fields.items():
            if value is not None:
                setattr(venue, key, value)
        self.db.add(venue)
        await self.db.commit()
        await self.db.refresh(venue)
        return venue

    async def delete(self, venue: Venue) -> None:
        await self.db.delete(venue)
        await self.db.commit()
