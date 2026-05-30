"""Policy-as-code Git sync endpoints.

Orgs register a GitHub/GitLab repo; Kynara fetches `kynara-policies.json`
from it and applies the bundle using the existing policy_bundle logic.
Push webhooks trigger automatic syncs when the file changes.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import record_admin
from app.auth.dependencies import Principal, require_seat
from app.db.session import SessionLocal
from app.models.git_connection import GitConnection
from app.security import decrypt_for_tenant, encrypt_for_tenant

router = APIRouter(prefix="/git", tags=["git-sync"])

POLICY_FILE = "kynara-policies.json"


async def _session():
    async with SessionLocal() as s:
        yield s


# ─── Schemas ──────────────────────────────────────────────────────────────────


class GitConnectIn(BaseModel):
    provider: str  # "github" | "gitlab"
    repo_url: str
    branch: str = "main"
    access_token: str


class GitConnectOut(BaseModel):
    id: str
    provider: str
    repo_url: str
    branch: str
    sync_status: str
    last_sync_at: datetime | None
    last_sync_sha: str | None
    is_active: bool
    webhook_secret: str
    created_at: datetime


class SyncResult(BaseModel):
    sync_status: str
    last_sync_sha: str | None
    last_sync_at: datetime | None
    diff: dict[str, Any] | None = None
    error: str | None = None


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _row_to_out(row: GitConnection) -> GitConnectOut:
    return GitConnectOut(
        id=str(row.id),
        provider=row.provider,
        repo_url=row.repo_url,
        branch=row.branch,
        sync_status=row.sync_status,
        last_sync_at=row.last_sync_at,
        last_sync_sha=row.last_sync_sha,
        is_active=row.is_active,
        webhook_secret=row.webhook_secret,
        created_at=row.created_at,
    )


async def _validate_token_and_repo(provider: str, repo_url: str, token: str) -> None:
    """Call the provider API to verify the token has at least read access to the repo."""
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    if provider == "github":
        # Extract owner/repo from https://github.com/owner/repo
        parts = repo_url.rstrip("/").split("/")
        if len(parts) < 5:
            raise HTTPException(400, "Invalid GitHub repo URL")
        owner, repo = parts[-2], parts[-1]
        api_url = f"https://api.github.com/repos/{owner}/{repo}"
    elif provider == "gitlab":
        # Extract project path from https://gitlab.com/owner/repo
        parts = repo_url.rstrip("/").split("gitlab.com/", 1)
        if len(parts) < 2:
            raise HTTPException(400, "Invalid GitLab repo URL")
        project_path = parts[1].strip("/").replace("/", "%2F")
        api_url = f"https://gitlab.com/api/v4/projects/{project_path}"
    else:
        raise HTTPException(400, f"Unsupported provider: {provider}")

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(api_url, headers=headers)
    if resp.status_code == 401:
        raise HTTPException(400, "Access token is invalid or lacks repo read permission")
    if resp.status_code == 404:
        raise HTTPException(400, "Repository not found or token lacks access")
    if resp.status_code >= 400:
        raise HTTPException(400, f"Provider API error: {resp.status_code}")


async def _fetch_policy_file(connection: GitConnection, org_id: str) -> tuple[str, dict]:
    """Fetch kynara-policies.json from the repo. Returns (commit_sha, parsed_json)."""
    token_bundle = connection.access_token_enc
    token = decrypt_for_tenant(token_bundle, org_id=org_id).decode()

    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    branch = connection.branch

    if connection.provider == "github":
        parts = connection.repo_url.rstrip("/").split("/")
        owner, repo = parts[-2], parts[-1]
        # Get the file content via contents API
        api_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{POLICY_FILE}?ref={branch}"
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(api_url, headers=headers)
        if resp.status_code == 404:
            raise HTTPException(404, f"{POLICY_FILE} not found in repo")
        resp.raise_for_status()
        data = resp.json()
        import base64
        content = base64.b64decode(data["content"]).decode()
        sha = data.get("sha", "")
    elif connection.provider == "gitlab":
        parts = connection.repo_url.rstrip("/").split("gitlab.com/", 1)
        project_path = parts[1].strip("/").replace("/", "%2F")
        encoded_file = POLICY_FILE.replace("/", "%2F")
        api_url = f"https://gitlab.com/api/v4/projects/{project_path}/repository/files/{encoded_file}/raw?ref={branch}"
        sha_url = f"https://gitlab.com/api/v4/projects/{project_path}/repository/commits?ref_name={branch}&per_page=1"
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(api_url, headers=headers)
            sha_resp = await client.get(sha_url, headers=headers)
        if resp.status_code == 404:
            raise HTTPException(404, f"{POLICY_FILE} not found in repo")
        resp.raise_for_status()
        content = resp.text
        sha = sha_resp.json()[0]["id"] if sha_resp.status_code == 200 else ""
    else:
        raise HTTPException(400, "Unsupported provider")

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as e:
        raise HTTPException(422, f"Invalid JSON in {POLICY_FILE}: {e}")

    return sha, parsed


async def _run_sync(connection: GitConnection, session: AsyncSession, actor: str) -> SyncResult:
    """Core sync logic — fetch + apply bundle, update connection state."""
    org_id = str(connection.organization_id)
    connection.sync_status = "syncing"
    await session.flush()

    try:
        sha, bundle_data = await _fetch_policy_file(connection, org_id)

        # Import via policy_bundle apply logic (reuse the BundleEnvelope path)
        from app.api.v1.policy_bundle import BundleEnvelope, apply_bundle
        from app.auth.dependencies import Principal as P

        # Build a synthetic principal for the bundle apply call
        fake_principal = P(
            user_id=None,
            org_id=org_id,
            seat_role="admin",
            scopes=(),
            auth_method="git_sync",
        )

        # Manually call the apply logic (not the HTTP handler)
        envelope = BundleEnvelope(**bundle_data)
        result = await apply_bundle(
            incoming=envelope,
            dry_run=False,
            principal=fake_principal,
            session=session,
        )

        connection.sync_status = "idle"
        connection.last_sync_at = datetime.now(timezone.utc)
        connection.last_sync_sha = sha[:64] if sha else None
        connection.sync_error = None

        await record_admin(
            session,
            org_id=org_id,
            actor=actor,
            event_type="git_sync.completed",
            resource_type="git_connection",
            resource_id=str(connection.id),
            payload={"sha": sha, "diff": result.get("diff")},
        )
        await session.commit()
        return SyncResult(
            sync_status="idle",
            last_sync_sha=connection.last_sync_sha,
            last_sync_at=connection.last_sync_at,
            diff=result.get("diff"),
        )

    except Exception as exc:
        connection.sync_status = "error"
        connection.sync_error = str(exc)[:1000]
        await session.commit()
        return SyncResult(
            sync_status="error",
            last_sync_sha=connection.last_sync_sha,
            last_sync_at=connection.last_sync_at,
            error=str(exc),
        )


# ─── Endpoints ────────────────────────────────────────────────────────────────


@router.post("/connect", response_model=GitConnectOut, status_code=201)
async def connect_repo(
    body: GitConnectIn,
    principal: Principal = Depends(require_seat("owner", "admin")),
    session: AsyncSession = Depends(_session),
):
    """Register a git repo for policy-as-code sync."""
    await _validate_token_and_repo(body.provider, body.repo_url, body.access_token)

    org_id = principal.org_id
    token_enc = encrypt_for_tenant(body.access_token.encode(), org_id=org_id)
    webhook_secret = secrets.token_urlsafe(32)

    conn = GitConnection(
        organization_id=uuid.UUID(org_id),
        provider=body.provider,
        repo_url=body.repo_url,
        branch=body.branch,
        access_token_enc=token_enc,
        webhook_secret=webhook_secret,
    )
    session.add(conn)
    await session.commit()
    await session.refresh(conn)
    return _row_to_out(conn)


@router.get("/connections", response_model=list[GitConnectOut])
async def list_connections(
    principal: Principal = Depends(require_seat("owner", "admin")),
    session: AsyncSession = Depends(_session),
):
    rows = (await session.scalars(
        select(GitConnection)
        .where(GitConnection.organization_id == uuid.UUID(principal.org_id))
        .order_by(GitConnection.created_at.desc())
    )).all()
    return [_row_to_out(r) for r in rows]


@router.delete("/connections/{connection_id}", status_code=204)
async def delete_connection(
    connection_id: str,
    principal: Principal = Depends(require_seat("owner", "admin")),
    session: AsyncSession = Depends(_session),
):
    conn = await session.get(GitConnection, uuid.UUID(connection_id))
    if not conn or str(conn.organization_id) != principal.org_id:
        raise HTTPException(404, "Connection not found")
    await session.delete(conn)
    await session.commit()


@router.post("/connections/{connection_id}/sync", response_model=SyncResult)
async def trigger_sync(
    connection_id: str,
    principal: Principal = Depends(require_seat("owner", "admin")),
    session: AsyncSession = Depends(_session),
):
    """Manually trigger a sync from the registered repo."""
    conn = await session.get(GitConnection, uuid.UUID(connection_id))
    if not conn or str(conn.organization_id) != principal.org_id:
        raise HTTPException(404, "Connection not found")
    if not conn.is_active:
        raise HTTPException(400, "Connection is inactive")

    actor = f"user:{principal.user_id}"
    return await _run_sync(conn, session, actor)


@router.post("/webhook", status_code=202)
async def receive_webhook(
    request: Request,
    x_hub_signature_256: str | None = Header(None),
    x_gitlab_token: str | None = Header(None),
    session: AsyncSession = Depends(_session),
):
    """Receive GitHub/GitLab push webhooks. HMAC-verified; no auth token required."""
    body = await request.body()

    # We determine which connection to use by matching the HMAC secret.
    # Iterate active connections to find the matching one.
    all_conns = (await session.scalars(
        select(GitConnection).where(GitConnection.is_active.is_(True))
    )).all()

    matched: GitConnection | None = None
    for conn in all_conns:
        secret = conn.webhook_secret.encode()
        if x_hub_signature_256:
            # GitHub: X-Hub-Signature-256: sha256=<hex>
            expected = "sha256=" + hmac.new(secret, body, hashlib.sha256).hexdigest()
            if hmac.compare_digest(expected, x_hub_signature_256):
                matched = conn
                break
        elif x_gitlab_token:
            # GitLab: X-Gitlab-Token header is the secret directly
            if hmac.compare_digest(conn.webhook_secret, x_gitlab_token):
                matched = conn
                break

    if not matched:
        raise HTTPException(401, "Invalid or missing webhook signature")

    # Only sync if kynara-policies.json was touched
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return {"accepted": False, "reason": "invalid JSON body"}

    commits = payload.get("commits", [])
    touched = any(
        POLICY_FILE in commit.get("added", [])
        or POLICY_FILE in commit.get("modified", [])
        or POLICY_FILE in commit.get("removed", [])
        for commit in commits
    )
    if not touched:
        return {"accepted": False, "reason": f"{POLICY_FILE} not modified"}

    # Async sync — run in background to return 202 quickly
    import asyncio
    asyncio.create_task(_run_sync(matched, session, actor="webhook"))
    return {"accepted": True, "connection_id": str(matched.id)}
