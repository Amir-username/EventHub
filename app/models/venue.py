from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base

if TYPE_CHECKING:
    from app.models.event import Event
    from app.models.user import User


class Venue(Base):
    __tablename__ = "venues"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str] = mapped_column(String(500), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    capacity: Mapped[int] = mapped_column(nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    # Relationships
    creator: Mapped["User"] = relationship("User", back_populates="venues")
    events: Mapped[list["Event"]] = relationship("Event", back_populates="venue")
