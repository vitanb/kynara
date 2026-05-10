"""Lightweight GeoIP resolution via ip-api.com (free, no API key required).

Results are cached in Redis for 24 hours so repeated decisions from the same
IP don't add latency. Private / loopback addresses resolve to "PRIVATE"
without a network call.

Usage:
    country = await resolve_country("203.0.113.42")   # → "US"
    country = await resolve_country("127.0.0.1")       # → "PRIVATE"
    country = await resolve_country(None)              # → None
"""
from __future__ import annotations

import ipaddress
import json
import logging

import httpx
import redis.asyncio as redis_async

from app.core.config import get_settings

log = logging.getLogger("kynara.geoip")

_CACHE_TTL = 86_400          # 24 hours — country-level geo is very stable
_TIMEOUT   = 2.0             # seconds — never block the hot path for long
_API_URL   = "http://ip-api.com/json/{ip}?fields=status,countryCode"

_redis: redis_async.Redis | None = None


async def _r() -> redis_async.Redis:
    global _redis
    if _redis is None:
        _redis = redis_async.from_url(
            str(get_settings().redis_url), decode_responses=True
        )
    return _redis


def _is_private(ip: str) -> bool:
    """Return True for loopback, link-local, private, and unspecified addresses."""
    try:
        addr = ipaddress.ip_address(ip)
        return addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_unspecified
    except ValueError:
        return False


async def resolve_country(ip: str | None) -> str | None:
    """Return the ISO 3166-1 alpha-2 country code for *ip*, or None on failure.

    Returns the special sentinel ``"PRIVATE"`` for RFC-1918 / loopback addresses
    so policies can explicitly match (or ignore) internal traffic.
    """
    if not ip:
        return None
    if _is_private(ip):
        return "PRIVATE"

    cache = await _r()
    cache_key = f"geoip:{ip}"

    cached = await cache.get(cache_key)
    if cached:
        return cached if cached != "__null__" else None

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(_API_URL.format(ip=ip))
            resp.raise_for_status()
            data = resp.json()

        if data.get("status") == "success":
            country = data.get("countryCode")
            await cache.setex(cache_key, _CACHE_TTL, country or "__null__")
            return country
        else:
            # ip-api returns status=fail for reserved ranges it doesn't recognise
            await cache.setex(cache_key, _CACHE_TTL, "__null__")
            return None

    except Exception as exc:
        # Never let a GeoIP failure block a policy decision — just log and continue.
        log.warning("geoip.resolve_failed", ip=ip, error=str(exc))
        return None
