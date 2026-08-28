from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.ticket_type import TicketType


class TicketTypeRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, ticket_type_id: int) -> TicketType | None:
        result = await self.db.execute(
            select(TicketType)
            .options(selectinload(TicketType.event))
            .where(TicketType.id == ticket_type_id)
        )
        return result.scalar_one_or_none()

    async def list_by_event(
        self,
        event_id: int,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[TicketType], int]:
        base = select(TicketType).where(TicketType.event_id == event_id)
        count_q = (
            select(func.count())
            .select_from(TicketType)
            .where(TicketType.event_id == event_id)
        )

        total = (await self.db.execute(count_q)).scalar_one()
        stmt = (
            base.options(selectinload(TicketType.event))
            .order_by(TicketType.id.asc())
            .offset(offset)
            .limit(limit)
        )
        items = list((await self.db.execute(stmt)).scalars().all())
        return items, total

    async def list_all(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        event_id: int | None = None,
    ) -> tuple[list[TicketType], int]:
        base = select(TicketType)
        count_q = select(func.count()).select_from(TicketType)

        if event_id is not None:
            base = base.where(TicketType.event_id == event_id)
            count_q = count_q.where(TicketType.event_id == event_id)

        total = (await self.db.execute(count_q)).scalar_one()
        stmt = (
            base.options(selectinload(TicketType.event))
            .order_by(TicketType.id.desc())
            .offset(offset)
            .limit(limit)
        )
        items = list((await self.db.execute(stmt)).scalars().all())
        return items, total

    async def create(
        self,
        *,
        event_id: int,
        name: str,
        price_cents: int,
        currency: str = "USD",
        total_quantity: int = 0,
        sales_start_at: datetime,
        sales_end_at: datetime,
    ) -> TicketType:
        ticket_type = TicketType(
            event_id=event_id,
            name=name,
            price_cents=price_cents,
            currency=currency,
            total_quantity=total_quantity,
            reserved_quantity=0,
            sold_quantity=0,
            sales_start_at=sales_start_at,
            sales_end_at=sales_end_at,
        )
        self.db.add(ticket_type)
        await self.db.commit()
        return await self.get_by_id(ticket_type.id)  # type: ignore[return-value]

    async def update(self, ticket_type: TicketType, **fields) -> TicketType:
        for key, value in fields.items():
            if value is not None:
                setattr(ticket_type, key, value)
        self.db.add(ticket_type)
        await self.db.commit()
        return await self.get_by_id(ticket_type.id)  # type: ignore[return-value]

    async def delete(self, ticket_type: TicketType) -> None:
        await self.db.delete(ticket_type)
        await self.db.commit()
