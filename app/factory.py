from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.gzip import GZipMiddleware

from app.api import admin_users, auth, events, ticket_types, venues
from app.config import Settings
from app.middleware.request_id import RequestIDMiddleware
from app.middleware.timing import TimingMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


def create_app(settings: Settings | None = None) -> FastAPI:
    if settings is None:
        settings = Settings()

    app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)

    # Register middlewares
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(TimingMiddleware)
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # Register routers
    app.include_router(auth.router)
    app.include_router(admin_users.router)
    app.include_router(events.router)
    app.include_router(venues.router)
    app.include_router(ticket_types.router)
    return app
