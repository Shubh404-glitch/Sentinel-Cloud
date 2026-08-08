"""AuthContextMiddleware (Section 9: Authentication).

What this middleware deliberately does NOT do: fully verify the JWT or
API key. Full verification needs a database round trip (to re-fetch the
user/API key and check it's still active) via a request-scoped
AsyncSession, and FastAPI's dependency-injection system -- not ASGI
middleware -- is where request-scoped, `Depends`-based resources like
that session are normally created and cleaned up. Doing full auth in
middleware would mean either duplicating that session-management logic
outside of `Depends`, or every route (including the public `/health`
check) paying for a DB round trip whether or not it needs
authentication. That verification stays in api/deps/auth.py, which is
the actual enforcement point.

What this middleware does do, cheaply and statelessly, before any route
or dependency runs:

  1. Rejects requests that present both a Bearer token and an X-API-Key
     header (Section 15: a request should authenticate as exactly one
     principal) -- the same check `get_current_principal` makes, but
     here it short-circuits before any DB session is even opened.
  2. Rejects a Bearer token that isn't even shaped like a JWT (must
     contain two `.` separators) before it reaches jose's decoder.
  3. Stamps a per-request correlation id (`request.state.request_id`,
     also echoed back as `X-Request-ID`) that later audit-logging
     (Section 10: AuditLogEntry) can use to correlate a logged action
     with the request that produced it, without threading an id through
     every function signature by hand.
"""
from __future__ import annotations

import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class AuthContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request.state.request_id = uuid.uuid4().hex

        auth_header = request.headers.get("authorization")
        api_key_header = request.headers.get("x-api-key")

        if auth_header and api_key_header:
            return JSONResponse(
                status_code=400,
                content={"detail": "present either a Bearer token or an X-API-Key header, not both"},
                headers={"X-Request-ID": request.state.request_id},
            )

        if auth_header and auth_header.lower().startswith("bearer "):
            token = auth_header[len("bearer "):].strip()
            if token.count(".") != 2:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "malformed bearer token"},
                    headers={"X-Request-ID": request.state.request_id, "WWW-Authenticate": "Bearer"},
                )

        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response
