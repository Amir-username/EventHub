## ADR-002: Use Pydantic Settings for Application Configuration

**Status:** Accepted  
**Date:** 2026-07-29  

### Context

EventHub is a multi-role platform (Customers, Admins, External Partners) with the following configuration complexity:

- **Multiple data stores:** PostgreSQL for transactional data (events, venues, tickets, reservations), Redis for caching, session storage, and rate-limiting counters.
- **External integrations:** A mocked payment provider (configurable endpoints, API keys, webhook secrets), email/SMS providers for confirmations.
- **Partner API surface:** Versioned, rate-limited public API requiring configurable throttle thresholds, JWT secrets, and versioning flags.
- **Environment variance:** Local development, CI, staging, and production each require different connection strings, credentials, and feature toggles (e.g., `MOCK_PAYMENT=true` in dev/test vs. real provider configs in prod).
- **Security requirements:** Database passwords, API keys, and JWT secrets must never be hardcoded and must be validated at startup to prevent silent failures.

We need a configuration strategy that is type-safe, validates at boot time, supports secrets via environment variables, and integrates natively with FastAPI's dependency injection system.

### Decision

We will use **Pydantic Settings (`pydantic-settings`)** as the single source of truth for all application configuration.

#### Rationale

1. **Fail-fast validation:** Pydantic validates and coerces all environment variables at import time. If `DATABASE_URL` or `PAYMENT_API_KEY` is missing or malformed, the application crashes immediately on startup with a descriptive error — not during a customer's ticket purchase.
2. **Type safety:** All configuration values are typed (`int`, `bool`, `RedisDsn`, `PostgresDsn`). This eliminates stringly-typed bugs (e.g., `POOL_SIZE="10"` being treated as a string instead of an integer).
3. **Hierarchical organization:** We will define nested models (`DatabaseSettings`, `RedisSettings`, `PaymentSettings`, `PartnerAPISettings`) to mirror our architectural boundaries, keeping related configs cohesive.
4. **Secrets management:** Pydantic Settings reads from environment variables and `.env` files, keeping secrets out of source control and allowing seamless integration with Docker, Kubernetes, and CI/CD secret injection.
5. **FastAPI integration:** Settings can be injected via `Depends(get_settings())`, enabling test overrides (e.g., swapping to a test database URL or mocked payment endpoint during integration tests).
6. **Caching:** The `get_settings()` dependency will be wrapped with `@lru_cache` to avoid re-parsing `.env` on every request, ensuring zero runtime overhead.

### Consequences

#### Positive
- **Operational safety:** Misconfigurations are caught before the server accepts traffic.
- **Developer experience:** Autocomplete and type checking work across the codebase for all config values.
- **Testability:** Easy to override specific settings for unit/integration tests without monkey-patching `os.environ`.
- **12-factor compliance:** Configuration is strictly separated from code via environment variables.

#### Negative / Trade-offs
- **Startup dependency:** The app will refuse to start if any required env var is missing, which requires discipline in deployment pipelines.
- **Learning curve:** Team members must understand Pydantic v2 field aliases and nested model syntax.
- **Not runtime-reloadable:** Changing a setting requires a process restart (acceptable for our deployment model).

### Alternatives Considered

| Alternative | Why Rejected |
|-------------|--------------|
| **Raw `os.environ` / `python-dotenv` alone** | No type validation, no autocomplete, silent failures on missing keys. Too risky for payment-adjacent flows. |
| **YAML/JSON config files** | Secrets would need to be committed or mounted separately. Adds file I/O and parsing complexity without validation benefits. |
| **Django-style `settings.py`** | Hardcoded Python files encourage committing secrets and make per-environment overrides cumbersome. |
| **HashiCorp Vault / AWS Secrets Manager direct SDK calls** | Overkill for current scale. We will inject secrets via env vars (populated by the orchestrator), keeping the app simple and cloud-agnostic. |

### Implementation Notes

- Define a `Settings` class in `app/config.py` with nested models for each subsystem.
- Use `SettingsConfigDict(env_nested_delimiter="__")` to allow `REDIS__HOST`, `DATABASE__POOL_SIZE`, etc.
- Cache the settings instance with `@lru_cache` in the factory function.
- Inject settings via FastAPI `Depends()` in routers, services, and external API clients.
- Commit a `.env.example` file (without real secrets) to document required variables for new developers.