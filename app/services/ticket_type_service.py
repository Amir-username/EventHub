from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import Event, EventStatus
from app.repositories.ticket_type_repository import TicketTypeRepository
from app.schemas.ticket_type import TicketTypeCreate, TicketTypeUpdate


class TicketTypeService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = TicketTypeRepository(db)

    # ── Public reads ───────────────────────────────────────────────

    async def list_public_by_event(
        self,
        event_id: int,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list, int]:
        # Only allow listing for published events
        event = (
            await self.db.execute(select(Event).where(Event.id == event_id))
        ).scalar_one_or_none()
        if not event or event.status != EventStatus.PUBLISHED:
            raise ValueError("Event not found")
        return await self.repo.list_by_event(event_id, offset=offset, limit=limit)

    async def get_public(self, ticket_type_id: int):
        ticket_type = await self.repo.get_by_id(ticket_type_id)
        if not ticket_type:
            raise ValueError("Ticket type not found")
        if ticket_type.event.status != EventStatus.PUBLISHED:
            raise ValueError("Ticket type not found")
        return ticket_type

    # ── Admin reads ────────────────────────────────────────────────

    async def list_all(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        event_id: int | None = None,
    ) -> tuple[list, int]:
        return await self.repo.list_all(offset=offset, limit=limit, event_id=event_id)

    async def get_ticket_type(self, ticket_type_id: int):
        ticket_type = await self.repo.get_by_id(ticket_type_id)
        if not ticket_type:
            raise ValueError("Ticket type not found")
        return ticket_type

    # ── Admin writes ───────────────────────────────────────────────

    async def create_ticket_type(self, data: TicketTypeCreate):
        if data.sales_end_at <= data.sales_start_at:
            raise ValueError("sales_end_at must be after sales_start_at")

        event = (
            await self.db.execute(select(Event).where(Event.id == data.event_id))
        ).scalar_one_or_none()
        if not event:
            raise ValueError("Event not found")

        return await self.repo.create(
            event_id=data.event_id,
            name=data.name,
            price_cents=data.price_cents,
            currency=data.currency,
            total_quantity=data.total_quantity,
            sales_start_at=data.sales_start_at,
            sales_end_at=data.sales_end_at,
        )

    async def update_ticket_type(self, ticket_type_id: int, data: TicketTypeUpdate):
        ticket_type = await self.repo.get_by_id(ticket_type_id)
        if not ticket_type:
            raise ValueError("Ticket type not found")

        fields: dict = {}
        if data.name is not None:
            fields["name"] = data.name
        if data.price_cents is not None:
            fields["price_cents"] = data.price_cents
        if data.currency is not None:
            fields["currency"] = data.currency
        if data.total_quantity is not None:
            fields["total_quantity"] = data.total_quantity
        if data.sales_start_at is not None:
            fields["sales_start_at"] = data.sales_start_at
        if data.sales_end_at is not None:
            fields["sales_end_at"] = data.sales_end_at

        # Cross-field validation
        new_start = fields.get("sales_start_at", ticket_type.sales_start_at)
        new_end = fields.get("sales_end_at", ticket_type.sales_end_at)
        if new_end <= new_start:
            raise ValueError("sales_end_at must be after sales_start_at")

        return await self.repo.update(ticket_type, **fields)

    async def delete_ticket_type(self, ticket_type_id: int):
        ticket_type = await self.repo.get_by_id(ticket_type_id)
        if not ticket_type:
            raise ValueError("Ticket type not found")
        await self.repo.delete(ticket_type)
