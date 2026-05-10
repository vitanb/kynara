"""Tool registry."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import record_admin
from app.auth.dependencies import Principal, get_principal, require_seat
from app.db.session import SessionLocal
from app.models import Tool, ToolScope

router = APIRouter(prefix="/tools", tags=["tools"])


async def _session():
    async with SessionLocal() as s:
        yield s


class ToolIn(BaseModel):
    namespace: str = Field(pattern=r"^[a-z0-9][a-z0-9_]*$")
    name: str = Field(pattern=r"^[a-z0-9][a-z0-9_.]*$")
    description: str | None = None
    risk_class: str = Field(default="low", pattern=r"^(low|medium|high|critical)$")
    input_schema: dict = Field(default_factory=dict)
    scopes: list[str] = Field(default_factory=list)


class ToolOut(ToolIn):
    id: str
    is_enabled: bool


@router.get("", response_model=list[ToolOut])
async def list_tools(principal: Principal = Depends(get_principal), session: AsyncSession = Depends(_session)):
    rows = (await session.scalars(
        select(Tool).where(Tool.organization_id == uuid.UUID(principal.org_id))
        .order_by(Tool.namespace, Tool.name)
    )).all()
    out: list[ToolOut] = []
    for t in rows:
        scopes = (await session.scalars(
            select(ToolScope.scope).where(ToolScope.tool_id == t.id)
        )).all()
        out.append(ToolOut(
            id=str(t.id),
            namespace=t.namespace, name=t.name,
            description=t.description, risk_class=t.risk_class,
            input_schema=t.input_schema, scopes=list(scopes),
            is_enabled=t.is_enabled,
        ))
    return out


@router.post("", response_model=ToolOut, status_code=201)
async def create_tool(
    body: ToolIn, request: Request,
    principal: Principal = Depends(require_seat("owner", "admin", "developer")),
    session: AsyncSession = Depends(_session),
):
    t = Tool(
        organization_id=uuid.UUID(principal.org_id),
        namespace=body.namespace, name=body.name,
        description=body.description, risk_class=body.risk_class,
        input_schema=body.input_schema,
    )
    session.add(t)
    await session.flush()
    for s in body.scopes:
        session.add(ToolScope(tool_id=t.id, scope=s))
    await session.flush()

    await record_admin(
        session, org_id=principal.org_id,
        actor=f"user:{principal.user_id}" if principal.user_id else "system",
        event_type="tool.created",
        resource_type="tool",
        resource_id=str(t.id),
        payload={"namespace": body.namespace, "name": body.name, "risk_class": body.risk_class},
        ip_address=request.client.host if request.client else None,
    )
    return ToolOut(id=str(t.id), **body.model_dump(), is_enabled=True)


class ToolUpdate(BaseModel):
    description: str | None = None
    risk_class: str = Field(default="low", pattern=r"^(low|medium|high|critical)$")
    input_schema: dict = Field(default_factory=dict)
    scopes: list[str] = Field(default_factory=list)
    is_enabled: bool = True


@router.put("/{tool_id}")
async def update_tool(
    tool_id: str, body: ToolUpdate, request: Request,
    principal: Principal = Depends(require_seat("owner", "admin", "developer")),
    session: AsyncSession = Depends(_session),
):
    t = await session.get(Tool, uuid.UUID(tool_id))
    if not t or t.organization_id != uuid.UUID(principal.org_id):
        raise HTTPException(404, "Tool not found")

    t.description = body.description
    t.risk_class = body.risk_class
    t.input_schema = body.input_schema
    t.is_enabled = body.is_enabled

    # Replace scopes
    existing_scopes = (await session.scalars(
        select(ToolScope).where(ToolScope.tool_id == t.id)
    )).all()
    for s in existing_scopes:
        await session.delete(s)
    await session.flush()
    for s in body.scopes:
        session.add(ToolScope(tool_id=t.id, scope=s))
    await session.flush()

    await record_admin(
        session, org_id=principal.org_id,
        actor=f"user:{principal.user_id}" if principal.user_id else "system",
        event_type="tool.updated",
        resource_type="tool",
        resource_id=tool_id,
        payload={"risk_class": body.risk_class, "is_enabled": body.is_enabled},
        ip_address=request.client.host if request.client else None,
    )
    await session.commit()

    scopes = (await session.scalars(
        select(ToolScope.scope).where(ToolScope.tool_id == t.id)
    )).all()
    return ToolOut(
        id=str(t.id), namespace=t.namespace, name=t.name,
        description=t.description, risk_class=t.risk_class,
        input_schema=t.input_schema, scopes=list(scopes),
        is_enabled=t.is_enabled,
    )
