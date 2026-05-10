"""Security middleware — headers, request IDs, body-size cap."""
from __future__ import annotations

import uuid
import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import request_id_ctx

_dbg = logging.getLogger("kynara.redirect_debug")


class RedirectDebugMiddleware(BaseHTTPMiddleware):
    """Temporary: log every 3xx so we can find what is issuing the redirect."""
    async def dispatch(self, request: Request, call_next) -> Response:
        resp = await call_next(request)
        if resp.status_code in (301, 302, 307, 308):
            _dbg.warning(
                "REDIRECT_DETECTED method=%s path=%s status=%s location=%s",
                request.method,
                request.url.path,
                resp.status_code,
                resp.headers.get("location", "<none>"),
            )
        return resp


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        resp = await call_next(request)
        resp.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        resp.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
        resp.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data:; "
            "script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        )
        return resp


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex
        token = request_id_ctx.set(rid)
        try:
            resp = await call_next(request)
            resp.headers["x-request-id"] = rid
            return resp
        finally:
            request_id_ctx.reset(token)


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_bytes: int = 1_000_000):
        super().__init__(app)
        self.max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next) -> Response:
        cl = request.headers.get("content-length")
        if cl and int(cl) > self.max_bytes:
            return Response("Payload too large", status_code=413)
        return await call_next(request)
