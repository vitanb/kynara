import re

from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import SessionLocal

router = APIRouter(tags=["health"])

# Update this whenever a new migration is added.
_EXPECTED_MIGRATION_HEAD = "20260505_0012"


def _masked_url(url: str) -> str:
    """Hide password in DSN but keep host/dbname visible."""
    return re.sub(r"://[^@]+@", "://*****@", url)


@router.get("/health", include_in_schema=False)
async def health():
    """Liveness probe — resolves to /api/v1/health via the v1 router prefix.
    Used by Railway healthcheckPath = /api/v1/health in railway.toml.
    """
    try:
        async with SessionLocal() as s:
            await s.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception as e:
        return {"status": "degraded", "error": str(e)}


@router.get("/ready", include_in_schema=False)
async def ready():
    """Readiness probe — checks DB connection AND migration head."""
    try:
        async with SessionLocal() as s:
            row = await s.execute(text("SELECT version_num FROM alembic_version"))
            versions = [r[0] for r in row]
        head_ok = any(_EXPECTED_MIGRATION_HEAD in v for v in versions)
        if not head_ok:
            return {
                "status": "not_ready",
                "reason": "migrations_behind",
                "current": versions,
                "expected_head": _EXPECTED_MIGRATION_HEAD,
            }
        return {"status": "ready", "migration_head": versions}
    except Exception as e:
        return {"status": "not_ready", "reason": str(e)}


@router.get("/debug/db", include_in_schema=False)
async def debug_db():
    """Diagnostic: DB connection, migration state, row counts.
    Disabled in prod environments.
    """
    settings = get_settings()
    if settings.env == "prod":
        from fastapi import HTTPException
        raise HTTPException(404)

    result: dict = {"database_url": _masked_url(settings.database_url)}
    try:
        async with SessionLocal() as s:
            try:
                rows = await s.execute(text("SELECT version_num FROM alembic_version"))
                versions = [r[0] for r in rows]
                result["alembic_versions"] = versions
                result["migration_head_ok"] = any(_EXPECTED_MIGRATION_HEAD in v for v in versions)
            except Exception as e:
                result["alembic_versions"] = f"ERROR: {e}"

            for table in ("organizations", "users", "agents", "tools", "policies"):
                try:
                    count = (await s.execute(text(f"SELECT count(*) FROM {table}"))).scalar()
                    result[f"count_{table}"] = count
                except Exception as e:
                    result[f"count_{table}"] = f"ERROR: {e}"

            row = (await s.execute(text(
                "SELECT current_database(), inet_server_addr()::text, inet_server_port()"
            ))).one()
            result["pg_database"] = row[0]
            result["pg_host"] = row[1]
            result["pg_port"] = row[2]

        result["status"] = "ok"
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
    return result
