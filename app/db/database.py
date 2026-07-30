from collections.abc import AsyncGenerator

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import (
    AsyncAttrs,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()

# Auto-convert sqlite:// to sqlite+aiosqlite:// for async support
database_url = settings.database_url
if database_url.startswith("sqlite:///") and not database_url.startswith(
    "sqlite+aiosqlite"
):
    database_url = database_url.replace("sqlite:///", "sqlite+aiosqlite:///")

# Engine kwargs: only use connection pooling for Postgres
engine_kwargs: dict = {"echo": settings.debug}
if "postgresql" in database_url:
    engine_kwargs.update(
        {
            "pool_size": settings.db_pool_size,
            "max_overflow": 10,
            "pool_pre_ping": True,
        }
    )

engine = create_async_engine(database_url, **engine_kwargs)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)

convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(AsyncAttrs, DeclarativeBase):
    metadata = MetaData(naming_convention=convention)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
