# ADR-003: Use FastAPI Application Factory Pattern

## Status

**Accepted**

## Context

EventHub is a multi-tenant event management and ticketing platform with the following characteristics:

- **Multiple runtime environments**: Development (SQLite + mocked payments), Staging (PostgreSQL + sandbox payments), and Production (PostgreSQL + live payment provider + strict rate limiting).
- **Complex integration testing**: Core flows (browse → reserve → pay → confirm → inventory update) require isolated app instances with test databases, mocked external services, and toggled middleware.
- **Database and cache lifecycle**: The application relies on SQLAlchemy (async), Redis for caching/session store, and potentially Celery for background jobs (e.g., sending confirmation emails). These resources must be initialized and torn down cleanly.
- **Multi-audience API surface**: Customers (public browsing), Admins (venue/event management), and External Partners (versioned, rate-limited JSON API). Each audience may require different middleware stacks, authentication backends, or router configurations in the future.
- **Payment provider abstraction**: The system integrates with a mocked payment provider for testing and a real gateway for production. The application must support swapping this dependency without code changes.

The default FastAPI pattern creates a global `app = FastAPI()` instance at module import time. This approach makes environment-specific configuration, test isolation, and resource lifecycle management difficult because:

1. Configuration is read at import time, making it hard to override in tests.
2. Global state (database connections, middleware) leaks between test cases.
3. Conditional router registration or middleware stacking requires `if` blocks at the top level of modules, reducing readability and testability.
4. Running multiple app variants (e.g., a partner-only API server) requires duplicating setup logic.

## Decision

We will adopt the **FastAPI Application Factory Pattern**. All application setup logic (router registration, middleware attachment, lifespan context managers, and dependency overrides) will be encapsulated in a `create_app(settings: Settings | None = None) -> FastAPI` function located in `app/factory.py`.

The concrete ASGI application instance will be created in the entry-point module (`main.py` or `app/main.py`) by calling this factory with the appropriate settings.

### Key Rules

1. **No global `app` instance in internal modules**: Only the entry-point module may expose a top-level `app` object.
2. **Settings-driven configuration**: The factory accepts a `Settings` object (Pydantic-based). All environment-specific behavior (database URLs, payment provider mode, feature flags) flows through this object.
3. **Lifespan context managers**: Database connections, Redis pools, and other resources are initialized inside an `@asynccontextmanager` lifespan handler attached within the factory.
4. **Router registration inside the factory**: Core routers (events, tickets, payments, admin, partners) are hardcoded inside `create_app()` to maintain a single source of truth for the application's structure. Optional/experimental routers may be toggled via `Settings` feature flags.
5. **Test isolation**: The test suite will create app instances via `create_app(TestSettings())`, ensuring each test receives a clean, fully configured application with an isolated database and mocked external dependencies.

## Consequences

### Positive

- **Testability**: Integration tests can spawn isolated app instances with test databases, mocked payment providers, and disabled rate limiting without monkeypatching global state.
- **Configuration clarity**: All environment-specific wiring lives in one function. A developer can read `create_app()` and understand the entire application's structure.
- **Resource lifecycle safety**: Database and cache connections are tied to the app's lifespan, guaranteeing proper startup and shutdown per instance.
- **Deployment flexibility**: The same codebase can produce differently configured apps (e.g., partner API only, admin only) by passing different settings or calling the factory with overrides.
- **No circular import issues**: Routers and services import the factory or settings without risk of triggering side effects from a globally instantiated `FastAPI()` object.

### Negative

- **Slight boilerplate**: Every test helper and entry-point script must explicitly call `create_app()` rather than importing a ready-made `app`.
- **Uvicorn factory flag**: Developers must ensure Uvicorn or the FastAPI CLI points to the concrete `app` object in the entry module (`main:app`), or use the `--factory` flag if calling the factory directly.
- **Indirection**: New team members must understand that `create_app()` is the canonical place to register new routers or middleware, not scattered across modules.

## Alternatives Considered

### 1. Global `app = FastAPI()` Instance (Status Quo)

- **Rejected**: Makes it impossible to create isolated app instances for testing. Configuration would need to be mutated via monkeypatching or global state, which is error-prone and reduces test parallelism.

### 2. Passing Routers as Arguments to the Factory

- **Rejected**: While this adds flexibility for plugin-like systems, EventHub's router structure is stable and domain-specific. Hardcoding routers inside the factory provides better discoverability and ensures the application structure is explicit. If future requirements demand pluggable routers, we can expose an `extra_routers: list[APIRouter] | None` parameter without changing the core pattern.

### 3. Multiple Entry Modules (e.g., `main_customer.py`, `main_partner.py`)

- **Rejected**: Duplicates factory logic. Instead, we will use a single factory with settings-driven conditional registration (e.g., `if settings.ENABLE_PARTNER_API: app.include_router(partners.router)`).

## Implementation Notes

```python
# app/factory.py
from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.config import Settings
from app.database import init_db, close_db
from app.routers import events, tickets, payments, admin, partners


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings: Settings = app.state.settings
    await init_db(settings.database_url)
    yield
    await close_db()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    app = FastAPI(
        title="EventHub",
        version="1.0.0",
        lifespan=lifespan,
        debug=settings.debug,
    )
    app.state.settings = settings

    # Core routers
    app.include_router(events.router)
    app.include_router(tickets.router)
    app.include_router(payments.router)
    app.include_router(admin.router, prefix="/admin")

    if settings.enable_partner_api:
        app.include_router(partners.router, prefix="/api/v1/partners")

    return app
```

```python
# main.py
from app.factory import create_app
from app.config import get_settings

app = create_app(get_settings())
```

## References

- [FastAPI Documentation — Larger Applications](https://fastapi.tiangolo.com/tutorial/bigger-applications/)
- [Flask Application Factories](https://flask.palletsprojects.com/en/latest/patterns/appfactories/)
- [ASGI Lifespan Protocol](https://asgi.readthedocs.io/en/latest/specs/lifespan.html)
