from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import auth
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
    return app
