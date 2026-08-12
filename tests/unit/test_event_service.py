"""Shared test configuration and fixtures for all test types.

This file is loaded automatically by pytest for every test directory.
"""

import itertools
import os
from datetime import UTC

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.database import Base

# ── Ensure RSA keys exist for JWT token creation in tests ───────────
# The security module loads keys from files on import. We generate
# temporary keys before any test imports security.py.

_scripts_dir = os.path.join(os.path.dirname(__file__), "..", "scripts")
_private_key_path = os.path.join(_scripts_dir, "private_key.pem")
_public_key_path = os.path.join(_scripts_dir, "public_key.pem")

if not os.path.exists(_private_key_path) or not os.path.exists(_public_key_path):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    _key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    os.makedirs(_scripts_dir, exist_ok=True)
    with open(_private_key_path, "wb") as f:
        f.write(
            _key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )
    with open(_public_key_path, "wb") as f:
        f.write(
            _key.public_key().public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
        )


# ── In-memory SQLite engine for tests ───────────────────────────────
# In-memory SQLite is fast and requires no external services.

TestEngine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    echo=False,
)

TestSessionLocal = async_sessionmaker(
    TestEngine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


# ── Per-test database isolation ─────────────────────────────────────
# Each test gets a fresh in-memory database (create_all → test → drop_all).
# This is fast with SQLite in-memory and guarantees full isolation.


@pytest_asyncio.fixture()
async def db_session():
    """Provide a fresh database session with all tables created.

    The entire database is dropped and recreated for each test,
    guaranteeing full isolation. This is fast with in-memory SQLite.

    Usage:
        async def test_something(db_session):
            service = MyService(db_session)
            result = await service.do_thing()
            assert result is not None
    """
    async with TestEngine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestSessionLocal() as session:
        yield session

    async with TestEngine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


# ── Factory fixtures for creating test objects ─────────────────────


@pytest_asyncio.fixture()
async def user_factory(db_session: AsyncSession):
    """Factory to create User records without going through AuthService.

    Usage:
        user = await user_factory(email="a@b.com", role=UserRole.ADMIN)
    """
    from app.models.user import User, UserRole

    _counter = itertools.count(1)

    async def _create(
        email: str | None = None,
        hashed_password: str = "dummy_hash",
        full_name: str = "Test User",
        role: UserRole = UserRole.CUSTOMER,
    ) -> User:
        user = User(
            email=email or f"user-{next(_counter)}@test.example.com",
            hashed_password=hashed_password,
            full_name=full_name,
            role=role,
        )
        db_session.add(user)
        await db_session.flush()
        return user

    return _create


@pytest_asyncio.fixture()
async def venue_factory(db_session: AsyncSession, user_factory):
    """Factory to create Venue records.

    Usage:
        venue = await venue_factory(name="Test Hall")
    """
    from app.models.venue import Venue

    async def _create(
        name: str = "Test Venue",
        address: str = "123 Test St",
        city: str = "Test City",
        capacity: int = 100,
        created_by: int | None = None,
    ) -> Venue:
        if created_by is None:
            creator = await user_factory()
            created_by = creator.id
        venue = Venue(
            name=name,
            address=address,
            city=city,
            capacity=capacity,
            created_by=created_by,
        )
        db_session.add(venue)
        await db_session.flush()
        return venue

    return _create


@pytest_asyncio.fixture()
async def event_factory(db_session: AsyncSession, user_factory, venue_factory):
    """Factory to create Event records.

    Usage:
        event = await event_factory(title="Test Concert")
    """
    from datetime import datetime, timedelta

    from app.models.event import Event, EventStatus

    async def _create(
        title: str = "Test Event",
        description: str = "A test event",
        venue_id: int | None = None,
        created_by: int | None = None,
        starts_at: datetime | None = None,
        ends_at: datetime | None = None,
        status: EventStatus = EventStatus.PUBLISHED,
    ) -> Event:
        now = datetime.now(UTC)
        if starts_at is None:
            starts_at = now + timedelta(days=1)
        if ends_at is None:
            ends_at = starts_at + timedelta(hours=2)
        if venue_id is None:
            venue = await venue_factory()
            venue_id = venue.id
        if created_by is None:
            creator = await user_factory()
            created_by = creator.id

        event = Event(
            title=title,
            description=description,
            venue_id=venue_id,
            created_by=created_by,
            starts_at=starts_at,
            ends_at=ends_at,
            status=status,
        )
        db_session.add(event)
        await db_session.flush()
        return event

    return _create
