# app/factory.py
from fastapi import FastAPI

from app.config import Settings

# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     # Startup logic
#     await init_db()
#     yield
#     # Shutdown logic
#     pass


def create_app(settings: Settings | None = None) -> FastAPI:
    """Application factory."""
    if settings is None:
        settings = Settings()

    app = FastAPI(
        title=settings.APP_NAME,
        debug=settings.DEBUG,
        # lifespan=lifespan,
    )

    # # Register routers
    # app.include_router(users.router)

    # Add middleware
    # app.add_middleware(...)

    return app
