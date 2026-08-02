import enum
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base

if TYPE_CHECKING:
    from app.models.order import Order
    from app.models.ticket_type import TicketType
    from app.models.user import User


class ReservationStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class Reservation(Base):
    __tablename__ = "reservations"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    ticket_type_id: Mapped[int] = mapped_column(
        ForeignKey("ticket_types.id"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[ReservationStatus] = mapped_column(
        Enum(ReservationStatus, name="reservation_status_enum", create_type=True),
        nullable=False,
        default=ReservationStatus.PENDING,
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="reservations")
    ticket_type: Mapped["TicketType"] = relationship(
        "TicketType", back_populates="reservations"
    )
    order: Mapped["Order | None"] = relationship(
        "Order", back_populates="reservation", uselist=False
    )
