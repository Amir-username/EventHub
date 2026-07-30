# app/factory.py
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import Settings
from app.db.database import Base, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create all tables (dev only — use Alembic in production)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Shutdown: clean up engine
    await engine.dispose()


def create_app(settings: Settings | None = None) -> FastAPI:
    """Application factory."""
    if settings is None:
        settings = Settings()

    app = FastAPI(
        title=settings.APP_NAME,
        debug=settings.DEBUG,
        lifespan=lifespan,
    )

    # # Register routers
    # app.include_router(users.router)

    # Add middleware
    # app.add_middleware(...)

    return app
