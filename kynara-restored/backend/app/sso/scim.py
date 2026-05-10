"""SCIM 2.0 server (RFC 7644) for automated user & group provisioning from Okta.

Implemented endpoints (see app.api.v1.scim):
  * GET /Users, POST /Users, PUT /Users/{id}, PATCH /Users/{id}, DELETE /Users/{id}
  * GET /Groups, POST /Groups, PATCH /Groups/{id}

SCIM auth uses a bearer token generated per-org in the Kynara UI. The token is scoped
only to SCIM operations and rate-limited separately.
"""
from __future__ import annotations

from typing import Any


def user_to_scim(user, memberships) -> dict[str, Any]:
    return {
        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
        "id": str(user.id),
        "userName": user.email,
        "active": user.is_active,
        "name": {"formatted": user.display_name or ""},
        "emails": [{"value": user.email, "primary": True}],
        "meta": {
            "resourceType": "User",
            "created": user.created_at.isoformat(),
            "lastModified": user.updated_at.isoformat(),
        },
        "groups": [
            {"value": str(m.organization_id), "display": m.seat_role}
            for m in memberships
        ],
    }


def scim_error(status: int, detail: str) -> dict[str, Any]:
    return {
        "schemas": ["urn:ietf:params:scim:api:messages:2.0:Error"],
        "status": str(status),
        "detail": detail,
    }
