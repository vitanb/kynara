"""Thin HTTP client + in-process decision cache."""
from __future__ import annotations

import contextlib
import os
import threading
import time
from dataclasses import dataclass
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential_jitter

from kynara_sdk.errors import (
    ApprovalRequired,
    PermissionDenied,
    KynaraUnavailable,
)
from kynara_sdk.types import Decision, DecisionEffect, Resource


@dataclass
class _CacheEntry:
    decision: Decision
    expires_at: float


class _DecisionCache:
    """Small thread-safe LRU-ish cache keyed by (subject, action, resource_id)."""

    def __init__(self, max_entries: int = 4096):
        self._lock = threading.Lock()
        self._data: dict[str, _CacheEntry] = {}
        self._max = max_entries

    def get(self, key: str) -> Decision | None:
        with self._lock:
            e = self._data.get(key)
            if not e:
                return None
            if e.expires_at < time.time():
                self._data.pop(key, None)
                return None
            return e.decision

    def put(self, key: str, decision: Decision, ttl: float = 5.0) -> None:
        with self._lock:
            if len(self._data) >= self._max:
                # evict oldest
                for k in list(self._data.keys())[:128]:
                    self._data.pop(k, None)
            self._data[key] = _CacheEntry(decision, time.time() + ttl)


class Kynara:
    """Main SDK entry point.

    Typical instantiation at agent bootstrap:

        kynara = Kynara(
            api_key=os.environ["KYNARA_API_KEY"],
            agent_id="crm-assistant",
            user_id=current_user_id,
            base_url="https://api.kynara.dev",
            fail_closed=True,
        )
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        agent_id: str,
        user_id: str | None,
        base_url: str = "https://api.kynara.dev",
        timeout_seconds: float = 2.0,
        fail_closed: bool = True,
        cache_ttl_seconds: float = 5.0,
    ):
        self.api_key = api_key or os.environ.get("KYNARA_API_KEY")
        if not self.api_key:
            raise ValueError("Kynara api_key is required")
        self.agent_id = agent_id
        self.user_id = user_id
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.fail_closed = fail_closed
        self._cache = _DecisionCache()
        self._cache_ttl = cache_ttl_seconds
        self._http = httpx.Client(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=self.timeout_seconds,
        )

    # ------------------------------------------------------------------- check
    def check(
        self,
        *,
        action: str,
        resource: Resource | dict | None = None,
        context: dict[str, Any] | None = None,
    ) -> Decision:
        """Evaluate a decision and return it. Does NOT raise on deny."""
        r = self._normalize_resource(resource)
        ck = self._cache_key(action, r.get("id"))
        cached = self._cache.get(ck)
        if cached:
            return cached
        try:
            d = self._call_check(action, r, context or {})
        except Exception as e:
            if self.fail_closed:
                raise KynaraUnavailable(f"decision call failed: {e}") from e
            return Decision(effect=DecisionEffect.ALLOW, reason="fail_open")
        self._cache.put(ck, d, self._cache_ttl)
        return d

    def enforce(
        self,
        *,
        action: str,
        resource: Resource | dict | None = None,
        context: dict[str, Any] | None = None,
    ) -> Decision:
        """Evaluate and raise on deny/approval. Returns Decision on allow."""
        d = self.check(action=action, resource=resource, context=context)
        if d.effect == DecisionEffect.DENY:
            raise PermissionDenied(d, action, self.agent_id)
        if d.effect == DecisionEffect.REQUIRE_APPROVAL:
            raise ApprovalRequired(d, action)
        return d

    @contextlib.contextmanager
    def guard(
        self,
        action: str,
        *,
        resource: Resource | dict | None = None,
        context: dict[str, Any] | None = None,
    ):
        """Context manager for check-then-act. Yields a small handle with ``.check()``.

        The SDK emits a ``tool.call.started`` audit event on enter and a ``tool.call.finished``
        event on exit, enabling end-to-end traceability.
        """
        start = time.time()
        handle = _GuardHandle(self, action, self._normalize_resource(resource), context or {})
        handle.check()
        try:
            yield handle
            handle.confirm(outcome="success", duration_ms=int((time.time() - start) * 1000))
        except Exception as e:
            handle.confirm(outcome="error", duration_ms=int((time.time() - start) * 1000),
                           error=type(e).__name__)
            raise

    # ------------------------------------------------------------------ private
    @retry(stop=stop_after_attempt(3), wait=wait_exponential_jitter(initial=0.05, max=0.5))
    def _call_check(self, action: str, resource: dict, context: dict) -> Decision:
        r = self._http.post(
            "/api/v1/decisions/check",
            json={
                "subject_type": "agent",
                "subject_id": self.agent_id,
                "on_behalf_of_user_id": self.user_id,
                "action": action,
                "resource": resource,
                "context": context,
            },
        )
        r.raise_for_status()
        d = r.json()
        return Decision(
            effect=DecisionEffect(d["effect"]),
            reason=d["reason"],
            matched_policy_id=d.get("matched_policy_id"),
            obligations=d.get("obligations", []),
        )

    def _normalize_resource(self, r) -> dict:
        if r is None:
            return {"type": None, "id": None, "attrs": {}}
        if isinstance(r, Resource):
            return {"type": r.type, "id": r.id, "attrs": dict(r.attrs)}
        return dict(r)

    def _cache_key(self, action: str, resource_id: str | None) -> str:
        return f"{self.agent_id}:{self.user_id}:{action}:{resource_id or ''}"


class _GuardHandle:
    def __init__(self, kynara: Kynara, action: str, resource: dict, context: dict):
        self._s = kynara
        self.action = action
        self.resource = resource
        self.context = context
        self._decision: Decision | None = None

    def check(self) -> Decision:
        self._decision = self._s.enforce(
            action=self.action, resource=self.resource, context=self.context
        )
        return self._decision

    def confirm(self, *, outcome: str, duration_ms: int | None = None,
                error: str | None = None) -> None:
        # Fire-and-forget notification; non-blocking failure mode.
        try:
            self._s._http.post(
                "/api/v1/decisions/events",
                json={
                    "action": self.action,
                    "resource": self.resource,
                    "outcome": outcome,
                    "duration_ms": duration_ms,
                    "error": error,
                },
                timeout=0.5,
            )
        except Exception:
            pass
