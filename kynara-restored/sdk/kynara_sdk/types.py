from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class DecisionEffect(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"


@dataclass
class Resource:
    type: str | None = None
    id: str | None = None
    attrs: dict[str, Any] = field(default_factory=dict)


@dataclass
class Decision:
    effect: DecisionEffect
    reason: str
    matched_policy_id: str | None = None
    obligations: list[dict[str, Any]] = field(default_factory=list)
