"""
Mock Kynara Sidecar — for local testing WITHOUT a real Kynara backend.

Mimics the sidecar's /api/v1/decisions/check endpoint so kynara-proxy
and kynara-mcp-wrapper can run standalone in dev/test.

Policy is defined in DENY_TOOLS below — everything else is allowed.

Usage:
  python mock_sidecar.py
  # Listens on http://localhost:7070
"""
import json
import time
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer

# ── Configure your test policy here ──────────────────────────────────────
#
# Tools in this list will be DENIED.
# Everything else is ALLOWED.
#
DENY_TOOLS = {
    "delete_file",
    "drop_table",
    "send_email",
    "execute_shell",
}

# Tools requiring human approval (returns require_approval effect)
APPROVAL_TOOLS = {
    "transfer_funds",
    "deploy_to_production",
}

# ─────────────────────────────────────────────────────────────────────────


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        ts = time.strftime("%H:%M:%S")
        print(f"  [{ts}] {fmt % args}")

    def do_GET(self):
        if self.path == "/healthz":
            self._respond(200, {"ok": True, "mode": "mock"})
        else:
            self._respond(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/api/v1/decisions/check":
            self._respond(404, {"error": "not found"})
            return

        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length))

        action = body.get("action", "")
        agent  = body.get("subject_id", "unknown")
        dec_id = f"mock_{uuid.uuid4().hex[:8]}"

        if action in DENY_TOOLS:
            effect, reason = "deny", f"tool '{action}' is in the deny list"
            print(f"  ⛔  DENY   agent={agent} tool={action}")
        elif action in APPROVAL_TOOLS:
            effect, reason = "require_approval", f"tool '{action}' needs human approval"
            print(f"  ⏳  APPROVAL_REQUIRED  agent={agent} tool={action}")
        else:
            effect, reason = "allow", "no matching deny policy"
            print(f"  ✅  ALLOW  agent={agent} tool={action}")

        resp = {
            "effect": effect,
            "reason": reason,
            "decision_id": dec_id,
            "matched_policy_id": "mock-policy-001" if effect != "allow" else None,
            "ttl_seconds": 5,
        }
        if effect == "require_approval":
            resp["approval_url"] = f"http://localhost:7070/approvals/{dec_id}"

        self._respond(200, resp)

    def _respond(self, code, data):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    port = 7070
    print(f"\n🔧 Mock Kynara Sidecar running on http://localhost:{port}")
    print(f"   DENY list  : {sorted(DENY_TOOLS)}")
    print(f"   APPROVAL   : {sorted(APPROVAL_TOOLS)}")
    print(f"   Everything else → ALLOW\n")
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()
