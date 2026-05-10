"""@permission_required decorator.

Resolves the current ``Kynara`` client from either an explicit arg or a threadlocal
(``kynara_sdk.context.current``) so agents built on different frameworks can share
the same decorator without plumbing.
"""
from __future__ import annotations

import functools
import inspect
from typing import Any, Callable

from kynara_sdk.context import current_kynara
from kynara_sdk.types import Resource


def permission_required(
    action: str,
    *,
    resource_arg: str | None = None,
    resource_type: str | None = None,
    resource_attrs: dict[str, Any] | Callable[..., dict[str, Any]] | None = None,
    context_fn: Callable[..., dict[str, Any]] | None = None,
    client_kw: str = "kynara",
):
    """Enforce ``action`` before the wrapped callable runs.

    Args:
        action: The action namespace, e.g. ``crm.contacts.read``.
        resource_arg: Name of the wrapped function's kwarg carrying the resource id.
        resource_type: Optional type string passed through to the policy engine.
        resource_attrs: Static attrs dict or a callable taking the same (*args, **kwargs)
                        as the wrapped function that returns attrs.
        context_fn: Optional callable taking (*args, **kwargs) that returns extra context.
        client_kw: Optional kwarg on the wrapped function carrying a Kynara instance.
    """

    def deco(fn):
        sig = inspect.signature(fn)

        @functools.wraps(fn)
        def wrapped(*args, **kwargs):
            kynara = kwargs.pop(client_kw, None) or current_kynara()
            if kynara is None:
                raise RuntimeError(
                    "No Kynara client. Pass `kynara=...` or use set_current_kynara(...)."
                )
            bound = sig.bind_partial(*args, **kwargs)
            bound.apply_defaults()

            resource = Resource(type=resource_type)
            if resource_arg and resource_arg in bound.arguments:
                resource.id = str(bound.arguments[resource_arg])
            if resource_attrs:
                if callable(resource_attrs):
                    resource.attrs = resource_attrs(*args, **kwargs)
                else:
                    resource.attrs = dict(resource_attrs)

            ctx = context_fn(*args, **kwargs) if context_fn else {}
            kynara.enforce(action=action, resource=resource, context=ctx)
            return fn(*args, **kwargs)

        @functools.wraps(fn)
        async def awrapped(*args, **kwargs):
            kynara = kwargs.pop(client_kw, None) or current_kynara()
            if kynara is None:
                raise RuntimeError("No Kynara client.")
            bound = sig.bind_partial(*args, **kwargs)
            bound.apply_defaults()

            resource = Resource(type=resource_type)
            if resource_arg and resource_arg in bound.arguments:
                resource.id = str(bound.arguments[resource_arg])
            if resource_attrs:
                resource.attrs = (resource_attrs(*args, **kwargs)
                                  if callable(resource_attrs) else dict(resource_attrs))
            ctx = context_fn(*args, **kwargs) if context_fn else {}
            kynara.enforce(action=action, resource=resource, context=ctx)
            return await fn(*args, **kwargs)

        return awrapped if inspect.iscoroutinefunction(fn) else wrapped

    return deco
