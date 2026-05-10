"""FastAPI entrypoint."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.api.v1 import v1
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.core.telemetry import init_telemetry
from app.middleware.security import (
    BodySizeLimitMiddleware,
    RequestContextMiddleware,
    SecurityHeadersMiddleware,
)

log = get_logger("kynara")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    init_telemetry(app)
    log.info("kynara.startup", env=settings.env)
    yield
    log.info("kynara.shutdown")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Kynara API",
        version="0.1.0",
        description="AI Agent permission system — control plane.",
        lifespan=lifespan,
        openapi_url="/api/v1/openapi.json",
        docs_url="/api/v1/docs",
        redoc_url="/api/v1/redoc",
        redirect_slashes=False,
    )

    # Rate limiting
    limiter = Limiter(key_func=get_remote_address, default_limits=[settings.rate_limit_anonymous])
    app.state.limiter = limiter

    # Middlewares (order matters — outermost last)
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=1_000_000)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    app.include_router(v1)

    @app.get("/metrics", include_in_schema=False)
    def metrics():
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    @app.exception_handler(RateLimitExceeded)
    async def _ratelimit_handler(request, exc):
        from starlette.responses import JSONResponse
        return JSONResponse({"detail": "rate limit exceeded"}, status_code=429)

    return app


app = create_app()
