# app/factory.py
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import Settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create all tables (dev only — use Alembic in production)
    yield
    # Shutdown: clean up engine


def create_app(settings: Settings | None = None) -> FastAPI:
    """Application factory."""
    if settings is None:
        settings = Settings()

    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        lifespan=lifespan,
    )

    # # Register routers
    # app.include_router(users.router)

    # Add middleware
    # app.add_middleware(...)

    return app
