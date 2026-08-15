# ADR 009: Test Pyramid Strategy

## Status

Accepted

## Context

EventHub is a FastAPI async REST API for event ticketing. As the codebase grew to include authentication (JWT RS256), authorization (role-based middleware), CRUD services for venues/events/ticket types, admin user management, and custom middleware (request ID, timing, rate limiting), we needed a coherent testing strategy that balances **speed**, **isolation**, and **confidence**.

### Key Constraints

- **Async codebase**: All service and repository methods are `async`. Tests must handle async natively without ad-hoc `asyncio.run()` wrappers.
- **Database-dependent business logic**: Services enforce cross-field validation (e.g., `ends_at > starts_at`), existence guards (venue must exist before creating an event), and draft-event visibility rules. Testing these requires a real database — pure mocks would not catch SQL-level regressions.
- **Small team, rapid iteration**: Tests must be cheap to write and maintain. Complex mocking setups or external service dependencies (PostgreSQL, Redis) slow down development and CI.
- **Financial-adjacent domain**: Ticket inventory, pricing, and access control have low tolerance for bugs. Validation gaps at the schema, service, or middleware layer could lead to data corruption or unauthorized access.
- **No frontend or E2E layer yet**: The API is backend-only. There is no UI to drive browser-based end-to-end tests, so the test pyramid must be anchored at the unit and integration levels.

We considered several testing approaches and had to decide on the right layering, tooling, and isolation strategy.

## Decision

We adopt a **modified test pyramid** with three layers, optimized for an async Python API:

```
        ┌─────────────────────┐
        │   Middleware Tests  │  ← 6 tests  (sync, no DB, isolated Starlette)
       ─└─────────────────────┘─
      ──┌───────────────────────┐──
     ───┤  Service + Schema Tests  ├──  ← 96 tests (async, in-memory SQLite)
     ───└───────────────────────┘──
    ─────┌─────────────────────────┐────
   ──────┤  Pure Function Tests     ├─────  ← 24 tests (sync/async, no DB)
   ──────└─────────────────────────┘────
```

### Layer 1 — Pure Function Tests (No Database)

**What**: Stateless functions with zero external dependencies.

**Modules tested**:
- `app/core/security.py` — password hashing (Argon2), JWT token creation/decoding (RS256)
- `app/schemas/*.py` — Pydantic validation rules (field constraints, cross-field validators)

**Count**: 26 tests across `test_security.py` (12) and `test_schemas.py` (14)

**Characteristics**:
- No database, no HTTP client, no async event loop required for security tests (run as `async def` due to `auto` mode but are effectively synchronous)
- Execute in microseconds — these are the fastest tests in the suite
- Catch regressions in: hash algorithm changes, JWT claim structure, password policy enforcement, schema field constraints

### Layer 2 — Service + Schema Integration Tests (In-Memory SQLite)

**What**: Service-layer business logic tested against a real database, using factory fixtures instead of mocks.

**Modules tested**:
- `AuthService` — register, login, refresh token flow
- `VenueService` — CRUD, search, pagination
- `EventService` — CRUD, cross-field time validation, draft-event guards, status filtering
- `TicketTypeService` — CRUD, sales window validation, draft-event guards
- `AdminUserService` — admin CRUD, role parsing, email uniqueness, self-delete prevention

**Count**: 96 tests across 5 test files

**Characteristics**:
- Use **in-memory SQLite** via `aiosqlite` — no external PostgreSQL dependency, no Docker, no network
- **Per-test isolation**: Each test gets a fresh database (`create_all` → test → `drop_all`), guaranteeing no state leaks
- **Factory fixture pattern**: `user_factory`, `venue_factory`, `event_factory`, `ticket_type_factory` with `itertools.count()` for unique values — eliminates test data setup boilerplate
- These are technically integration-light (real DB, real ORM), but we treat them as our primary unit tests because they test business logic in isolation from HTTP routing

### Layer 3 — Middleware Tests (Isolated HTTP)

**What**: Custom middleware tested against a minimal `Starlette` app (not the full `create_app()`).

**Modules tested**:
- `RequestIDMiddleware` — UUID v4 generation, client header echo, uniqueness per request
- `TimingMiddleware` — `X-Response-Time` header presence and format
- `RateLimitMiddleware` — 429 response after threshold, disabled bypass

**Count**: 6 tests in `test_middleware.py`

**Characteristics**:
- Use `starlette.testclient.TestClient` against a **minimal Starlette app** with only the middleware under test — no database, no auth, no routes beyond `/ping`
- Synchronous test functions (no async needed — `TestClient` handles the event loop)
- Test middleware behavior (headers, status codes) in isolation from application logic

### What We Explicitly Do NOT Test

| Excluded | Reason |
|---|---|
| **Repository layer in isolation** | Repositories are thin SQLAlchemy wrappers. Testing them separately from services adds maintenance cost without catching additional bugs — service tests already exercise the full query path. |
| **Router/endpoint layer** | Routes are thin delegation to services (extract request body → call service → return response). When endpoint tests are added, they will live in `tests/integration/` and will be the right place to test HTTP status codes, response schemas, and error formats. |
| **Pydantic model serialization** | Output schemas (response models) are simple `from_attributes=True` configurations. Their correctness is implicitly verified by service tests that inspect returned ORM objects. |
| **External services** | No payment gateway, email provider, or third-party API exists yet. When they do, they will be mocked at the service boundary using `dependency_overrides` or protocol-based mocks. |

## Tooling Decisions

| Tool | Purpose | Why |
|---|---|---|
| **pytest** | Test runner | Industry standard for Python; supports fixtures, parametrization, plugins |
| **pytest-asyncio** (`auto` mode) | Async test support | `asyncio_mode = "auto"` eliminates the need for `@pytest.mark.asyncio` on every test. All `async def` functions are automatically treated as coroutines. |
| **In-memory SQLite** (`sqlite+aiosqlite:///:memory:`) | Test database | Zero-configuration, no external service, `create_all`/`drop_all` per test gives full isolation. SQLite is sufficient for testing ORM queries and business logic — we do not rely on PostgreSQL-specific features. |
| **Factory fixtures** | Test data creation | `itertools.count()` generates unique emails/names. Factories accept overrides for specific fields while providing sensible defaults. This keeps tests focused on the scenario under test rather than data setup. |
| **Starlette TestClient** | Middleware HTTP testing | Synchronous client that handles the async event loop internally. Used with minimal apps (single `/ping` route) to test middleware in isolation. |
| **Environment overrides** (`os.environ` in `conftest.py`) | Test configuration | Hard-assigns `DATABASE_URL`, `SECRET_KEY`, `RATE_LIMIT_ENABLED` before any app import, ensuring tests never touch production configuration or real services. |

## Consequences

### Positive

- **Fast feedback loop**: 126 tests execute in seconds (in-memory SQLite, no network). Developers can run the full suite on every save without waiting for external services.
- **High confidence per test**: Service tests exercise real SQL through SQLAlchemy, catching ORM mapping errors, constraint violations, and query bugs that pure mocks would miss.
- **Low maintenance**: Factory fixtures eliminate test data boilerplate. No complex mock setups. Adding a new service test requires only importing the factory and writing assertions.
- **No external dependencies for CI**: No PostgreSQL container, no Redis, no Docker Compose. CI can run `pytest` directly after `pip install`.
- **Parallelism-ready**: Per-test database isolation means tests can safely run in parallel (via `pytest-xdist`) without file-level or database-level conflicts.
- **Pyramid shape is healthy**: The bulk of tests (96/126 = 76%) are at the service layer where business logic lives. Pure function tests (21%) are the fastest safety net. Middleware tests (5%) cover infrastructure concerns.

### Negative

- **SQLite is not PostgreSQL**: SQLite does not enforce all PostgreSQL constraints (e.g., specific `CHECK` constraints, enum types, `JSONB` operators). If we add PostgreSQL-specific features, some tests may pass against SQLite but fail in production. Mitigation: we use standard SQLAlchemy types and avoid PostgreSQL-specific features in business logic.
- **No endpoint/router tests yet**: The current suite does not test HTTP status codes, request parsing, or response serialization at the router level. Bugs in route wiring, dependency injection, or error handling middleware will go undetected until endpoint tests are added in `tests/integration/`.
- **No E2E tests**: There is no browser-based or full-stack test that exercises the complete request lifecycle from HTTP to database and back. This is acceptable for a backend-only API but will need to be addressed when a frontend is added.
- **`auto` mode hides intent**: `pytest-asyncio`'s `auto` mode means all `async def` functions are treated as tests, even if a developer writes an async helper that is not a test. This is a minor footgun — helpers should be regular `def` or `async def` with a leading underscore and not start with `test_`.
- **Middleware tests use `TestClient` (sync wrapper)**: The middleware test functions are synchronous (`def`, not `async def`), which means they run in a different async context than service tests. This is correct behavior but could confuse developers who expect all tests to be async.

## Alternatives Considered

| Approach | Why it was rejected |
|---|---|
| **Mock-heavy unit tests** (mock every repository call) | Eliminates database dependency but creates fragile tests that break when internal implementation changes. Does not catch SQL or ORM mapping errors. High maintenance cost for marginal speed gain over in-memory SQLite. |
| **Docker-based PostgreSQL test container** (`testcontainers`) | More realistic but adds 5-10 seconds of startup time per test session and requires Docker in CI and on every developer machine. In-memory SQLite is sufficient for our current query patterns. Can be adopted later if PostgreSQL-specific features are needed. |
| **Full app `TestClient` for all tests** (including service tests) | Couples service tests to HTTP routing, middleware stack, and error handlers. A bug in middleware would fail unrelated service tests. Testing services via a minimal `db_session` fixture keeps failures localized. |
| **No isolation (shared database across tests)** | Faster (no `create_all`/`drop_all` per test) but introduces state leaks: test A's data affects test B. Debugging inter-test dependencies is extremely costly. Per-test isolation is worth the ~5ms overhead. |
| **Property-based testing** (`hypothesis`) | Powerful for finding edge cases in pure functions, but adds complexity to the test suite. We may adopt it for `security.py` functions in the future, but it is premature for the current scope. |

## Test Inventory

| Test File | Tests | Layer | DB? | Async? |
|---|---|---|---|---|
| `test_security.py` | 12 | Pure function | No | Yes (auto) |
| `test_schemas.py` | 14 | Pure function | No | Yes (auto) |
| `test_auth_service.py` | 10 | Service | In-memory SQLite | Yes |
| `test_venue_service.py` | 14 | Service | In-memory SQLite | Yes |
| `test_event_service.py` | 20 | Service | In-memory SQLite | Yes |
| `test_ticket_type_service.py` | 18 | Service | In-memory SQLite | Yes |
| `test_admin_user_service.py` | 22 | Service | In-memory SQLite | Yes |
| `test_middleware.py` | 6 | Middleware (HTTP) | No | No (sync TestClient) |
| **Total** | **116** | | | |

## Date

2026-08-15