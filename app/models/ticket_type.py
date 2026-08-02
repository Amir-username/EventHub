from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base

if TYPE_CHECKING:
    from app.models.event import Event
    from app.models.reservation import Reservation


class TicketType(Base):
    __tablename__ = "ticket_types"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    price_cents: Mapped[int] = mapped_column(nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    total_quantity: Mapped[int] = mapped_column(nullable=False)
    reserved_quantity: Mapped[int] = mapped_column(nullable=False, default=0)
    sold_quantity: Mapped[int] = mapped_column(nullable=False, default=0)
    sales_start_at: Mapped[datetime] = mapped_column(nullable=False)
    sales_end_at: Mapped[datetime] = mapped_column(nullable=False)

    # Relationships
    event: Mapped["Event"] = relationship("Event", back_populates="ticket_types")
    reservations: Mapped[list["Reservation"]] = relationship(
        "Reservation", back_populates="ticket_type"
    )
