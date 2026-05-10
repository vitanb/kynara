"""Hybrid RBAC + ABAC policy engine.

## Evaluation model

For every decision request, the engine runs this pipeline:

1.  **Hard gates.** If the agent is disabled, the org is past_due, or daily budget is
    exhausted, return ``deny`` immediately with the appropriate ``reason``.
2.  **RBAC pass.** Compute the union of role-granted scopes for the principal. If no
    role covers the requested ``action``, the rest of the pipeline can only ``deny``.
3.  **ABAC pass.** Evaluate every bound policy whose ``actions`` and ``resource_types``
    match, in ascending priority order. Stop at the first terminal effect.
4.  **Default.** If no policy matches, apply the org's default effect (``deny`` by
    default — Kynara is fail-closed).

## Condition grammar

Conditions are JSON AST nodes. Every node has ``op`` and operands. Atoms reference
the evaluation context as ``ctx.<path>``.

```
{"op": "and", "args": [
   {"op": "eq", "args": ["ctx.resource.attrs.classification", "public"]},
   {"op": "in", "args": ["ctx.context.ip_country", ["US", "CA"]]},
   {"op": "time_between", "args": ["ctx.context.time", "09:00", "18:00"]}
]}
```

Supported ops: ``and``, ``or``, ``not``, ``eq``, ``neq``, ``gt``, ``gte``, ``lt``,
``lte``, ``in``, ``contains``, ``starts_with``, ``time_between``, ``has_scope``.
"""
from __future__ import annotations

import datetime as dt
import fnmatch
from dataclasses import dataclass, field
from typing import Any, Literal

Effect = Literal["allow", "deny", "require_approval"]


@dataclass
class DecisionContext:
    subject: dict[str, Any]   # {"id", "type", "attrs"}
    action: str
    resource: dict[str, Any]  # {"type", "id", "attrs"}
    context: dict[str, Any]   # {"time", "ip", "ip_country", "request_id", ...}


@dataclass
class Decision:
    effect: Effect
    reason: str
    matched_policy_id: str | None = None
    obligations: list[dict[str, Any]] = field(default_factory=list)
    # Debug fields — populated by the service layer, not audited
    granted_scopes: list[str] = field(default_factory=list)
    rbac_pass: bool = True  # False when the RBAC gate denied before ABAC ran

    def to_audit_payload(self) -> dict[str, Any]:
        return {
            "effect": self.effect,
            "reason": self.reason,
            "matched_policy_id": self.matched_policy_id,
            "obligations": self.obligations,
        }


@dataclass
class _PolicyRow:
    id: str
    priority: int
    effect: Effect
    actions: list[str]
    resource_types: list[str]
    condition: dict[str, Any]
    is_enabled: bool = True


# --------------------------------------------------------------------- atoms --
def _resolve_path(ctx: DecisionContext, path: str) -> Any:
    """Resolve dotted path like `ctx.resource.attrs.classification`."""
    if not path.startswith("ctx."):
        return path  # literal
    cur: Any = {"subject": ctx.subject, "action": ctx.action,
                "resource": ctx.resource, "context": ctx.context}
    for part in path.split(".")[1:]:
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            cur = getattr(cur, part, None)
        if cur is None:
            return None
    return cur


def _coerce(v: Any) -> Any:
    return v


def _evaluate(node: Any, ctx: DecisionContext) -> bool:
    if node in (None, {}, True):
        return True
    if node is False:
        return False
    if not isinstance(node, dict) or "op" not in node:
        raise ValueError(f"invalid policy node: {node!r}")

    op = node["op"]
    args = node.get("args", [])

    if op == "and":
        return all(_evaluate(a, ctx) for a in args)
    if op == "or":
        return any(_evaluate(a, ctx) for a in args)
    if op == "not":
        return not _evaluate(args[0], ctx)

    # Leaf ops resolve args that start with "ctx."
    resolved = [_resolve_path(ctx, a) if isinstance(a, str) else a for a in args]

    if op == "eq":  return resolved[0] == resolved[1]
    if op == "neq": return resolved[0] != resolved[1]
    if op == "gt":  return _coerce(resolved[0]) >  _coerce(resolved[1])
    if op == "gte": return _coerce(resolved[0]) >= _coerce(resolved[1])
    if op == "lt":  return _coerce(resolved[0]) <  _coerce(resolved[1])
    if op == "lte": return _coerce(resolved[0]) <= _coerce(resolved[1])
    if op == "in":  return resolved[0] in (resolved[1] or [])
    if op == "contains": return resolved[1] in (resolved[0] or [])
    if op == "starts_with": return (resolved[0] or "").startswith(resolved[1])
    if op == "time_between":
        t, lo, hi = resolved
        if isinstance(t, str):
            t = dt.datetime.fromisoformat(t.replace("Z", "+00:00"))
        return _in_time_window(t, lo, hi)
    if op == "has_scope":
        scopes = ctx.subject.get("attrs", {}).get("scopes", [])
        return _scope_matches(scopes, resolved[0])

    raise ValueError(f"unsupported op: {op}")


def _in_time_window(t: dt.datetime, lo: str, hi: str) -> bool:
    t_time = t.timetz() if t.tzinfo else t.time()
    lo_t = dt.time.fromisoformat(lo)
    hi_t = dt.time.fromisoformat(hi)
    if lo_t <= hi_t:
        return lo_t <= t_time.replace(tzinfo=None) <= hi_t
    # window crosses midnight, e.g. 22:00 -> 06:00
    return t_time.replace(tzinfo=None) >= lo_t or t_time.replace(tzinfo=None) <= hi_t


def _scope_matches(granted: list[str], requested: str) -> bool:
    for s in granted or []:
        if s == "*" or s == requested:
            return True
        if s.endswith("*") and requested.startswith(s[:-1]):
            return True
        # fnmatch handles patterns like `crm.*.read`
        if fnmatch.fnmatchcase(requested, s):
            return True
    return False


def _action_matches(policy_actions: list[str], action: str) -> bool:
    if not policy_actions:
        return True  # empty = any
    return any(_scope_matches([pa], action) for pa in policy_actions)


def _resource_matches(resource_types: list[str], resource_type: str | None) -> bool:
    if not resource_types:
        return True
    return resource_type in resource_types or "*" in resource_types


# ----------------------------------------------------------------- evaluate --
@dataclass
class EngineInput:
    policies: list[_PolicyRow]
    granted_scopes: list[str]
    default_effect: Effect = "deny"


def evaluate(inp: EngineInput, ctx: DecisionContext) -> Decision:
    # RBAC gate
    if not _scope_matches(inp.granted_scopes, ctx.action):
        return Decision(
            effect="deny",
            reason=f"no role grants scope {ctx.action!r}",
            granted_scopes=list(inp.granted_scopes),
            rbac_pass=False,
        )

    # ABAC pass — ascending priority
    ordered = sorted(
        (p for p in inp.policies if p.is_enabled),
        key=lambda p: p.priority,
    )
    for policy in ordered:
        if not _action_matches(policy.actions, ctx.action):
            continue
        if not _resource_matches(policy.resource_types, ctx.resource.get("type")):
            continue
        try:
            if not _evaluate(policy.condition, ctx):
                continue
        except Exception as e:
            return Decision(
                effect="deny",
                reason=f"policy {policy.id} condition error: {e}",
                matched_policy_id=policy.id,
                granted_scopes=list(inp.granted_scopes),
            )
        return Decision(
            effect=policy.effect,
            reason=f"matched policy {policy.id}",
            matched_policy_id=policy.id,
            granted_scopes=list(inp.granted_scopes),
        )

    return Decision(
        effect=inp.default_effect,
        reason="no policy matched; default applied",
        granted_scopes=list(inp.granted_scopes),
    )
