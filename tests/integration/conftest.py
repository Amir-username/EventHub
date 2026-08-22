# /**
#  * Integration test configuration — PostgreSQL testcontainer + full FastAPI app.
#  *
#  * These tests exercise the complete HTTP request lifecycle through real PostgreSQL.
#  * They require Docker to be running (for the testcontainer).
#  *
#  * Run with:
#  *     pytest tests/integration/ -v
#  *
#  * Unit tests (tests/unit/) use in-memory SQLite and do NOT need Docker.
#  *
#  * Architecture note:
#  *   All fixtures here are synchronous (plain @pytest.fixture).
#  *   Async operations (table creation, truncation, user seeding) run inside
#  *   asyncio.run() so they don't conflict with TestClient's internal loop.
#  *   TestClient manages its own event loop — having pytest-asyncio fixtures
#  *   on a *different* loop causes "Future attached to a different loop" errors
#  *   with asyncpg connection pools.
#  */

import asyncio
import os
import subprocess

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# ── Disable Ryuk (testcontainers cleanup container) to avoid port 8080 conflicts ──
os.environ.setdefault("TESTCONTAINERS_RYUK_DISABLED", "true")

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


# ── Session-scoped: PostgreSQL container ─────────────────────────────
# One container for the entire test session. This adds ~5-10s startup
# but avoids per-test container overhead.


@pytest.fixture(scope="session")
def pg_container():
    """Start a PostgreSQL 17 container; yield the container object."""
    from testcontainers.community.postgres import PostgresContainer

    with PostgresContainer("postgres:17-alpine") as pg:
        yield pg


@pytest.fixture(scope="session")
def pg_url(pg_container) -> str:
    """Return the asyncpg URL for the test container."""
    url = pg_container.get_connection_url()
    return url.replace("psycopg2", "asyncpg")


# ── Session-scoped: create / drop tables ─────────────────────────────
# Runs asynchronously via asyncio.run() so no pytest-asyncio loop
# conflicts with TestClient's internal loop.


@pytest.fixture(scope="session")
def pg_setup(pg_url):
    """Create all tables once at session start; drop them at session end."""

    async def _create_tables():
        engine = create_async_engine(pg_url, echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await engine.dispose()

    asyncio.run(_create_tables())
    yield  # ── tests run here ──

    async def _drop_tables():
        engine = create_async_engine(pg_url, echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()

    asyncio.run(_drop_tables())


# ── Per-test: truncate all tables ───────────────────────────────────
# Runs before token fixtures and app_client so every test starts clean.


@pytest.fixture()
def clean_db(pg_setup, pg_url):
    """Truncate all tables in reverse dependency order for test isolation."""

    async def _truncate():
        engine = create_async_engine(pg_url, echo=False)
        async with engine.begin() as conn:
            for table in reversed(Base.metadata.sorted_tables):
                await conn.execute(table.delete())
        await engine.dispose()

    asyncio.run(_truncate())


# ── Per-test: FastAPI app + TestClient ─────────────────────────────
# The get_db override is an async generator that TestClient's internal
# loop calls.  The engine is created synchronously here; its connection
# pool lazily binds to TestClient's loop on first use — no loop conflict.


@pytest.fixture()
def app_client(clean_db, pg_url):
    """Full FastAPI app with get_db overridden to use the PG test session."""
    from app import config

    config.get_settings.cache_clear()

    settings = Settings(
        secret_key="test-secret-key-for-integration-tests",
        environment="development",
        rate_limit_enabled=False,
        database_url="postgresql+asyncpg://unused",
    )

    # create_async_engine is synchronous — no loop needed yet.
    # The pool binds to TestClient's loop on first actual connection.
    engine = create_async_engine(pg_url, echo=False)
    factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )

    async def override_get_db():
        async with factory() as session:
            yield session

    app = create_app(settings=settings)
    app.dependency_overrides[get_db] = override_get_db

    from starlette.testclient import TestClient

    client = TestClient(app, raise_server_exceptions=False)
    yield client

    app.dependency_overrides.clear()
    config.get_settings.cache_clear()
    asyncio.run(engine.dispose())


# ── Auth token fixtures ──────────────────────────────────────────────
# These insert users directly via raw SQL (committed) so the data is
# visible to TestClient's separate connection.  Uses asyncio.run() to
# avoid loop conflicts.


@pytest.fixture()
def admin_token(clean_db, pg_url) -> str:
    """Create an admin user in PG and return a valid access token."""
    from datetime import UTC, datetime

    from app.core.security import create_access_token, hash_password

    async def _create():
        from sqlalchemy import insert

        from app.models.user import User, UserRole

        engine = create_async_engine(pg_url, echo=False)
        async with engine.begin() as conn:
            hashed = hash_password("AdminPass1!")
            result = await conn.execute(
                insert(User)
                .values(
                    email="admin@integration.test",
                    hashed_password=hashed,
                    full_name="Integration Admin",
                    role=UserRole.ADMIN,
                    created_at=datetime.now(UTC),
                )
                .returning(User.id)
            )
            user_id = result.scalar_one()
        await engine.dispose()
        return create_access_token(
            data={
                "sub": str(user_id),
                "email": "admin@integration.test",
                "role": "admin",
            }
        )

    return asyncio.run(_create())


@pytest.fixture()
def customer_token(clean_db, pg_url) -> str:
    """Create a customer user in PG and return a valid access token."""
    from datetime import UTC, datetime

    from app.core.security import create_access_token, hash_password

    async def _create():
        from sqlalchemy import insert

        from app.models.user import User, UserRole

        engine = create_async_engine(pg_url, echo=False)
        async with engine.begin() as conn:
            hashed = hash_password("CustomerPass1!")
            result = await conn.execute(
                insert(User)
                .values(
                    email="customer@integration.test",
                    hashed_password=hashed,
                    full_name="Integration Customer",
                    role=UserRole.CUSTOMER,
                    created_at=datetime.now(UTC),
                )
                .returning(User.id)
            )
            user_id = result.scalar_one()
        await engine.dispose()
        return create_access_token(
            data={
                "sub": str(user_id),
                "email": "customer@integration.test",
                "role": "customer",
            }
        )

    return asyncio.run(_create())


def auth_header(token: str) -> dict[str, str]:
    """Build an Authorization header dict from a token string."""
    return {"Authorization": f"Bearer {token}"}
