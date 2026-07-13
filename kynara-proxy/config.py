"""
Kynara Proxy — configuration loaded from environment variables.

Every field can be set via env var with the KYNARA_ prefix, e.g.
  KYNARA_UPSTREAM_URL=https://api.openai.com
"""
import os


class Settings:
    # Where to forward allowed requests
    upstream_url: str = os.getenv("KYNARA_UPSTREAM_URL", "https://api.openai.com")

    # Local sidecar decision endpoint (see sidecar/main.go)
    sidecar_url: str = os.getenv("KYNARA_SIDECAR_URL", "http://localhost:7070")

    # Fall back to central API if sidecar is unreachable
    api_base_url: str = os.getenv("KYNARA_API_BASE_URL", "https://kynaraai.com")
    api_key: str = os.getenv("KYNARA_API_KEY", "")

    # fail_open=True: if Kynara is unreachable, allow the request (risky but available)
    # fail_open=False (default): block the request if Kynara is unreachable
    fail_open: bool = os.getenv("KYNARA_FAIL_OPEN", "false").lower() == "true"

    # Header the agent/platform sets to identify itself
    agent_id_header: str = os.getenv("KYNARA_AGENT_ID_HEADER", "x-kynara-agent")
    org_id_header: str = os.getenv("KYNARA_ORG_ID_HEADER", "x-kynara-org")

    # Append-only JSONL audit log (complementing the central audit trail)
    audit_log_path: str = os.getenv("KYNARA_AUDIT_LOG", "/tmp/kynara-proxy-audit.jsonl")

    # Port the proxy listens on
    port: int = int(os.getenv("KYNARA_PROXY_PORT", "8080"))

    # Request timeout forwarded to upstream (seconds)
    upstream_timeout: float = float(os.getenv("KYNARA_UPSTREAM_TIMEOUT", "30"))

    # Default subject type for policy checks
    default_subject_type: str = os.getenv("KYNARA_DEFAULT_SUBJECT_TYPE", "agent")


settings = Settings()
