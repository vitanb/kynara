"""Centralized settings. Every secret & tunable comes from env — no hardcoded prod values."""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # ---- Environment ----
    env: Literal["dev", "staging", "prod"] = "dev"
    log_level: str = "INFO"
    service_name: str = "kynara-control-plane"

    # ---- CORS ----
    # Comma-separated allowed origins, e.g. https://app.railway.app,http://localhost:5173
    cors_origins_str: str = "http://localhost:5173"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_origins_str.split(",") if o.strip()]

    # ---- Database ----
    database_url: str = Field(
        default="postgresql+asyncpg://kynara:kynara_dev@localhost:5432/kynara"
    )
    redis_url: str = Field(default="redis://localhost:6379/0")

    @field_validator("database_url", mode="after")
    @classmethod
    def ensure_asyncpg_driver(cls, v: str) -> str:
        """Guarantee asyncpg is the driver regardless of how the URL was supplied."""
        if v.startswith("postgresql://") and "+asyncpg" not in v:
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    # ---- Auth ----
    # Required for the web server. Cron jobs (anomaly-detector, jit-expirer,
    # chain-verifier) don't issue or verify JWTs so they don't need this —
    # but they still call get_settings(), so we provide a clearly unsafe
    # default that only the web server startup check (below) rejects in prod.
    jwt_secret: str = Field(default="CHANGE_ME_NOT_FOR_PRODUCTION_USE_32ch")
    jwt_access_ttl_seconds: int = 15 * 60
    jwt_refresh_ttl_seconds: int = 30 * 24 * 3600
    password_pepper: str = "change-me-in-prod"
    api_key_prefix: str = "sk_live_"

    @field_validator("jwt_secret", mode="after")
    @classmethod
    def jwt_secret_strong_in_prod(cls, v: str) -> str:
        """Enforce a real secret in production. Dev/cron contexts get a warning only."""
        import os
        if os.environ.get("ENV", "dev") == "prod" and (
            len(v) < 32 or v == "CHANGE_ME_NOT_FOR_PRODUCTION_USE_32ch"
        ):
            raise ValueError(
                "JWT_SECRET must be set to a random string of at least 32 characters in production. "
                "Generate one with: openssl rand -hex 32"
            )
        return v

    # ---- Policy decisions ----
    decision_cache_ttl_seconds: int = 5
    deny_on_policy_error: bool = True  # fail-closed

    # ---- Public URL (used to build SSO callback URIs) ----
    # Set this to your backend's public hostname, e.g. https://kynara-api.railway.app
    # Required for SSO to work in production.
    public_api_url: str = "http://localhost:8000"

    # ---- SSO: Okta (OIDC) ----
    okta_issuer: str | None = None
    okta_client_id: str | None = None
    okta_client_secret: str | None = None
    okta_redirect_uri: str = "http://localhost:8000/api/v1/auth/sso/okta/callback"

    # ---- SSO: SAML ----
    saml_sp_entity_id: str = "https://kynara.dev/saml"
    saml_sp_acs_url: str = "http://localhost:8000/api/v1/auth/sso/saml/acs"
    saml_cert_dir: str = "./saml-certs"  # points at x509 key/cert pair

    # ---- Billing ----
    stripe_secret_key: str | None = None
    stripe_webhook_secret: str | None = None
    # Stripe Price IDs — set these in Railway env vars once you've created
    # products in the Stripe dashboard. Format: price_xxxxxxxxxxxxxxxxxx
    # Stripe Price IDs — must start with "price_" (Railway → Variables)
    # Frontend plan IDs: "pro" ($49/seat) and "enterprise" (custom)
    stripe_price_pro: str = "price_pro_monthly"             # replace with real ID
    stripe_price_enterprise: str = "price_enterprise_monthly"  # replace with real ID
    # Legacy aliases kept so old env vars don't cause startup errors
    stripe_price_team: str = "price_team_monthly"
    stripe_price_business: str = "price_business_monthly"

    # ---- Email ----
    # Transport priority: MailChannels → SMTP → console log (dev fallback)
    #
    # MailChannels (Cloudflare's email partner — free, no API key):
    #   Set MAILCHANNELS_ENABLED=true and add the required DNS records below.
    #   Leave RESEND_API_KEY empty / unset.
    mailchannels_enabled: bool = False

    # Optional: DKIM signing for MailChannels (strongly recommended for deliverability)
    # Generate with: openssl genrsa -out dkim.pem 2048 && openssl rsa -in dkim.pem -pubout
    # Set MAILCHANNELS_DKIM_DOMAIN to your sending domain and
    # MAILCHANNELS_DKIM_PRIVATE_KEY to the base64-encoded private key (single line).
    mailchannels_dkim_domain: str = ""
    mailchannels_dkim_selector: str = "mailchannels"
    mailchannels_dkim_private_key: str = ""   # base64-encoded RSA private key

    # Legacy Resend key — kept so existing deployments don't break.
    # Leave empty if you are using MailChannels.
    resend_api_key: str = ""

    # SMTP fallback — works with Gmail app-password, SendGrid, Postmark, etc.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_tls: bool = True  # use STARTTLS

    # "From" shown in every outbound email.
    # Must match a domain that has SPF/DKIM set up for the chosen transport.
    email_from_address: str = "Kynara <noreply@yourdomain.com>"

    # Base URL used when building links inside emails (reset / invite).
    app_url: str = "http://localhost:5173"

    # ---- Field-level encryption ----
    # Used to encrypt per-org tokens (Slack, Teams) stored in the DB.
    # Generate: openssl rand -hex 32
    encryption_key: str = ""

    # ---- Chat Approval Integrations ----
    # Slack — set SLACK_BOT_TOKEN and SLACK_SIGNING_SECRET in Railway env vars
    # Bot needs: chat:write, chat:write.public scopes
    slack_bot_token: str = ""            # xoxb-...
    slack_signing_secret: str = ""       # used to verify callback payloads
    slack_approval_channel: str = ""     # default channel ID, e.g. C08XXXXXXX

    # Microsoft Teams — set TEAMS_WEBHOOK_URL in Railway env vars
    # Use a Power Automate HTTP trigger or an Incoming Webhook connector
    teams_webhook_url: str = ""          # https://...webhook.office.com/...
    # For interactive buttons in Teams, set a callback secret
    teams_callback_secret: str = ""      # shared secret for HMAC verification

    # ---- Rate limits ----
    rate_limit_authenticated: str = "600/minute"
    rate_limit_anonymous: str = "60/minute"
    rate_limit_decision: str = "5000/minute"

    # ---- Observability ----
    otlp_endpoint: str | None = None
    prometheus_enabled: bool = True
    # Secret token required in the X-Metrics-Token header to access GET /metrics.
    # Generate with: openssl rand -hex 32
    # If left empty in prod, the /metrics endpoint will return 403 for all requests.
    metrics_secret: str = ""

    @property
    def is_prod(self) -> bool:
        return self.env == "prod"


@lru_cache
def get_settings() -> "Settings":
    return Settings()  # type: ignore[call-arg]
