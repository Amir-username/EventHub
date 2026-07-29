# ADR 001: Backend Framework — FastAPI

## Status

Accepted

## Context

EventHub requires a backend framework that can support:

1. A **public-facing REST API** for customers to browse events, reserve tickets, and complete payments.
2. A **versioned, rate-limited external API** for third-party partners to pull event data.
3. **High concurrency** during ticket-release spikes (flash sales, popular events).
4. **Strict data validation** for financial-adjacent operations (ticket inventory, payment payloads).
5. **Rapid development** with a small team, while maintaining long-term maintainability.

We evaluated **Django + DRF**, **Flask**, **Node.js/Express**, and **FastAPI**.

## Decision

We will use **FastAPI** as the primary backend framework for EventHub.

## Consequences

### Positive

- **Native async support**: Built on Starlette and Uvicorn, FastAPI handles I/O-bound operations (database queries, mocked payment provider calls, email confirmations) concurrently without blocking the event loop. This directly addresses flash-sale traffic spikes.
- **Automatic OpenAPI documentation**: The external partner API will be self-documenting via `/docs` and `/redoc`, reducing integration friction and support overhead.
- **Pydantic-driven validation**: Request/response models enforce schemas at the edge. Malformed ticket reservations or payment requests are rejected before reaching business logic, reducing bugs and security surface area.
- **Dependency injection system**: Auth, database sessions, rate-limiting middleware, and payment service clients are injected cleanly. This makes unit testing straightforward and allows swapping implementations (e.g., mocked payment → Stripe) with zero endpoint changes.
- **Type hints as documentation**: The entire codebase is self-documenting via Python type annotations, improving onboarding speed for new developers and API consumers.
- **Background task support**: Non-blocking tasks (sending confirmation emails, publishing analytics events) can be triggered directly from endpoints without requiring a separate job queue for simple use cases.

### Negative

- **Smaller ecosystem than Django**: FastAPI is younger. While the core ecosystem is mature, some niche Django packages (e.g., advanced admin panels, CMS plugins) do not have direct equivalents. We will build admin functionality as a separate service or use an existing admin template.
- **Less "batteries-included"**: Unlike Django, FastAPI does not ship with an ORM, admin interface, or user management out of the box. We must explicitly choose and integrate SQLAlchemy (async), Alembic for migrations, and a separate auth library (e.g., `python-jose` + `passlib`).
- **Team learning curve**: Developers familiar only with synchronous Flask or Django may need time to adjust to `async/await` patterns and Pydantic model design.

## Alternatives Considered

| Framework | Why it was rejected |
|---|---|
| **Django + DRF** | Excellent for monolithic apps with admin panels, but its synchronous-by-default request handling and heavier ORM are suboptimal for high-concurrency ticket booking. Async Django (4.2+) is still maturing. |
| **Flask** | Lightweight and familiar, but lacks native async support, automatic validation, and OpenAPI generation. We would need to manually glue together Marshmallow, Flask-RESTX, and an ASGI server, increasing maintenance burden. |
| **Node.js / Express** | Strong async I/O, but JavaScript's lack of static typing (without TypeScript) increases risk in financial-adjacent domains. TypeScript + NestJS was a close contender, but the team has stronger Python expertise, and Pydantic's validation ergonomics are superior to class-validator. |


## Date

2026-07-29