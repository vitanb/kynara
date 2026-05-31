# Kynara Backend — Code Review & Security Audit

**Date:** 2026-05-31  
**Scope:** `backend/app/` — auth, middleware, decisions, approvals, webhooks, billing, anomaly detection  
**Reviewer:** Claude (Cowork)

---

## Summary

The codebase is well-structured with several security-conscious design choices already in place: Argon2id + pepper for passwords, HMAC-based refresh token hashing, a solid SSRF blocklist, security headers, and a fail-closed policy engine. The issues below are real but mostly moderate — no obvious critical vulnerabilities were found. The most pressing items are the missing rate limit on `/login`, the unprotected `/metrics` endpoint, and a SSRF gap in webhook URL validation.

---

## Security Findings

### 🔴 HIGH — Login endpoint has no rate limiting

**File:** `app/api/v1/auth.py` — `POST /auth/login`

The `login` endpoint has no `@limiter.limit(...)` decorator. The global `slowapi` limiter is configured with `key_func=get_remote_address` and `default_limits=[rate_limit_anonymous]` (60/min), but SlowAPI's default limits only apply to routes that explicitly opt in or when the limiter is used as a dependency — they do **not** automatically apply to all routes. An attacker can brute-force passwords without hitting any rate limit.

**Fix:** Add `@limiter.limit("10/minute")` (or tighter) to `/login`, `/register`, `/forgot-password`, and `/reset-password`.

```python
from app.main import app  # or pass limiter via dependency
@router.post("/login", ...)
@limiter.limit("10/minute")
async def login(request: Request, body: LoginIn, ...):
    ...
```

---

### 🔴 HIGH — `/metrics` endpoint is unauthenticated

**File:** `app/main.py`

```python
@app.get("/metrics", include_in_schema=False)
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
```

Prometheus metrics expose internal counters (login failures, decision counts, org activity) with no auth check. In a multi-tenant SaaS, this leaks aggregate behavioral data to anyone who can reach the API.

**Fix:** Restrict to internal networks via reverse proxy, or add a simple secret header check:

```python
@app.get("/metrics", include_in_schema=False)
def metrics(x_metrics_token: str = Header(None)):
    if x_metrics_token != settings.metrics_secret:
        raise HTTPException(403)
    return Response(generate_latest(), ...)
```

---

### 🟠 MEDIUM — Webhook URL creation lacks SSRF validation

**File:** `app/webhooks/service.py` — `WebhookService.create_endpoint`  
**Contrast:** `app/api/v1/guardrails.py` correctly calls `assert_safe_url()` on outbound URLs.

`create_endpoint` stores a webhook URL without calling `assert_safe_url()`. When the webhook worker later POSTs to that URL, it can be used to probe internal services. `HttpUrl` (Pydantic) validates format but not that the host resolves to a public IP.

**Fix:** Call `assert_safe_url(url, scheme_whitelist={"https"})` inside `WebhookService.create_endpoint` before persisting:

```python
from app.core.ssrf import assert_safe_url

async def create_endpoint(self, org_id, url, ...):
    try:
        assert_safe_url(url, scheme_whitelist={"https"})
    except ValueError as exc:
        raise ValueError(f"Webhook URL not allowed: {exc}") from exc
    ...
```

---

### 🟠 MEDIUM — `assert` used as runtime guard in request handlers

**File:** `app/api/v1/auth.py` — lines 164, 215, 242

```python
user = await session.get(User, row.user_id)
assert user   # ← will raise AssertionError, not HTTPException
```

Python's `assert` is disabled when running with `-O` (optimize flag). Even without that, `AssertionError` bubbles up as an unhandled 500 rather than a clean 404/400, leaking a stack trace in development and giving attackers confirmation that an invariant was violated.

**Fix:** Replace with explicit guards:

```python
if not user:
    raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
```

---

### 🟠 MEDIUM — JWT algorithm is HS256 (symmetric); no rotation mechanism

**File:** `app/auth/tokens.py`

HS256 means the same `jwt_secret` is used to both sign and verify tokens. Anyone with read access to the secret can forge tokens for any user, including superadmins. There is also no `jti` blocklist, so stolen tokens are valid until they expire (15 min TTL — acceptable, but worth noting).

**Recommendation:** Consider RS256 (asymmetric) so verification keys can be public. If staying with HS256, document a key-rotation procedure. The prod validator (`jwt_secret_strong_in_prod`) is a good safeguard but does not enforce rotation.

---

### 🟠 MEDIUM — Password minimum length is only 8 characters

**File:** `app/api/v1/auth.py` — `RegisterIn.password_strength`, `ResetPasswordIn.password_strength`

8 characters is below the NIST SP 800-63B recommended minimum of 15 for memorized secrets in high-assurance systems. Given that Kynara controls agent permissions, accounts have significant blast radius.

**Fix:** Raise the minimum to 12–15 characters and optionally integrate a `zxcvbn` score check.

---

### 🟠 MEDIUM — API key hashed with plain SHA-256, not HMAC

**File:** `app/auth/dependencies.py` — line 76  
**Contrast:** refresh tokens correctly use HMAC-SHA256 (`hash_refresh_token`).

```python
h = hashlib.sha256(credential.encode()).hexdigest()
```

SHA-256 without a key allows offline brute-force if the `api_keys` table is leaked, since `sk_live_` prefix + 64 hex chars is a known-format high-entropy token but can still be targeted with GPU-accelerated lookup tables. The refresh token path does this correctly with `hash_refresh_token` (HMAC-keyed). The API key path should be consistent.

**Fix:** Use the same HMAC approach as refresh tokens, or at minimum use `hashlib.sha256` with a domain-separation constant and the JWT secret as a key (like `_refresh_hmac_key`).

---

### 🟡 LOW — `password_pepper` default is a weak placeholder

**File:** `app/core/config.py`

```python
password_pepper: str = "change-me-in-prod"
```

Unlike `jwt_secret`, there is no `@field_validator` that rejects this value in production. A deployment that forgets to set `PASSWORD_PEPPER` silently uses the default, eliminating the pepper's protection.

**Fix:** Add a validator mirroring `jwt_secret_strong_in_prod`:

```python
@field_validator("password_pepper", mode="after")
@classmethod
def pepper_strong_in_prod(cls, v: str) -> str:
    import os
    if os.environ.get("ENV", "dev") == "prod" and v == "change-me-in-prod":
        raise ValueError("PASSWORD_PEPPER must be set in production.")
    return v
```

---

### 🟡 LOW — CORS error message leaks allowed-origin list to blocked callers

**File:** `app/middleware/security.py` — line 119

```python
return Response(
    content=f"CORS: origin '{origin}' not allowed. Allowed: {self.allow_origins}",
    ...
)
```

This tells an attacker exactly which origins are whitelisted, helping them craft spoofed or misconfigured requests. For a pre-flight 403, the body should be generic.

**Fix:**
```python
content="CORS: request origin not permitted"
```

---

### 🟡 LOW — Residency middleware relies on `request.state.org` being set upstream

**File:** `app/middleware/residency.py`

The check `org = getattr(request.state, "org", None)` silently no-ops if no upstream handler has set `request.state.org`. If the middleware ordering ever changes or a new route bypasses the principal-resolution step, residency enforcement is silently skipped with no log.

**Fix:** Add a warning log when `org` is `None` on requests that should have a resolved principal (non-health, non-metrics paths).

---

## Code Quality Findings

### 🟠 MEDIUM — Anomaly detector uses population variance, not sample variance

**File:** `app/anomaly/detector.py` — lines 57–61

```python
var = sum((v - mean) ** 2 for v in vals) / len(vals)   # population variance
```

For a rolling 30-day baseline with `len(vals) >= 5`, population variance (÷N) systematically underestimates spread for small samples, meaning z-scores are inflated and false positives increase. Should use sample variance (÷(N-1)).

**Fix:**
```python
var = sum((v - mean) ** 2 for v in vals) / (len(vals) - 1)
```

---

### 🟡 LOW — `BodySizeLimitMiddleware` trusts `Content-Length` header

**File:** `app/middleware/security.py` — lines 62–65

```python
cl = request.headers.get("content-length")
if cl and int(cl) > self.max_bytes:
    return Response("Payload too large", status_code=413)
return await call_next(request)
```

If `Content-Length` is absent or falsified, the body is passed through unchecked. A client can send a 100 MB body by omitting the header or lying about it (e.g., chunked transfer encoding). The check prevents honest clients from exceeding the limit but does not protect against a malicious actor.

**Fix:** Stream and buffer the actual body bytes up to `max_bytes`:

```python
async def dispatch(self, request: Request, call_next):
    body = b""
    async for chunk in request.stream():
        body += chunk
        if len(body) > self.max_bytes:
            return Response("Payload too large", status_code=413)
    # Reconstruct request with buffered body
    ...
```
(Note: requires patching `request._body` or using a `receive` override.)

---

### 🟡 LOW — `enforce_seat_limit` silently skips paid plans without checking Stripe

**File:** `app/billing/quota.py` — lines 60–62

```python
if sub.plan != "free":
    return  # paid plans are managed by Stripe seat counts — don't block here
```

If a Stripe webhook fails to update the subscription status (e.g., a payment failure is delayed), a `past_due` paid plan can still add unlimited seats. This is acknowledged in the comment but worth flagging as a potential revenue leak.

**Fix:** Consider calling `enforce_active_subscription` before returning for paid plans, or logging a warning when `status != "active"` on non-free plans.

---

### 🟡 LOW — `_pick_org` defaults to most-recently-joined org silently

**File:** `app/api/v1/auth.py` — `_pick_org`

When no `org_id` is supplied at login, the user gets their most recently joined org. This can silently log a user into an unexpected org (e.g., one they were just invited to) without any indication in the response. No `active_org` preference is persisted per user.

**Recommendation:** Surface the selected org in the `TokenOut` response so the frontend can warn users or prompt them to switch.

---

## What's Done Well

- **SSRF protection** in `ssrf.py` is comprehensive — covers all RFC-1918 ranges, metadata endpoints, IPv6 edge cases, and DNS rebinding by checking all resolved IPs.
- **Refresh token rotation** with reuse detection (`_revoke_chain`) is correctly implemented.
- **Argon2id + pepper** is the right password storage choice with correct tuning.
- **Security headers** (HSTS, CSP, X-Frame-Options, etc.) are all set correctly.
- **Fail-closed policy engine** (`deny_on_policy_error = True`) is the right default.
- **Prod secret enforcement** for `jwt_secret` prevents accidental weak-secret deployments.
- **Org-scoped queries** throughout — no cross-tenant data leakage observed.
- **Refresh token HMAC** is correctly domain-separated from the JWT secret.

---

## Priority Order

| # | Severity | Finding |
|---|----------|---------|
| 1 | 🔴 HIGH | No rate limit on `/login` — brute-force risk |
| 2 | 🔴 HIGH | `/metrics` unauthenticated — leaks internal telemetry |
| 3 | 🟠 MEDIUM | Webhook URL not SSRF-validated before storage |
| 4 | 🟠 MEDIUM | `assert` used as runtime guard in auth handlers |
| 5 | 🟠 MEDIUM | API key hashed with plain SHA-256, not HMAC |
| 6 | 🟠 MEDIUM | Password minimum too short (8 chars) |
| 7 | 🟠 MEDIUM | HS256 JWT with no rotation mechanism |
| 8 | 🟡 LOW | `password_pepper` default not validated in prod |
| 9 | 🟡 LOW | CORS error leaks allowed-origin list |
| 10 | 🟡 LOW | Anomaly detector uses population vs sample variance |
| 11 | 🟡 LOW | `BodySizeLimitMiddleware` trusts `Content-Length` header |
| 12 | 🟡 LOW | Residency middleware silently no-ops if `request.state.org` missing |
