import re

from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import SessionLocal

router = APIRouter(tags=["health"])


def _masked_url(url: str) -> str:
    """Hide password in DSN but keep host/dbname visible."""
    return re.sub(r"://[^@]+@", "://*****@", url)


@router.get("/health", include_in_schema=False)
async def health():
    try:
        async with SessionLocal() as s:
            await s.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception as e:
        return {"status": "degraded", "error": str(e)}


@router.get("/ready", include_in_schema=False)
async def ready():
    return {"status": "ready"}


@router.get("/debug/db", include_in_schema=False)
async def debug_db():
    """Temporary diagnostic: shows which DB the backend is connected to
    and whether migrations + seed data are present.
    Remove this endpoint before going to production.
    """
    settings = get_settings()
    result: dict = {
        "database_url": _masked_url(settings.database_url),
    }
    try:
        async with SessionLocal() as s:
            # Alembic migration state
            try:
                rows = await s.execute(text("SELECT version_num FROM alembic_version"))
                result["alembic_versions"] = [r[0] for r in rows]
            except Exception as e:
                result["alembic_versions"] = f"ERROR: {e}"

            # Row counts for key tables
            for table in ("organizations", "users", "agents", "tools", "policies"):
                try:
                    count = (await s.execute(text(f"SELECT count(*) FROM {table}"))).scalar()
                    result[f"count_{table}"] = count
                except Exception as e:
                    result[f"count_{table}"] = f"ERROR: {e}"

            # Current Postgres connection info
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
