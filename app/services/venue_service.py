from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.venue_repository import VenueRepository
from app.schemas.venue import VenueCreate, VenueUpdate


class VenueService:
    def __init__(self, db: AsyncSession):
        self.repo = VenueRepository(db)

    async def list_public(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        search: str | None = None,
    ) -> tuple[list, int]:
        return await self.repo.list_all(offset=offset, limit=limit, search=search)

    async def get_public(self, venue_id: int):
        venue = await self.repo.get_by_id(venue_id)
        if not venue:
            raise ValueError("Venue not found")
        return venue

    async def list_all(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        search: str | None = None,
    ) -> tuple[list, int]:
        return await self.repo.list_all(offset=offset, limit=limit, search=search)

    async def get_venue(self, venue_id: int):
        venue = await self.repo.get_by_id(venue_id)
        if not venue:
            raise ValueError("Venue not found")
        return venue

    async def create_venue(self, data: VenueCreate, created_by: int):
        return await self.repo.create(
            name=data.name,
            address=data.address,
            city=data.city,
            capacity=data.capacity,
            created_by=created_by,
        )

    async def update_venue(self, venue_id: int, data: VenueUpdate):
        venue = await self.repo.get_by_id(venue_id)
        if not venue:
            raise ValueError("Venue not found")

        fields: dict = {}
        if data.name is not None:
            fields["name"] = data.name
        if data.address is not None:
            fields["address"] = data.address
        if data.city is not None:
            fields["city"] = data.city
        if data.capacity is not None:
            fields["capacity"] = data.capacity

        return await self.repo.update(venue, **fields)

    async def delete_venue(self, venue_id: int):
        venue = await self.repo.get_by_id(venue_id)
        if not venue:
            raise ValueError("Venue not found")
        await self.repo.delete(venue)
