#!/usr/bin/env python3
"""Offline audit-chain verifier.

Re-derive ``entry_hash`` for every row in an exported audit log and report
the first sequence number where the chain breaks. Designed for use during
the ``audit_chain_broken`` incident playbook (`docs/runbooks/incident-response.md`
§5.1) — operators can run this against a snapshot of ``audit_events`` with no
network access to the running service.

Input formats supported:

  - JSON Lines: one event per line (each line a JSON object with at minimum
    ``sequence``, ``ts``, ``event_type``, ``actor``, ``payload``,
    ``prev_hash``, ``entry_hash``).
  - CSV: same fields as columns; ``payload`` is JSON-encoded.

Examples:

  $ python scripts/verify_chain_offline.py audit.jsonl
  $ pg_dump -t audit_events ... | jq -c '.' | python scripts/verify_chain_offline.py -
  $ python scripts/verify_chain_offline.py --since 2026-04-01 audit.csv

Exit codes: 0 OK, 1 chain broken, 2 input error.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime
from typing import Any, Iterable

ZERO_HASH = "0" * 64


def canonical_json(payload: Any) -> str:
    """Match the canonicalisation used by ``app/audit/service.py``."""
    return json.dumps(payload, separators=(",", ":"), sort_keys=True, ensure_ascii=False)


def compute_entry_hash(prev_hash: str, sequence: int, ts: str,
                       event_type: str, actor: str, payload: Any) -> str:
    h = hashlib.sha256()
    h.update(prev_hash.encode())
    h.update(b"|")
    h.update(str(sequence).encode())
    h.update(b"|")
    h.update(ts.encode())
    h.update(b"|")
    h.update(event_type.encode())
    h.update(b"|")
    h.update(actor.encode())
    h.update(b"|")
    h.update(canonical_json(payload).encode())
    return h.hexdigest()


def iter_jsonl(path: str) -> Iterable[dict]:
    f = sys.stdin if path == "-" else open(path)
    try:
        for n, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as e:
                print(f"err: line {n}: {e}", file=sys.stderr)
                sys.exit(2)
    finally:
        if f is not sys.stdin:
            f.close()


def iter_csv(path: str) -> Iterable[dict]:
    f = sys.stdin if path == "-" else open(path)
    try:
        for row in csv.DictReader(f):
            row["payload"] = json.loads(row.get("payload") or "{}")
            row["sequence"] = int(row["sequence"])
            yield row
    finally:
        if f is not sys.stdin:
            f.close()


def verify(rows: Iterable[dict], *, since: datetime | None) -> tuple[bool, int | None, int]:
    """Return (ok, broken_at, count)."""
    prev = None
    expected_seq = None
    count = 0

    for row in rows:
        seq = int(row["sequence"])
        if since is not None:
            ts = datetime.fromisoformat(str(row["ts"]).replace("Z", "+00:00"))
            if ts < since:
                continue

        # First event: prev_hash must be the zero seed.
        if prev is None:
            expected_seq = seq
            if str(row.get("prev_hash") or "") != ZERO_HASH:
                return False, seq, count
        else:
            if seq != expected_seq:
                return False, seq, count
            if str(row.get("prev_hash") or "") != prev:
                return False, seq, count

        recomputed = compute_entry_hash(
            prev_hash=str(row.get("prev_hash") or ZERO_HASH),
            sequence=seq,
            ts=str(row["ts"]),
            event_type=str(row["event_type"]),
            actor=str(row["actor"]),
            payload=row.get("payload") or {},
        )
        if recomputed != row.get("entry_hash"):
            return False, seq, count

        prev = row["entry_hash"]
        expected_seq = seq + 1
        count += 1

    return True, None, count


def main() -> int:
    ap = argparse.ArgumentParser(description="Offline audit chain verifier")
    ap.add_argument("input", help="Path to JSONL or CSV file (use '-' for stdin)")
    ap.add_argument("--format", choices=("auto", "jsonl", "csv"), default="auto")
    ap.add_argument("--since", help="ISO-8601 timestamp; only verify events on or after")
    args = ap.parse_args()

    fmt = args.format
    if fmt == "auto":
        fmt = "csv" if args.input.lower().endswith(".csv") else "jsonl"

    rows = iter_csv(args.input) if fmt == "csv" else iter_jsonl(args.input)
    since = datetime.fromisoformat(args.since.replace("Z", "+00:00")) if args.since else None

    ok, broken_at, count = verify(rows, since=since)
    if ok:
        print(f"OK · {count} events verified · chain intact")
        return 0
    print(f"BROKEN at sequence #{broken_at} · {count} events verified before break", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
