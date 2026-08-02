import enum
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base

if TYPE_CHECKING:
    from app.models.ticket_type import TicketType
    from app.models.user import User
    from app.models.venue import Venue


class EventStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    CANCELLED = "cancelled"


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    venue_id: Mapped[int] = mapped_column(ForeignKey("venues.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    starts_at: Mapped[datetime] = mapped_column(nullable=False)
    ends_at: Mapped[datetime] = mapped_column(nullable=False)
    status: Mapped[EventStatus] = mapped_column(
        Enum(EventStatus, name="event_status_enum", create_type=True),
        nullable=False,
        default=EventStatus.DRAFT,
    )
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    venue: Mapped["Venue"] = relationship("Venue", back_populates="events")
    creator: Mapped["User"] = relationship("User", back_populates="events")
    ticket_types: Mapped[list["TicketType"]] = relationship(
        "TicketType", back_populates="event"
    )
