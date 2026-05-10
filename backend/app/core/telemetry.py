"""OpenTelemetry + Prometheus wiring."""
from __future__ import annotations

from fastapi import FastAPI
from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from prometheus_client import Counter, Histogram

from .config import get_settings


# --- Business-level metrics (exposed on /metrics) ---------------------------
decisions_total = Counter(
    "kynara_decisions_total",
    "Policy decisions evaluated",
    ["org_id", "effect"],  # effect: allow | deny | require_approval | error
)
decision_latency = Histogram(
    "kynara_decision_latency_seconds",
    "Policy decision latency",
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5),
)
auth_events_total = Counter(
    "kynara_auth_events_total",
    "Authentication events",
    ["event"],  # login_success | login_failure | sso_login | mfa_required | refresh | logout
)
audit_writes_total = Counter("kynara_audit_writes_total", "Audit log entries persisted")


def init_telemetry(app: FastAPI) -> None:
    s = get_settings()
    resource = Resource.create({"service.name": s.service_name, "deployment.environment": s.env})

    tracer_provider = TracerProvider(resource=resource)
    if s.otlp_endpoint:
        tracer_provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=s.otlp_endpoint, insecure=True))
        )
    trace.set_tracer_provider(tracer_provider)

    meter_provider = MeterProvider(
        resource=resource,
        metric_readers=(
            [PeriodicExportingMetricReader(OTLPMetricExporter(endpoint=s.otlp_endpoint, insecure=True))]
            if s.otlp_endpoint
            else []
        ),
    )
    metrics.set_meter_provider(meter_provider)

    FastAPIInstrumentor.instrument_app(app, excluded_urls="/health,/metrics")


def get_tracer():
    return trace.get_tracer("kynara")
