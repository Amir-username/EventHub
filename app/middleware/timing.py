import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

HEADER_NAME = "X-Response-Time"


class TimingMiddleware(BaseHTTPMiddleware):
    """Measures and reports the total processing time of each HTTP request.

    Uses ``time.perf_counter`` for high-resolution timing.
    The elapsed time is appended to the response as the
    ``X-Response-Time`` header in milliseconds (e.g. ``12.34ms``).
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()
        response: Response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        response.headers[HEADER_NAME] = f"{elapsed_ms:.2f}ms"
        return response
