"""Policy Template Marketplace endpoints.

Provides pre-built policy definitions that orgs can browse and install
with a single API call. Also supports creating custom org-private templates.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import Principal, get_principal, require_seat
from app.db.session import SessionLocal
from app.models import Policy
from app.models.policy_template import PolicyTemplate

router = APIRouter(prefix="/templates", tags=["policy-templates"])


async def _session():
    async with SessionLocal() as s:
        yield s


# ─── Schemas ──────────────────────────────────────────────────────────────────


class TemplateOut(BaseModel):
    id: str
    slug: str
    display_name: str
    description: str
    category: str
    author: str
    tags: list[str]
    install_count: int
    is_published: bool
    created_at: datetime


class TemplateDetailOut(TemplateOut):
    template_data: dict[str, Any]


class TemplateCreateIn(BaseModel):
    slug: str
    display_name: str
    description: str = ""
    category: str = "general"
    template_data: dict[str, Any]
    tags: list[str] = []


class InstallResult(BaseModel):
    template_slug: str
    created_policy_ids: list[str]
    skipped_slugs: list[str]  # slugs that already existed in the org


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _row_to_out(row: PolicyTemplate) -> TemplateOut:
    return TemplateOut(
        id=str(row.id),
        slug=row.slug,
        display_name=row.display_name,
        description=row.description,
        category=row.category,
        author=row.author,
        tags=row.tags or [],
        install_count=row.install_count,
        is_published=row.is_published,
        created_at=row.created_at,
    )


def _row_to_detail(row: PolicyTemplate) -> TemplateDetailOut:
    base = _row_to_out(row)
    return TemplateDetailOut(**base.model_dump(), template_data=row.template_data)


# ─── Endpoints ────────────────────────────────────────────────────────────────


@router.get("", response_model=list[TemplateOut])
async def list_templates(
    category: str | None = Query(None, description="Filter by category"),
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(_session),
):
    """List all published templates, optionally filtered by category."""
    q = select(PolicyTemplate).where(PolicyTemplate.is_published.is_(True))
    if category:
        q = q.where(PolicyTemplate.category == category)
    q = q.order_by(PolicyTemplate.install_count.desc(), PolicyTemplate.display_name)
    rows = (await session.scalars(q)).all()
    return [_row_to_out(r) for r in rows]


@router.get("/{slug}", response_model=TemplateDetailOut)
async def get_template(
    slug: str,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(_session),
):
    """Get a single template including its full template_data."""
    row = await session.scalar(
        select(PolicyTemplate).where(PolicyTemplate.slug == slug, PolicyTemplate.is_published.is_(True))
    )
    if not row:
        raise HTTPException(404, f"Template '{slug}' not found")
    return _row_to_detail(row)


@router.post("/{slug}/install", response_model=InstallResult)
async def install_template(
    slug: str,
    principal: Principal = Depends(require_seat("owner", "admin")),
    session: AsyncSession = Depends(_session),
):
    """Create Policy rows from a template for the calling org.

    Policies that already exist (matching slug) are skipped rather than
    overwritten so existing customisations are preserved.
    Increments the template's install_count.
    """
    template = await session.scalar(
        select(PolicyTemplate).where(PolicyTemplate.slug == slug, PolicyTemplate.is_published.is_(True))
    )
    if not template:
        raise HTTPException(404, f"Template '{slug}' not found")

    org_id = uuid.UUID(principal.org_id)
    policies_data: list[dict] = template.template_data.get("policies", [])

    # Fetch existing slugs for this org to detect conflicts
    existing_slugs = set(
        (await session.scalars(
            select(Policy.slug).where(Policy.organization_id == org_id)
        )).all()
    )

    created_ids: list[str] = []
    skipped: list[str] = []

    for p_def in policies_data:
        p_slug = p_def.get("slug", "")
        if p_slug in existing_slugs:
            skipped.append(p_slug)
            continue

        new_policy = Policy(
            organization_id=org_id,
            slug=p_slug,
            display_name=p_def.get("display_name", p_slug),
            description=p_def.get("description"),
            effect=p_def.get("effect", "allow"),
            priority=p_def.get("priority", 500),
            actions=p_def.get("actions", []),
            resource_types=p_def.get("resource_types", []),
            condition=p_def.get("condition") or {},
            is_enabled=p_def.get("is_enabled", True),
        )
        session.add(new_policy)
        await session.flush()  # get the id
        created_ids.append(str(new_policy.id))

    # Increment install count
    template.install_count = (template.install_count or 0) + 1

    await session.commit()
    return InstallResult(
        template_slug=slug,
        created_policy_ids=created_ids,
        skipped_slugs=skipped,
    )


@router.post("", response_model=TemplateDetailOut, status_code=201)
async def create_template(
    body: TemplateCreateIn,
    principal: Principal = Depends(require_seat("owner", "admin")),
    session: AsyncSession = Depends(_session),
):
    """Create a custom (org-private) template.

    The template is published globally so other orgs can discover it.
    To keep it private, extend this endpoint with an org_id foreign key.
    """
    # Check slug uniqueness
    existing = await session.scalar(
        select(PolicyTemplate).where(PolicyTemplate.slug == body.slug)
    )
    if existing:
        raise HTTPException(409, f"Template slug '{body.slug}' already exists")

    t = PolicyTemplate(
        slug=body.slug,
        display_name=body.display_name,
        description=body.description,
        category=body.category,
        author=f"org:{principal.org_id}",
        template_data=body.template_data,
        tags=body.tags,
    )
    session.add(t)
    await session.commit()
    await session.refresh(t)
    return _row_to_detail(t)
