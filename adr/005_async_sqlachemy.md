# ADR-003: Adopt Async SQLAlchemy for Database Access

## Status
**Accepted** — 2026-07-30

## Context
EventHub is a scaled-down Eventbrite clone with the following database access patterns:

- **High-concurrency reads**: Customers browse events, check ticket availability, and view venue details. These are I/O-bound operations that block on network round-trips to the database.
- **Transactional writes**: Ticket reservations and payments require atomic updates to inventory and order tables.
- **External API**: Partners pull event data through a rate-limited, versioned API. Each request may trigger multiple DB queries.
- **Future scaling target**: Handle traffic spikes during popular event releases without provisioning excessive thread/process pools.

Our current synchronous SQLAlchemy setup works for low traffic, but every DB query blocks the event loop (or a worker thread), reducing throughput under concurrent load. We need a database access layer that:

1. Integrates cleanly with our async Python stack (FastAPI + Uvicorn).
2. Supports the full SQLAlchemy ORM feature set (relationships, migrations via Alembic, hybrid properties).
3. Provides connection pooling without blocking the async event loop.
4. Allows gradual migration from sync code where absolutely necessary.

## Decision
We will use **Async SQLAlchemy** (`sqlalchemy.ext.asyncio`) as the primary database access layer for all new features. Synchronous SQLAlchemy is deprecated for new code and scheduled for removal in Q4 2026.

### Specifics
- **Engine**: `create_async_engine` with `AsyncAdaptedQueuePool` (default) and `pool_pre_ping=True`.
- **Session**: `async_sessionmaker` with `expire_on_commit=False` to prevent lazy-loading issues in async contexts.
- **ORM**: Declarative base via `DeclarativeBase`; relationships defined with standard ORM patterns.
- **Migrations**: Alembic with async support (`run_migrations_online` using `connectable.run_sync`).
- **Sync fallback**: A thin sync wrapper (`run_in_threadpool`) is permitted *only* for third-party libraries that lack async support (e.g., certain reporting tools).

## Consequences

### Positive
- **Concurrency**: DB queries yield control to the event loop, allowing a single worker to handle many concurrent requests without thread-per-request overhead.
- **Throughput**: Reduces need for horizontal scaling during traffic spikes; a single Uvicorn worker handles significantly more I/O-bound requests.
- **Consistency**: Same ORM models, migrations, and query patterns as sync SQLAlchemy; team ramp-up is minimal.
- **Ecosystem alignment**: FastAPI, Starlette, and modern Python libraries are built around `async`/`await`. Async SQLAlchemy fits naturally.
- **API performance**: External partner API endpoints benefit directly from non-blocking DB access under concurrent load.

### Negative
- **Cognitive overhead**: Developers must remember that lazy loading (`relationship` access after session close) is dangerous in async code. `expire_on_commit=False` and explicit `await session.refresh()` are required.
- **Debugging complexity**: Async stack traces and connection pool exhaustion are harder to diagnose than thread-pool saturation.
- **Library compatibility**: Some SQLAlchemy extensions and third-party libraries still assume sync sessions. We may need thin sync wrappers or avoid those libraries.
- **Migration risk**: Existing sync code paths (admin dashboards, background jobs) must be ported or wrapped. This is scheduled work.

## Alternatives Considered

| Alternative | Why Rejected |
|-------------|--------------|
| **Sync SQLAlchemy + ThreadPoolExecutor** | Adds thread overhead; does not scale as efficiently for high-concurrency I/O. GIL limits true parallelism for CPU-bound work, but our bottleneck is DB latency, not CPU. |
| **Databases (Encode)** | Lightweight and fast, but lacks ORM features. We rely on SQLAlchemy ORM for complex relationships and migrations; rewriting all models is too costly. |
| **Tortoise ORM / Prisma Client Python** | Would require rewriting all models, migrations, and queries. Team expertise is in SQLAlchemy. |
| **psycopg3 native async** | Too low-level. We want the SQLAlchemy ORM abstraction for business logic. |

