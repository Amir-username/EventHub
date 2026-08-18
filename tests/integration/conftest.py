"""Integration test configuration — PostgreSQL testcontainer + full FastAPI app.

These tests exercise the complete HTTP request lifecycle through real PostgreSQL.
They require Docker to be running (for the testcontainer).

Run with:
    pytest tests/integration/ -v

Unit tests (tests/unit/) use in-memory SQLite and do NOT need Docker.
"""

import os
import subprocess
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# ── Override env BEFORE any app import ───────────────────────────────
os.environ["SECRET_KEY"] = "test-secret-key-for-integration-tests"
os.environ["ENVIRONMENT"] = "development"
os.environ["RATE_LIMIT_ENABLED"] = "false"

from app.config import Settings
from app.db.database import Base, get_db
from app.factory import create_app

# ── Docker availability check ──────────────────────────────────────


def _is_docker_available() -> bool:
    """Check if Docker daemon is reachable."""
    try:
        result = subprocess.run(
            ["docker", "info"], capture_output=True, timeout=5, check=False
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


_DOCKER_AVAILABLE = _is_docker_available()


def pytest_collection_modifyitems(session, config, items):
    """Skip integration test items when Docker is not available."""
    if not _DOCKER_AVAILABLE:
        for item in items:
            path = str(item.fspath) if hasattr(item, "fspath") else str(item.path)
            if "/integration/" in path:
                item.add_marker(
                    pytest.mark.skip(
                        reason="Docker is not available — integration tests require Docker for PostgreSQL testcontainer",
                    )
                )


# ── Session-scoped PostgreSQL container ───────────────────────────────
# One container for the entire test session. This adds ~5-10s startup
# but avoids per-test container overhead.


@pytest_asyncio.fixture(scope="session")
def pg_container():
    """Start a PostgreSQL 17 container; yield the container object."""
    from testcontainers.community.postgres import PostgresContainer

    with PostgresContainer("postgres:17-alpine") as pg:
        yield pg


@pytest_asyncio.fixture(scope="session")
def pg_url(pg_container) -> str:
    """Return the asyncpg URL for the test container."""
    url = pg_container.get_connection_url()
    return url.replace("psycopg2", "asyncpg")


@pytest_asyncio.fixture(scope="session")
async def pg_engine(pg_url: str):
    """Create an async engine against the PostgreSQL test container.

    Creates all tables once. Drops them at session end.
    """

    engine = create_async_engine(pg_url, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="session")
def pg_session_factory(pg_engine):
    """Session factory bound to the test PostgreSQL engine."""
    from sqlalchemy.ext.asyncio import AsyncSession

    return async_sessionmaker(
        pg_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )


# ── Per-test session with table truncation ───────────────────────────
# Truncating all rows is much faster than drop_all/create_all per test
# while still providing full data isolation.


@pytest_asyncio.fixture()
async def db_session(
    pg_engine,
    pg_session_factory,
) -> AsyncGenerator[AsyncSession, None]:
    """Provide a clean database session for each test.

    Truncates all tables in reverse dependency order before yielding.
    Commits after setup so the test starts with a clean slate.
    """

    async with pg_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())
        await conn.commit()

    async with pg_session_factory() as session:
        yield session
        await session.rollback()


# ── FastAPI app + TestClient ─────────────────────────────────────────


@pytest_asyncio.fixture()
async def app_client(db_session: AsyncSession):
    """Full FastAPI app with get_db overridden to use the PG test session."""
    from app import config

    config.get_settings.cache_clear()

    settings = Settings(
        secret_key="test-secret-key-for-integration-tests",
        environment="development",
        rate_limit_enabled=False,
        database_url="postgresql+asyncpg://unused",
    )

    app = create_app(settings=settings)
    app.dependency_overrides[get_db] = lambda: db_session

    from starlette.testclient import TestClient

    client = TestClient(app, raise_server_exceptions=False)
    yield client

    app.dependency_overrides.clear()
    config.get_settings.cache_clear()


# ── Auth token helpers ──────────────────────────────────────────────


@pytest_asyncio.fixture()
async def admin_token(db_session: AsyncSession) -> str:
    """Create an admin user and return a valid access token."""
    from app.core.security import create_access_token, hash_password
    from app.models.user import User, UserRole

    user = User(
        email="admin@integration.test",
        hashed_password=hash_password("AdminPass1!"),
        full_name="Integration Admin",
        role=UserRole.ADMIN,
    )
    db_session.add(user)
    await db_session.flush()

    return create_access_token(
        data={"sub": str(user.id), "email": user.email, "role": "admin"}
    )


@pytest_asyncio.fixture()
async def customer_token(db_session: AsyncSession) -> str:
    """Create a customer user and return a valid access token."""
    from app.core.security import create_access_token, hash_password
    from app.models.user import User, UserRole

    user = User(
        email="customer@integration.test",
        hashed_password=hash_password("CustomerPass1!"),
        full_name="Integration Customer",
        role=UserRole.CUSTOMER,
    )
    db_session.add(user)
    await db_session.flush()

    return create_access_token(
        data={"sub": str(user.id), "email": user.email, "role": "customer"}
    )


def auth_header(token: str) -> dict[str, str]:
    """Build an Authorization header dict from a token string."""
    return {"Authorization": f"Bearer {token}"}
