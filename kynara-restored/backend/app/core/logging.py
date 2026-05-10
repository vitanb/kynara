"""Structured JSON logging with request/trace correlation.

Every log line emitted by Kynara is a single JSON object, enabling direct ingestion by
Datadog, Splunk, Loki, or any SIEM. Log records pick up `request_id`, `org_id`, `user_id`,
and `trace_id` from the contextvars populated by `RequestContextMiddleware`.
"""
from __future__ import annotations

import logging
import sys
from contextvars import ContextVar
from typing import Any

import structlog

request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)
org_id_ctx: ContextVar[str | None] = ContextVar("org_id", default=None)
user_id_ctx: ContextVar[str | None] = ContextVar("user_id", default=None)
trace_id_ctx: ContextVar[str | None] = ContextVar("trace_id", default=None)


def _inject_context(_, __, event_dict: dict[str, Any]) -> dict[str, Any]:
    for key, ctx in (
        ("request_id", request_id_ctx),
        ("org_id", org_id_ctx),
        ("user_id", user_id_ctx),
        ("trace_id", trace_id_ctx),
    ):
        val = ctx.get()
        if val is not None:
            event_dict.setdefault(key, val)
    return event_dict


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            _inject_context,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, level)),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
