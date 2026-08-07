from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import admin_users, auth, events, venues
from app.config import Settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


def create_app(settings: Settings | None = None) -> FastAPI:
    if settings is None:
        settings = Settings()

    app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)

    # Register routers
    app.include_router(auth.router)
    app.include_router(admin_users.router)
    app.include_router(events.router)
    app.include_router(venues.router)
    return app
