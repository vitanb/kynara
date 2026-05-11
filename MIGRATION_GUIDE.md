# Database Migration Guide

## How migrations run

Migrations run automatically on every deploy via `entrypoint.sh`:

```sh
alembic upgrade head
```

`alembic.ini` points to `app/db/migrations` as the script location.
`env.py` overrides the DB URL at runtime from the `DATABASE_URL` env var.

## Required environment variables (deployment fails without these)

| Variable | Description |
|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://user:pass@host:5432/dbname` |
| `JWT_SECRET` | Random 32+ char string. Never use the default. |

## Current migration chain

| # | Revision | Description |
|---|---|---|
| 01 | `0001_initial` | Core schema — orgs, users, agents, tools, policies, audit |
| 02 | `0002_org_invites` | Org invitation tokens |
| 03 | `0003_password_reset_tokens` | Password reset flow |
| 04 | `0004_approval_requests` | Approval workflow |
| 05 | `20260428_0005` | Webhooks — endpoints + outbox |
| 06 | `20260428_0006` | BYOK / tenant key residency |
| 07 | `20260501_0007` | Agent risk score column |
| 08 | `20260501_0008` | JIT grants |
| 09 | `20260501_0009` | Guardrail integrations + events |
| 10 | `20260502_0010` | Guardrail rules |
| 11 | `20260504_0011` | User profile fields (avatar, job title, timezone) |
| 12 | `20260505_0012` | Superadmin flag on users |

**Head:** `20260505_0012`

## Adding a new migration

```sh
cd backend
alembic revision --autogenerate -m "short_description"
# Review generated file in app/db/migrations/versions/
# Update _EXPECTED_MIGRATION_HEAD in app/api/v1/health.py
```

## Verifying migration state on live deployment

```sh
curl https://kynaraai.com/api/v1/ready
# {"status": "ready", "migration_head": ["20260505_0012"]}
```

If `status` is `not_ready` with `reason: migrations_behind`, migrations didn't apply.

## Rolling back (emergency only — take a DB backup first)

```sh
alembic downgrade -1                  # one step back
alembic downgrade <revision_id>       # to a specific revision
```
