import enum
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base

if TYPE_CHECKING:
    from app.models.event import Event
    from app.models.reservation import Reservation
    from app.models.venue import Venue


class UserRole(str, enum.Enum):
    CUSTOMER = "customer"
    ADMIN = "admin"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role_enum", create_type=True),
        nullable=False,
        default=UserRole.CUSTOMER,
    )
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    venues: Mapped[list["Venue"]] = relationship("Venue", back_populates="creator")
    events: Mapped[list["Event"]] = relationship("Event", back_populates="creator")
    reservations: Mapped[list["Reservation"]] = relationship(
        "Reservation", back_populates="user"
    )
