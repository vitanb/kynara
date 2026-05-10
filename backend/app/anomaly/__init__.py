"""Anomaly detection and risk scoring for agents.

Two cooperating components:

  * ``risk.score_agent(...)`` — synchronous, per-agent risk score in [0, 100],
    blending tool risk class, deny rate, sensitive-scope ownership, and time
    since last review. Surfaced on dashboards and used by ``policy.service``
    to break ties on overlapping policies.

  * ``detector.run_once(...)`` — periodic background job. Computes z-scores
    across a 30-day rolling baseline and emits ``anomaly.*`` audit events plus
    ``audit.chain_broken``-style webhook deliveries when something drifts.

The detector is intentionally simple — z-scores rather than ML — because
explainability matters more for a security control than peak accuracy.
"""
from app.anomaly.risk import score_agent
from app.anomaly.detector import run_once

__all__ = ["score_agent", "run_once"]
