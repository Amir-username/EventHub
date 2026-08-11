# ADR 008: Middleware Ordering Strategy

## Status

Accepted

## Context

EventHub uses Starlette's `add_middleware()` to layer middleware around the FastAPI application. Starlette stacks middlewares in **reverse registration order** — the last `add_middleware()` call becomes the outermost layer that runs first on incoming requests.

As the middleware stack grew (RequestID → Timing → GZip → CORS → RateLimit), the ordering became a meaningful architectural decision that affects security, observability, performance, and correctness.

### Key Constraints

- **Rate limiting** should reject abusive requests as early as possible, before any other processing work is done.
- **CORS** must add `Access-Control-*` headers to **all** responses, including 429s and 5xx errors, so browsers can read error responses.
- **GZip compression** is CPU-expensive; it should not be included in application timing measurements.
- **Timing** should measure the application's business logic, not infrastructure overhead (compression, CORS header injection).
- **Request ID** should be available to all inner layers via `request.state.request_id` for potential future logging.

## Decision

Middlewares are registered in the following order in `app/factory.py`, which produces the illustrated execution flow:

```
Registration order (in code)     Execution order (at runtime)
───────────────────────────     ──────────────────────────────
1. RequestIDMiddleware       ⑤  ← innermost (closest to route)
2. TimingMiddleware          ④
3. GZipMiddleware            ③
4. CORSMiddleware            ②
5. RateLimitMiddleware       ①  ← outermost (runs first)
```

### Onion Model

```
Incoming request →
  ┌─ ① RateLimit ─── reject early if 429
  │  ┌─ ② CORS ─────── preflight handling, add cors headers
  │  │  ┌─ ③ GZip ───── compress response on the way out
  │  │  │  ┌─ ④ Timing ── start perf_counter
  │  │  │  │  ┌─ ⑤ RequestID ── assign X-Request-ID
  │  │  │  │  │  ┌─ Route Handler
  │  │  │  │  │  └─
  │  │  │  │  └─ add X-Request-ID to response
  │  │  │  └─ stop timer, add X-Response-Time
  │  │  └─ compress body, add Content-Encoding
  │  └─ add Access-Control-* headers
  └─ (pass through or 429)
→ Outgoing response
```

### Rationale Per Layer

| Position | Middleware | Why here |
|---|---|---|
| ① Outermost | **RateLimit** | Rejects requests before any other work is done. No point parsing CORS, compressing, or assigning IDs to a request that will receive a 429. Protects all inner layers from abuse and saves CPU. |
| ② | **CORS** | Must run outside all other middleware so that `Access-Control-*` headers are added to **every** response — including 429s from RateLimitMiddleware and 5xx errors. Browsers require CORS headers to be present even on error responses to allow JavaScript to read them. |
| ③ | **GZip** | Placed inside CORS so `Content-Encoding: gzip` is visible to the browser (CORS doesn't strip it). Placed outside Timing so compression cost is **not** included in `X-Response-Time` — we want to measure application logic, not gzip overhead. |
| ④ | **Timing** | Measures the pure application processing time (route handler + business logic + database queries). Excludes both GZip compression (CPU-heavy, not app logic) and CORS header injection (infrastructure concern). |
| ⑤ Innermost | **RequestID** | Closest to the route handler so `request.state.request_id` is available to all downstream code (dependencies, services, future loggers). Runs last on the response path, so it doesn't interfere with any other middleware's timing or headers. |

## Consequences

### Positive

- **Security-first**: Rate limiting is the outermost gate. Abusive traffic is rejected before consuming any application resources.
- **Accurate timing**: `X-Response-Time` reflects actual business logic duration, not infrastructure overhead.
- **CORS compliance**: All responses — including errors from any layer — carry proper `Access-Control-*` headers, so browser-based clients can handle 429 and 5xx responses correctly.
- **Clean separation of concerns**: Each layer has a single responsibility and doesn't pollute measurements or headers of adjacent layers.
- **Observability**: Both `X-Request-ID` and `X-Response-Time` are set independently without interference, making them reliable for logging and monitoring.

### Negative

- **Rate limit counts compressed responses**: If GZip is later moved outside RateLimit (unlikely), rate limit counters would need adjustment. Currently this is not an issue since RateLimit rejects before GZip runs.
- **BaseHTTPMiddleware overhead**: RequestID, Timing, and RateLimit all use `BaseHTTPMiddleware`, which wraps the response in a streaming wrapper. This adds a small latency overhead (~1-2ms). If this becomes measurable, RateLimit and Timing can be migrated to pure ASGI middleware (no wrapper overhead) without changing the ordering.
- **Order is non-obvious**: Developers unfamiliar with Starlette's reverse stacking may find it surprising that `RateLimitMiddleware` (registered last) runs first. The comment in `factory.py` and this ADR mitigate that confusion.

## Middleware Inventory

| Middleware | Type | Header(s) Set | Config Source |
|---|---|---|---|
| `RateLimitMiddleware` | Custom (BaseHTTPMiddleware) | `Retry-After` (on 429) | `rate_limit_enabled`, `rate_limit_max_requests`, `rate_limit_window_seconds` |
| `CORSMiddleware` | FastAPI built-in | `Access-Control-Allow-*` | `environment`, `cors_origins` |
| `GZipMiddleware` | Starlette built-in | `Content-Encoding` | `minimum_size=1000` (hardcoded) |
| `TimingMiddleware` | Custom (BaseHTTPMiddleware) | `X-Response-Time` | None (always active) |
| `RequestIDMiddleware` | Custom (BaseHTTPMiddleware) | `X-Request-ID` | None (always active) |

## Date

2026-08-11
