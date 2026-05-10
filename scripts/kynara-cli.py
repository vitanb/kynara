#!/usr/bin/env python3
"""kynara-cli — round-trip policy bundles through git.

Subcommands:

  pull       Download the live bundle for the configured org and write to a file.
  push       Upload a bundle file; prints the diff. With --dry-run, just diffs.
  diff       Compute the diff vs. the live bundle without applying.
  verify     Recompute the bundle's checksum and confirm it matches.

Auth: reads ``KYNARA_BASE_URL`` and ``KYNARA_API_KEY`` from the environment,
or accepts ``--base-url`` and ``--api-key`` flags. The API key must have
``policies.write`` scope.

Bundles are JSON. They are designed for committing to git; commit only what
your IdP can read with ``policies.read``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from typing import Any
from urllib import error, request


def env(*candidates: str, default: str = "") -> str:
    for c in candidates:
        if v := os.environ.get(c):
            return v
    return default


def http(method: str, url: str, *, body: dict | None = None, api_key: str) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = request.Request(url, data=data, method=method)
    req.add_header("X-Kynara-Key", api_key)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        sys.exit(f"HTTP {e.code}: {body}")


def canonical(o: Any) -> bytes:
    return json.dumps(o, sort_keys=True, separators=(",", ":")).encode()


def checksum(env_dict: dict) -> str:
    body = {k: v for k, v in env_dict.items() if k != "checksum"}
    return "sha256:" + hashlib.sha256(canonical(body)).hexdigest()


def cmd_pull(args, base_url: str, api_key: str) -> int:
    bundle = http("GET", f"{base_url}/api/v1/policy-bundle/export", api_key=api_key)
    text = json.dumps(bundle, indent=2, sort_keys=True)
    if args.out == "-" or not args.out:
        sys.stdout.write(text + "\n")
    else:
        with open(args.out, "w") as f:
            f.write(text + "\n")
        print(f"Wrote {args.out} ({len(text)} bytes)", file=sys.stderr)
    return 0


def cmd_diff(args, base_url: str, api_key: str) -> int:
    with open(args.bundle) as f:
        b = json.load(f)
    diff = http("POST", f"{base_url}/api/v1/policy-bundle/diff", body=b, api_key=api_key)
    print(json.dumps(diff, indent=2))
    n = sum(len(diff[k]["added"]) + len(diff[k]["removed"]) + len(diff[k]["changed"])
            for k in ("policies", "roles", "tools"))
    return 0 if n == 0 else 1  # nonzero so CI sees there are changes


def cmd_push(args, base_url: str, api_key: str) -> int:
    with open(args.bundle) as f:
        b = json.load(f)
    expected = checksum(b)
    if b.get("checksum") and b["checksum"] != expected:
        sys.exit(f"Bundle checksum mismatch. expected={expected} found={b['checksum']}")
    b["checksum"] = expected
    qs = "?dry_run=true" if args.dry_run else ""
    res = http("POST", f"{base_url}/api/v1/policy-bundle/apply{qs}", body=b, api_key=api_key)
    print(json.dumps(res, indent=2))
    return 0


def cmd_verify(args, *_unused) -> int:
    with open(args.bundle) as f:
        b = json.load(f)
    expected = checksum(b)
    if b.get("checksum") != expected:
        sys.exit(f"Mismatch. expected={expected} found={b.get('checksum')}")
    print(f"OK: {expected}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(prog="kynara-cli", description=__doc__)
    ap.add_argument("--base-url", default=env("KYNARA_BASE_URL", default="https://kynara.example.com"))
    ap.add_argument("--api-key", default=env("KYNARA_API_KEY"))

    sp = ap.add_subparsers(dest="cmd", required=True)

    p = sp.add_parser("pull", help="Download the live bundle")
    p.add_argument("--out", default="-", help="Output file or '-'")
    p.set_defaults(fn=cmd_pull)

    p = sp.add_parser("diff", help="Diff a local bundle against the live state")
    p.add_argument("bundle")
    p.set_defaults(fn=cmd_diff)

    p = sp.add_parser("push", help="Apply a local bundle")
    p.add_argument("bundle")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(fn=cmd_push)

    p = sp.add_parser("verify", help="Verify the bundle checksum")
    p.add_argument("bundle")
    p.set_defaults(fn=cmd_verify)

    args = ap.parse_args()
    if args.cmd != "verify" and not args.api_key:
        sys.exit("Missing --api-key (or KYNARA_API_KEY env var)")

    return args.fn(args, args.base_url, args.api_key)


if __name__ == "__main__":
    raise SystemExit(main())
