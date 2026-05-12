"""SSRF protection — reject URLs that resolve to internal/private network addresses.

Blocks:
  - Loopback:        127.0.0.0/8, ::1
  - RFC-1918 private: 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16
  - Link-local:      169.254.0.0/16, fe80::/10
  - Unique-local:    fc00::/7
  - Multicast:       224.0.0.0/4, ff00::/8
  - Unspecified:     0.0.0.0/8

Usage::

    from app.core.ssrf import assert_safe_url

    assert_safe_url(url)          # raises ValueError if blocked
    assert_safe_url(url, scheme_whitelist={"https"})  # also restrict scheme
"""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

# CIDR ranges that must never be reached via a user-supplied URL
_BLOCKED_NETWORKS: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = [
    # IPv4
    ipaddress.IPv4Network("0.0.0.0/8"),         # "This" network
    ipaddress.IPv4Network("10.0.0.0/8"),         # RFC-1918 private
    ipaddress.IPv4Network("100.64.0.0/10"),      # Shared address space (RFC 6598)
    ipaddress.IPv4Network("127.0.0.0/8"),        # Loopback
    ipaddress.IPv4Network("169.254.0.0/16"),     # Link-local
    ipaddress.IPv4Network("172.16.0.0/12"),      # RFC-1918 private
    ipaddress.IPv4Network("192.0.0.0/24"),       # IETF protocol assignments
    ipaddress.IPv4Network("192.168.0.0/16"),     # RFC-1918 private
    ipaddress.IPv4Network("198.18.0.0/15"),      # Benchmarking
    ipaddress.IPv4Network("198.51.100.0/24"),    # Documentation (TEST-NET-2)
    ipaddress.IPv4Network("203.0.113.0/24"),     # Documentation (TEST-NET-3)
    ipaddress.IPv4Network("224.0.0.0/4"),        # Multicast
    ipaddress.IPv4Network("240.0.0.0/4"),        # Reserved
    ipaddress.IPv4Network("255.255.255.255/32"), # Broadcast
    # IPv6
    ipaddress.IPv6Network("::1/128"),            # Loopback
    ipaddress.IPv6Network("::/128"),             # Unspecified
    ipaddress.IPv6Network("fc00::/7"),           # Unique local
    ipaddress.IPv6Network("fe80::/10"),          # Link-local
    ipaddress.IPv6Network("ff00::/8"),           # Multicast
    ipaddress.IPv6Network("::ffff:0:0/96"),      # IPv4-mapped IPv6 (covers all IPv4)
    ipaddress.IPv6Network("64:ff9b::/96"),       # IPv4/IPv6 translation
    ipaddress.IPv6Network("100::/64"),           # Discard prefix
]

_DEFAULT_SCHEMES = {"http", "https"}


def _is_blocked(addr: str) -> bool:
    """Return True if the IP address string falls within a blocked range."""
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        return True  # can't parse → block
    for net in _BLOCKED_NETWORKS:
        if ip in net:
            return True
    return False


def assert_safe_url(
    url: str,
    *,
    scheme_whitelist: set[str] | None = None,
) -> None:
    """Raise ValueError if *url* points at an internal/private network address.

    Args:
        url: The URL to validate.
        scheme_whitelist: Allowed URL schemes. Defaults to ``{"http", "https"}``.
            Pass ``{"https"}`` to require TLS.

    Raises:
        ValueError: with a human-readable message describing why the URL was blocked.
    """
    allowed_schemes = scheme_whitelist if scheme_whitelist is not None else _DEFAULT_SCHEMES

    parsed = urlparse(url)

    if parsed.scheme not in allowed_schemes:
        raise ValueError(
            f"URL scheme {parsed.scheme!r} is not allowed. "
            f"Permitted schemes: {sorted(allowed_schemes)}"
        )

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("URL has no host component")

    # Reject obvious localhost names without a DNS lookup
    if hostname.lower() in ("localhost", "localhost.localdomain", "broadcasthost"):
        raise ValueError(f"Host {hostname!r} resolves to a loopback address")

    # Reject anything that looks like a metadata service or internal DNS
    _BLOCKED_HOSTNAMES = {
        "metadata.google.internal",
        "169.254.169.254",        # AWS/GCP/Azure IMDS
        "fd00:ec2::254",          # AWS IPv6 IMDS
        "metadata.internal",
        "metadata",
    }
    if hostname.lower() in _BLOCKED_HOSTNAMES:
        raise ValueError(f"Host {hostname!r} is a blocked metadata service endpoint")

    # Try direct IP parse first (no DNS lookup needed)
    try:
        if _is_blocked(hostname):
            raise ValueError(
                f"URL resolves to a private/internal network address: {hostname}"
            )
        return  # it's a valid public IP
    except ValueError as exc:
        if "private/internal" in str(exc):
            raise
        # hostname is not a raw IP — fall through to DNS

    # Resolve via DNS and check every returned address
    try:
        # getaddrinfo returns (family, type, proto, canonname, sockaddr)
        results = socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        # Can't resolve — block (fail-closed for SSRF protection)
        raise ValueError(f"Could not resolve host {hostname!r}: {exc}") from exc

    for _family, _type, _proto, _canonname, sockaddr in results:
        ip_str = sockaddr[0]
        if _is_blocked(ip_str):
            raise ValueError(
                f"URL {url!r} resolves to a private/internal address "
                f"({hostname} → {ip_str})"
            )
