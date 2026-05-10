"""Data-residency enforcement middleware.

If an org has ``residency_strict=true`` and the deployment region does not
match the org's chosen region, the middleware refuses every request with HTTP
451 ("Unavailable For Legal Reasons"). This guarantees that a misconfigured
DNS / global-load-balancer cannot accidentally route an EU-pinned tenant's
traffic through a US data centre.

Routing should be handled at the edge (Route 53 latency-based or geo-pinned
records); this middleware is the last line of defence.
"""
from __future__ import annotations

import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class ResidencyMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, deployment_region: str | None = None) -> None:
        super().__init__(app)
        self.region = deployment_region or os.environ.get("KYNARA_REGION", "us-east-1")

    async def dispatch(self, request: Request, call_next):
        # Lightweight: only apply once we have a principal-resolved org.
        org = getattr(request.state, "org", None)
        if org is not None and getattr(org, "residency_strict", False):
            if org.region and org.region != self.region:
                return JSONResponse(
                    status_code=451,
                    content={
                        "error": "residency_violation",
                        "message": (
                            f"Organization is pinned to region '{org.region}', "
                            f"but request reached deployment region '{self.region}'. "
                            f"Re-resolve via the regional endpoint."
                        ),
                        "expected_region": org.region,
                        "actual_region": self.region,
                    },
                )
        return await call_next(request)
