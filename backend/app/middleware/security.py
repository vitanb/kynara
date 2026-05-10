"""Security middleware — headers, request IDs, body-size cap, debug CORS."""
from __future__ import annotations

import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import get_logger, request_id_ctx

log = get_logger("kynara.middleware")


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


class DebugCORSMiddleware(BaseHTTPMiddleware):
    """
    Drop-in replacement for CORSMiddleware that logs every step of the
    CORS decision and handles preflight OPTIONS requests explicitly.

    This makes it impossible to miss a mismatch between what the browser
    sends and what the server expects — every header value is logged at INFO
    so it shows up in Railway logs regardless of LOG_LEVEL setting.
    """

    def __init__(self, app, allow_origins: list[str]):
        super().__init__(app)
        self.allow_origins = [o.rstrip("/") for o in allow_origins]

    def _origin_allowed(self, origin: str | None) -> bool:
        if not origin:
            return False
        return origin.rstrip("/") in self.allow_origins

    async def dispatch(self, request: Request, call_next) -> Response:
        origin = request.headers.get("origin", "")
        method = request.method
        path = request.url.path

        # Always log every cross-origin request so we have a full trace
        log.info(
            "cors.request",
            method=method,
            path=path,
            origin=origin or "<none>",
            allow_origins=self.allow_origins,
            origin_allowed=self._origin_allowed(origin),
            access_control_request_method=request.headers.get("access-control-request-method", ""),
            access_control_request_headers=request.headers.get("access-control-request-headers", ""),
            host=request.headers.get("host", ""),
            x_forwarded_for=request.headers.get("x-forwarded-for", ""),
            x_forwarded_proto=request.headers.get("x-forwarded-proto", ""),
        )

        # --- Preflight (OPTIONS) ---
        if method == "OPTIONS" and origin:
            allowed = self._origin_allowed(origin)
            log.info(
                "cors.preflight",
                origin=origin,
                allowed=allowed,
                reason="origin_not_in_allow_list" if not allowed else "ok",
            )

            if not allowed:
                return Response(
                    content=f"CORS: origin '{origin}' not allowed. Allowed: {self.allow_origins}",
                    status_code=403,
                    media_type="text/plain",
                )

            # Return a proper preflight response
            headers = {
                "Access-Control-Allow-Origin": origin,
                "Access-Control-Allow-Credentials": "true",
                "Access-Control-Allow-Methods": "GET, POST, PUT, PATCH, DELETE, OPTIONS",
                "Access-Control-Allow-Headers": (
                    "Authorization, Content-Type, X-Request-ID, "
                    "Accept, Origin, X-Requested-With"
                ),
                "Access-Control-Max-Age": "600",
                "Vary": "Origin",
            }
            log.info("cors.preflight_response", status=200, headers=dict(headers))
            return Response(status_code=200, headers=headers)

        # --- Actual request ---
        resp = await call_next(request)

        if origin and self._origin_allowed(origin):
            resp.headers["Access-Control-Allow-Origin"] = origin
            resp.headers["Access-Control-Allow-Credentials"] = "true"
            resp.headers["Access-Control-Expose-Headers"] = "X-Request-ID"
            resp.headers["Vary"] = "Origin"
            log.info(
                "cors.response_headers_added",
                method=method,
                path=path,
                origin=origin,
                status=resp.status_code,
            )
        elif origin:
            log.warning(
                "cors.origin_blocked",
                method=method,
                path=path,
                origin=origin,
                allow_origins=self.allow_origins,
            )

        return resp
