"""Global SlowAPI rate-limiter instance.

Import this module (not app.main) to apply @limiter.limit() decorators
to individual route functions. Using a single shared instance ensures all
decorated routes share the same backend and configuration.

Usage::

    from app.core.limiter import limiter

    @router.post("/login")
    @limiter.limit("10/minute")
    async def login(request: Request, ...):
        ...
"""
from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
