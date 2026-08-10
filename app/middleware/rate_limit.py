import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

# ── Backend interface (swap with Redis implementation later) ──────────


class _RateLimitBackend:
    """Abstract-style base for rate-limit storage backends.

    Each method must be implemented by concrete backends.
    When a Redis backend is ready, create ``RedisRateLimitBackend``
    with the same interface and pass it to ``RateLimitMiddleware``.
    """

    def is_rate_limited(self, key: str, max_requests: int, window_seconds: int) -> bool:
        raise NotImplementedError

    def cleanup(self, window_seconds: int) -> None:
        """Remove expired entries. Called periodically."""
        raise NotImplementedError


class InMemoryRateLimitBackend(_RateLimitBackend):
    """Naive in-memory rate-limit backend.

    Stores ``{key: [timestamp, ...]}`` in a plain dict.
    Suitable for single-process dev / testing.
    **Not** suitable for multi-worker production (each worker has
    its own dict — replace with ``RedisRateLimitBackend`` for prod).
    """

    def __init__(self) -> None:
        self._store: dict[str, list[float]] = {}
        self._last_cleanup: float = 0.0

    def is_rate_limited(self, key: str, max_requests: int, window_seconds: int) -> bool:
        now = time.monotonic()
        cutoff = now - window_seconds

        # Lazy cleanup every ~60 s to prevent unbounded growth
        if now - self._last_cleanup > 60:
            self.cleanup(window_seconds)
            self._last_cleanup = now

        timestamps = self._store.setdefault(key, [])

        # Discard expired timestamps
        while timestamps and timestamps[0] < cutoff:
            timestamps.pop(0)

        if len(timestamps) >= max_requests:
            return True

        timestamps.append(now)
        return False

    def cleanup(self, window_seconds: int) -> None:
        cutoff = time.monotonic() - window_seconds
        for key in list(self._store):
            self._store[key] = [t for t in self._store[key] if t >= cutoff]
            if not self._store[key]:
                del self._store[key]


# ── Middleware ──────────────────────────────────────────────────────────


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Fixed-window rate limiter keyed on client IP.

    Configuration:
        - ``RATE_LIMIT_MAX_REQUESTS`` — max requests per window (default 100)
        - ``RATE_LIMIT_WINDOW_SECONDS`` — window duration (default 60)
        - ``RATE_LIMIT_ENABLED`` — toggle on/off (default True)

    The backend defaults to :class:`InMemoryRateLimitBackend`.
    Replace it with a Redis-backed class for multi-worker deployments.
    """

    def __init__(
        self,
        app,
        backend: _RateLimitBackend | None = None,
        max_requests: int = 100,
        window_seconds: int = 60,
        enabled: bool = True,
    ) -> None:
        super().__init__(app)
        self.backend = backend or InMemoryRateLimitBackend()
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.enabled = enabled

    async def dispatch(self, request: Request, call_next) -> Response:
        if not self.enabled:
            return await call_next(request)

        # Skip non-HTTP (e.g. lifespan)
        client_ip = request.client.host if request.client else "unknown"
        key = f"rate_limit:{client_ip}"

        if self.backend.is_rate_limited(key, self.max_requests, self.window_seconds):
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded. Try again later.",
                    "retry_after": self.window_seconds,
                },
                headers={"Retry-After": str(self.window_seconds)},
            )

        return await call_next(request)
