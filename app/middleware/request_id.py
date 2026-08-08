import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

HEADER_NAME = "X-Request-ID"


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Assigns a unique request ID to every incoming HTTP request.

    - If the client sends an ``X-Request-ID`` header, it is reused (useful
      when an upstream proxy or load balancer already generated one).
    - Otherwise a new UUID4 is generated.
    - The ID is stored on ``request.state.request_id`` so any downstream
      code (deps, services, loggers) can access it.
    - The response always includes the ``X-Request-ID`` header.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get(HEADER_NAME) or str(uuid.uuid4())
        request.state.request_id = request_id
        response: Response = await call_next(request)
        response.headers[HEADER_NAME] = request_id
        return response
