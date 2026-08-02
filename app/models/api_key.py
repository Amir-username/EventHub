from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(primary_key=True)
    partner_name: Mapped[str] = mapped_column(String(255), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    scopes: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    rate_limit_tier: Mapped[str] = mapped_column(
        String(50), nullable=False, default="default"
    )
