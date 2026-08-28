from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware

from app.api import admin_users, auth, events, reservations, ticket_types, venues
from app.config import Settings
from app.middleware.rate_limit import InMemoryRateLimitBackend, RateLimitMiddleware
from app.middleware.request_id import RequestIDMiddleware
from app.middleware.timing import TimingMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


def _cors_kwargs(settings: Settings) -> dict:
    """Return CORS arguments based on the current environment.

    - development  → permissive (allow all origins with credentials)
    - production   → strict allow-list from ``settings.cors_origins``
    """
    if settings.environment == "development":
        return {
            "allow_origins": ["*"],
            "allow_credentials": True,
            "allow_methods": ["*"],
            "allow_headers": ["*"],
        }
    return {
        "allow_origins": settings.cors_origins,
        "allow_credentials": True,
        "allow_methods": ["GET", "POST", "PUT", "PATCH", "DELETE"],
        "allow_headers": ["Authorization", "Content-Type", "X-Request-ID"],
    }


def create_app(settings: Settings | None = None) -> FastAPI:
    if settings is None:
        settings = Settings()

    app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)

    # Register middlewares
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(TimingMiddleware)
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.add_middleware(CORSMiddleware, **_cors_kwargs(settings))
    app.add_middleware(
        RateLimitMiddleware,
        backend=InMemoryRateLimitBackend(),
        max_requests=settings.rate_limit_max_requests,
        window_seconds=settings.rate_limit_window_seconds,
        enabled=settings.rate_limit_enabled,
    )

    # Register routers
    app.include_router(auth.router)
    app.include_router(admin_users.router)
    app.include_router(events.router)
    app.include_router(venues.router)
    app.include_router(ticket_types.router)
    app.include_router(reservations.router)
    return app
