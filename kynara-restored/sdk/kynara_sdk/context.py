"""Ambient Kynara client (ContextVar-backed) so decorators need no plumbing."""
from __future__ import annotations

from contextvars import ContextVar
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kynara_sdk.client import Kynara

_current: ContextVar["Kynara | None"] = ContextVar("kynara_client", default=None)


def set_current_kynara(client) -> None:
    _current.set(client)


def current_kynara():
    return _current.get()
