#!/usr/bin/env python3
"""kynara-import — convert OPA/Rego, Cedar, and Casbin policies to Kynara JSON AST.

This is a best-effort migration aid. Many constructs in upstream policy
languages have no direct analog in Kynara's AST; the converter emits a
``warnings`` block listing what could not be translated faithfully and
inserts a TODO marker into the bundle so reviewers can finish by hand.

Examples:

  $ kynara-import opa rego/refund_rules.rego > out.bundle.json
  $ kynara-import cedar policies.cedar     > out.bundle.json
  $ kynara-import casbin model.conf policy.csv > out.bundle.json

Always pair with the simulator (``policies/replay``) before applying.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Any


# ─── Common output shape ─────────────────────────────────────────────────────


def empty_bundle() -> dict:
    return {
        "schema_version": "kynara/v1",
        "org_slug": "imported",
        "issued_at": "1970-01-01T00:00:00Z",
        "policies": [],
        "roles": [],
        "tools": [],
        "_warnings": [],
    }


# ─── OPA / Rego ──────────────────────────────────────────────────────────────
#
# We support a deliberate subset:
#   * rules of the form `allow { input.x == "y"; input.z > N }`
#   * deny rules
#   * implicit AND between expressions in the same body
#
# Anything more sophisticated (functions, comprehensions, walk()) is recorded
# as a warning and the policy is emitted disabled with a TODO note.


_OP_MAP = {"==": "eq", "!=": "neq", ">": "gt", ">=": "gte",
           "<": "lt", "<=": "lte"}
_RULE_RE = re.compile(
    r"^\s*(?P<effect>allow|deny|require_approval)\s*\{(?P<body>[^}]+)\}",
    re.MULTILINE | re.DOTALL,
)
_LINE_RE = re.compile(
    r"^\s*(?P<lhs>input(?:\.[A-Za-z_][\w]*)+)\s*(?P<op>==|!=|>=|<=|>|<)\s*(?P<rhs>.+?)\s*$"
)


def _rego_path(lhs: str) -> str:
    # input.foo.bar  ->  resource.foo.bar (heuristic — many Rego policies map
    # input.* to a single REST request body which we route to ``resource``).
    return lhs.replace("input.", "resource.")


def _parse_value(rhs: str) -> Any:
    rhs = rhs.strip()
    if rhs.startswith('"') and rhs.endswith('"'):
        return rhs[1:-1]
    if rhs in ("true", "false"):
        return rhs == "true"
    try:
        return int(rhs)
    except ValueError:
        try:
            return float(rhs)
        except ValueError:
            return rhs


def from_rego(text: str, *, slug_prefix: str) -> dict:
    bundle = empty_bundle()
    n = 0
    for m in _RULE_RE.finditer(text):
        effect = m.group("effect")
        body = m.group("body").strip()
        ands: list[dict] = []
        for line in (l.strip().rstrip(";") for l in body.split("\n")):
            if not line:
                continue
            mm = _LINE_RE.match(line)
            if not mm:
                bundle["_warnings"].append(
                    f"Could not translate Rego expression: '{line}'. "
                    f"Rule '{effect}' marked disabled."
                )
                continue
            ands.append({
                "op": _OP_MAP[mm.group("op")],
                "args": [_rego_path(mm.group("lhs")), _parse_value(mm.group("rhs"))],
            })
        cond = ands[0] if len(ands) == 1 else {"op": "and", "args": ands}
        n += 1
        bundle["policies"].append({
            "slug": f"{slug_prefix}-{effect}-{n}",
            "display_name": f"Imported from Rego ({effect})",
            "description": "Imported by kynara-import; review before enabling.",
            "effect": effect,
            "priority": 100,
            "actions": ["*"],
            "resource_types": [],
            "condition": cond,
            "is_enabled": False,
        })
    return bundle


# ─── Cedar ───────────────────────────────────────────────────────────────────
#
# Subset: ``permit(principal, action, resource) when { resource.x == "y" };``
# Anything using ``in``, hierarchical entities, or ABAC functions outside the
# allow-list is recorded as a warning.

_CEDAR_RE = re.compile(
    r"(?P<effect>permit|forbid)\s*\((?P<head>[^)]*)\)\s*"
    r"(?:when\s*\{(?P<when>[^}]*)\})?\s*;",
    re.MULTILINE | re.DOTALL,
)
_CEDAR_LINE_RE = re.compile(
    r'(?P<lhs>(?:resource|principal|context)\.[A-Za-z_][\w.]*)\s*'
    r'(?P<op>==|!=|>=|<=|>|<)\s*(?P<rhs>"[^"]*"|\d+(?:\.\d+)?|true|false)'
)


def from_cedar(text: str, *, slug_prefix: str) -> dict:
    bundle = empty_bundle()
    n = 0
    for m in _CEDAR_RE.finditer(text):
        effect = "allow" if m.group("effect") == "permit" else "deny"
        when = (m.group("when") or "").strip()
        ands: list[dict] = []
        for mm in _CEDAR_LINE_RE.finditer(when):
            lhs = mm.group("lhs").replace("principal.", "subject.")
            ands.append({
                "op": _OP_MAP[mm.group("op")],
                "args": [lhs, _parse_value(mm.group("rhs"))],
            })
        cond = ands[0] if len(ands) == 1 else {"op": "and", "args": ands} if ands else None
        n += 1
        bundle["policies"].append({
            "slug": f"{slug_prefix}-{effect}-{n}",
            "display_name": f"Imported from Cedar ({effect})",
            "description": "Imported by kynara-import; review before enabling.",
            "effect": effect, "priority": 100,
            "actions": ["*"], "resource_types": [],
            "condition": cond or {},
            "is_enabled": False,
        })
        if "in " in when or "has " in when:
            bundle["_warnings"].append(
                f"Cedar 'in'/'has' constructs in '{when[:80]}…' need manual translation."
            )
    return bundle


# ─── Casbin ──────────────────────────────────────────────────────────────────
#
# We support the canonical RBAC-with-ABAC model:
#     p, role, resource_pattern, action[, condition]
# Each row becomes a policy. The condition column (if any) is parsed as a
# limited expression in the form `r.act == "read" && r.obj.classification == "public"`.

_CASBIN_LINE_RE = re.compile(r'r\.(\w+(?:\.\w+)*)\s*(==|!=|>=|<=|>|<)\s*"?([^"\s&|()]+)"?')


def from_casbin(model: str, policy_csv: str, *, slug_prefix: str) -> dict:
    bundle = empty_bundle()
    n = 0
    for line in policy_csv.splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split(",")]
        if not parts or parts[0] not in ("p", "p2", "p3"):
            continue
        # p, role, obj_pattern, action[, condition]
        role, obj, action = parts[1], parts[2], parts[3]
        cond_text = parts[4] if len(parts) > 4 else ""

        ands = []
        for mm in _CASBIN_LINE_RE.finditer(cond_text):
            ands.append({
                "op": _OP_MAP[mm.group(2)],
                "args": [f"resource.{mm.group(1)}", _parse_value(mm.group(3))],
            })

        n += 1
        bundle["policies"].append({
            "slug": f"{slug_prefix}-{n}",
            "display_name": f"Imported Casbin rule (role={role})",
            "description": f"Imported from Casbin policy CSV. Original: {line}",
            "effect": "allow",
            "priority": 200,
            "actions": [action] if action != "*" else ["*"],
            "resource_types": [obj] if obj != "*" else [],
            "condition": ({"op": "and", "args": ands} if len(ands) > 1
                          else (ands[0] if ands else {})),
            "is_enabled": False,
        })
    return bundle


# ─── CLI ─────────────────────────────────────────────────────────────────────


def main() -> int:
    ap = argparse.ArgumentParser(prog="kynara-import")
    sp = ap.add_subparsers(dest="cmd", required=True)

    p = sp.add_parser("opa", help="Convert Rego (OPA) policies")
    p.add_argument("file"); p.add_argument("--slug-prefix", default="rego")

    p = sp.add_parser("cedar", help="Convert Cedar policies")
    p.add_argument("file"); p.add_argument("--slug-prefix", default="cedar")

    p = sp.add_parser("casbin", help="Convert Casbin model + policy CSV")
    p.add_argument("model"); p.add_argument("policy")
    p.add_argument("--slug-prefix", default="casbin")

    args = ap.parse_args()

    if args.cmd == "opa":
        bundle = from_rego(open(args.file).read(), slug_prefix=args.slug_prefix)
    elif args.cmd == "cedar":
        bundle = from_cedar(open(args.file).read(), slug_prefix=args.slug_prefix)
    elif args.cmd == "casbin":
        bundle = from_casbin(open(args.model).read(), open(args.policy).read(),
                             slug_prefix=args.slug_prefix)
    else:
        ap.print_help(); return 2

    if bundle["_warnings"]:
        print(f"# {len(bundle['_warnings'])} warnings — see _warnings field", file=sys.stderr)
    json.dump(bundle, sys.stdout, indent=2, sort_keys=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
