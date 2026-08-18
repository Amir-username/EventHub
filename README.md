# EventHub

A production-grade async REST API for event ticketing, built with **FastAPI**, **SQLAlchemy** (async), and **PostgreSQL**.

## Overview

EventHub provides a backend platform for creating events, managing venues, defining ticket types with pricing and sales windows, and handling user authentication with role-based access control. The system is designed to support high-concurrency ticket sales with proper inventory management, idempotent reservations, and webhook-driven payment processing.

### Tech Stack

| Layer | Technology |
|---|---|
| Framework | FastAPI (Starlette + Uvicorn) |
| Language | Python 3.12+ |
| Database | PostgreSQL (via asyncpg) |
| ORM | SQLAlchemy 2.0 (async) |
| Migrations | Alembic |
| Validation | Pydantic v2 + pydantic-settings |
| Auth | Argon2 password hashing, JWT RS256 (asymmetric) |
| Linting | Ruff (linter + formatter) |
| Testing | pytest + pytest-asyncio (116 tests) |
| Containerization | Docker Compose (API + PostgreSQL + Redis + pgAdmin) |

## Architecture

The codebase follows a **layered architecture** with clear separation of concerns:

```
HTTP Request
    │
    ▼
┌─────────────┐
│  Middleware   │  RequestID → Timing → GZip → CORS → RateLimit
└──────┬──────┘
       ▼
┌─────────────┐
│   Routers    │  app/api/ — HTTP endpoints, auth dependencies
└──────┬──────┘
       ▼
┌─────────────┐
│   Services   │  app/services/ — business logic, validation, orchestration
└──────┬──────┘
       ▼
┌─────────────┐
│ Repositories │  app/repositories/ — data access, SQLAlchemy queries
└──────┬──────┘
       ▼
┌─────────────┐
│   Models     │  app/models/ — SQLAlchemy ORM models
└──────┬──────┘
       ▼
   PostgreSQL
```

Each layer is independently testable. Services contain all business rules; repositories handle SQL; routers handle HTTP concerns only.

## Project Structure

```
EventHub/
├── app/
│   ├── api/              # API routes (auth, events, venues, ticket types, admin users)
│   ├── config.py         # Pydantic Settings (loads from .env)
│   ├── core/security.py  # Password hashing (Argon2) + JWT tokens (RS256)
│   ├── db/database.py    # Async engine, session factory, Base class
│   ├── factory.py        # FastAPI app factory with middleware + router registration
│   ├── main.py           # App entrypoint with health checks
│   ├── middleware/       # RequestID, Timing, RateLimit middleware
│   ├── models/           # SQLAlchemy models (User, Venue, Event, TicketType, ...)
│   ├── repositories/     # Data access layer (User, Venue, Event, TicketType repos)
│   ├── schemas/          # Pydantic request/response schemas
│   ├── seed.py           # Database seeder (idempotent)
│   └── services/         # Business logic (Auth, Venue, Event, TicketType, AdminUser)
├── alembic/              # Database migrations
├── adr/                  # Architecture Decision Records (9 ADRs)
├── docker/               # Dockerfiles (api, worker placeholder)
├── scripts/              # RSA key generation, admin creation, password hashing
├── tests/
│   ├── conftest.py       # Shared fixtures, factory pattern, in-memory SQLite
│   └── unit/             # 116 tests across 8 test modules
├── docker-compose.yml
├── alembic.ini
├── pyproject.toml
└── .pre-commit-config.yaml
```

## API Endpoints

### Authentication (`/auth`)

| Method | Path | Description | Auth |
|---|---|---|---|
| POST | `/auth/register` | Register a new customer | None |
| POST | `/auth/login` | Login with email + password | None |
| POST | `/auth/token` | OAuth2-compatible token endpoint | None |
| POST | `/auth/refresh` | Refresh access token | None |
| GET | `/auth/me` | Get current user profile | Bearer |

### Venues (`/venues`)

| Method | Path | Description | Auth |
|---|---|---|---|
| GET | `/venues/public` | List all venues (public) | None |
| GET | `/venues/public/{id}` | Get a venue (public) | None |
| GET | `/venues` | List all venues (admin) | Admin |
| GET | `/venues/{id}` | Get a venue (admin) | Admin |
| POST | `/venues` | Create a venue | Admin |
| PATCH | `/venues/{id}` | Update a venue | Admin |
| DELETE | `/venues/{id}` | Delete a venue | Admin |

### Events (`/events`)

| Method | Path | Description | Auth |
|---|---|---|---|
| GET | `/events/public` | List published events | None |
| GET | `/events/public/{id}` | Get a published event | None |
| GET | `/events` | List all events incl. drafts | Admin |
| GET | `/events/{id}` | Get any event by ID | Admin |
| POST | `/events` | Create an event | Admin |
| PATCH | `/events/{id}` | Update an event | Admin |
| DELETE | `/events/{id}` | Delete an event | Admin |

### Ticket Types (`/ticket-types`)

| Method | Path | Description | Auth |
|---|---|---|---|
| GET | `/ticket-types/public/events/{event_id}` | List ticket types for a published event | None |
| GET | `/ticket-types/public/{id}` | Get a ticket type (public) | None |
| GET | `/ticket-types` | List all ticket types | Admin |
| GET | `/ticket-types/{id}` | Get a ticket type | Admin |
| POST | `/ticket-types` | Create a ticket type | Admin |
| PATCH | `/ticket-types/{id}` | Update a ticket type | Admin |
| DELETE | `/ticket-types/{id}` | Delete a ticket type | Admin |

### Admin Users (`/admin/users`)

| Method | Path | Description | Auth |
|---|---|---|---|
| GET | `/admin/users` | List users (filter by role, search) | Admin |
| GET | `/admin/users/{id}` | Get a user | Admin |
| POST | `/admin/users` | Create a user (any role) | Admin |
| PATCH | `/admin/users/{id}` | Update a user | Admin |
| DELETE | `/admin/users/{id}` | Delete a user (self-delete blocked) | Admin |

### Health Checks

| Method | Path | Description |
|---|---|---|
| GET | `/healthz` | Liveness check |
| GET | `/db-health` | Database connectivity check |

## Data Models

```
User ──┬──< Venue ──< Event ──< TicketType ──< Reservation ──< Order
       │              │                                        │
       │              └── created_by → User                   │
       │                                                       │
       └── created_by → User         WebhookEvent              │
                                                               │
                               ApiKey                    provider_reference
                               FeatureFlag
```

Key models implemented with full SQLAlchemy definitions:

- **User** — email, hashed password, role (customer/admin)
- **Venue** — name, address, city, capacity
- **Event** — title, description, venue, time range, status (draft/published/cancelled)
- **TicketType** — name, price (cents), currency, quantities (total/reserved/sold), sales window
- **Reservation** — user, ticket type, quantity, status (pending/confirmed/expired/cancelled), idempotency key, expiry
- **Order** — reservation, amount, status (pending/paid/failed/refunded), provider reference
- **ApiKey** — partner name, hashed key, scopes, rate limit tier
- **FeatureFlag** — key, enabled, rollout config
- **WebhookEvent** — provider event ID, payload, processed timestamp

## Getting Started

### Prerequisites

- Python 3.12+
- PostgreSQL 17+
- Docker & Docker Compose (optional, for containerized setup)

### 1. Clone and Install

```bash
git clone https://github.com/Amir-username/EventHub.git
cd EventHub

# Install dependencies
pip install -e ".[dev]"

# Or with uv
uv sync
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your database URL, secret key, etc.
```

### 3. Generate RSA Keys

```bash
python scripts/generate_rsa_keys.py
```

### 4. Run Migrations

```bash
alembic upgrade head
```

### 5. Create Admin User

```bash
python scripts/create_admin.py
```

### 6. (Optional) Seed the Database

```bash
python -m app.seed
```

### 7. Run the Server

```bash
fastapi dev app/main.py
```

The API will be available at `http://localhost:8000`. Interactive docs at `/docs`.

### Docker Compose (Alternative)

```bash
docker compose up --build
```

This starts the API, PostgreSQL, Redis, and pgAdmin. RSA keys are mounted from the `./keys/` directory.

## Testing

### Test Strategy

The project follows a **modified test pyramid** (see [ADR 009](adr/009_test_pyramid_strategy.md)):

- **Layer 1 — Pure functions** (26 tests): Password hashing, JWT tokens, Pydantic schema validators. No database, microsecond execution.
- **Layer 2 — Service layer** (84 tests): Business logic tested against in-memory SQLite with factory fixtures. Real ORM queries, per-test DB isolation.
- **Layer 3 — Middleware** (6 tests): HTTP-level tests using isolated Starlette apps.

### Running Tests

```bash
# Run all 116 tests
pytest

# Run a specific module
pytest tests/unit/test_event_service.py

# Run with coverage
pytest --cov=app tests/

# Verbose output
pytest -v
```

Tests use **in-memory SQLite** for zero-configuration isolation — no PostgreSQL or Docker needed for the test suite.

## Middleware Stack

Middleware executes in this order (outermost first):

1. **RateLimitMiddleware** — rejects abusive requests early (429 + Retry-After header)
2. **CORSMiddleware** — adds Access-Control headers to all responses including errors
3. **GZipMiddleware** — compresses responses over 1000 bytes
4. **TimingMiddleware** — measures app logic time, sets `X-Response-Time` header
5. **RequestIDMiddleware** — assigns/reuses `X-Request-ID` (UUID v4)

See [ADR 008](adr/008_middleware_ordering_strategy.md) for the full rationale.

## Architecture Decision Records

All key architectural decisions are documented in the `adr/` directory:

| # | Decision | Date |
|---|---|---|
| 001 | Backend Framework — FastAPI | 2026-07-29 |
| 002 | Use Pydantic Settings for Configuration | 2026-07-29 |
| 003 | Application Factory Pattern | — |
| 004 | PostgreSQL as Primary Database | 2026-07-30 |
| 005 | Async SQLAlchemy for Database Access | 2026-07-30 |
| 006 | JWT Signing Algorithm — RS256 over HS256 | 2026-08-04 |
| 007 | Pagination Strategy — Offset/Limit | 2026-08-08 |
| 008 | Middleware Ordering Strategy | 2026-08-11 |
| 009 | Test Pyramid Strategy | 2026-08-15 |

## What's Done

### Core Infrastructure
- [x] FastAPI application with factory pattern and layered architecture
- [x] Async SQLAlchemy 2.0 with PostgreSQL (asyncpg) and Alembic migrations
- [x] Pydantic Settings configuration loading from `.env`
- [x] Docker Compose setup (API + PostgreSQL + Redis + pgAdmin)
- [x] Multi-stage Dockerfile for production builds
- [x] Ruff linter + formatter with pre-commit hooks

### Authentication & Authorization
- [x] RS256 JWT token authentication (asymmetric RSA key pair)
- [x] Argon2 password hashing with rehash detection
- [x] Access token (30 min) + refresh token (4 days) flow
- [x] Role-based access control (CUSTOMER / ADMIN)
- [x] OAuth2-compatible token endpoint

### Middleware
- [x] Request ID middleware (UUID v4, client header echo)
- [x] Response timing middleware (`X-Response-Time`)
- [x] Fixed-window rate limiting (IP-keyed, configurable, toggleable)
- [x] CORS middleware (permissive in dev, strict in production)
- [x] GZip compression
- [x] Documented middleware ordering strategy (ADR 008)

### Data Models
- [x] User, Venue, Event, TicketType (fully implemented with CRUD)
- [x] Reservation, Order (model defined, not yet wired to services)
- [x] ApiKey, FeatureFlag, WebhookEvent (model defined, not yet wired)

### API Routes
- [x] Auth: register, login, refresh, current user profile
- [x] Venues: full CRUD (public + admin endpoints)
- [x] Events: full CRUD with draft/published status, public filtering
- [x] Ticket Types: full CRUD with sales window validation
- [x] Admin Users: full CRUD with email uniqueness, self-delete guard
- [x] Health check endpoints

### Business Logic
- [x] Cross-field validation (ends_at > starts_at, sales_end_at > sales_start_at)
- [x] Draft-event visibility guards on public endpoints
- [x] Venue existence checks on event create/update
- [x] Email uniqueness enforcement on user create and update
- [x] Self-delete prevention for admin accounts
- [x] Offset/limit pagination with search filtering

### Testing
- [x] 116 unit/integration tests across 8 test modules
- [x] Factory fixture pattern for test data creation
- [x] Per-test database isolation (in-memory SQLite, create_all/drop_all)
- [x] Middleware isolation testing (minimal Starlette apps)
- [x] Test pyramid strategy documented (ADR 009)

### Developer Tooling
- [x] RSA key generation script (with self-test)
- [x] Admin user creation script
- [x] Password hashing utility script
- [x] Idempotent database seeder
- [x] 9 Architecture Decision Records

## What's Next

### High Priority — Core Ticketing
- [ ] **Reservation service** — reserve tickets with idempotency key, expiry countdown, inventory deduction
- [ ] **Order service** — create orders from confirmed reservations, track payment status
- [ ] **Payment integration** — mock payment provider, webhook handler for payment callbacks
- [ ] **Reservation + Order repositories** — data access layer for the ticketing models
- [ ] **Reservation + Order API routes** — customer-facing endpoints for browsing and reserving tickets

### High Priority — Testing
- [ ] **Integration tests for API routes** — test full HTTP request lifecycle via TestClient (status codes, response schemas, error formats)
- [ ] **Reservation and order service tests** — test idempotency, expiry, inventory race conditions

### Medium Priority — API Features
- [ ] **Cursor-based pagination** — migrate from offset/limit to cursor-based for stable pagination on large datasets (deferred from ADR 007)
- [ ] **External partner API** — versioned, API-key-authenticated endpoints for third-party event data access
- [ ] **API key management** — CRUD endpoints for partner API keys, scope-based access control
- [ ] **Feature flag service** — runtime feature toggles with rollout percentages
- [ ] **Webhook event processing** — receive and process payment provider webhooks

### Medium Priority — Infrastructure
- [ ] **Redis integration** — rate limiting backend, session caching, potential pub/sub for events
- [ ] **Background worker** — process webhooks, send confirmation emails, cleanup expired reservations
- [ ] **PostgreSQL-specific test containers** — for testing PG-specific features when needed
- [ ] **CI/CD pipeline** — GitHub Actions for lint, test, build, and deploy

### Low Priority — Operations
- [ ] **Structured logging** — request ID correlation, JSON-formatted logs
- [ ] **Monitoring and alerting** — Prometheus metrics, Grafana dashboards
- [ ] **Email notifications** — confirmation emails, event reminders
- [ ] **Frontend** — customer-facing web or mobile UI for browsing and booking events

## License

This project is proprietary. All rights reserved.