"""LangChain callback — enforce permissions on every tool call.

Usage:
    from kynara_sdk import Kynara
    from kynara_sdk.langchain import KynaraCallbackHandler

    kynara = Kynara(api_key=..., agent_id="crm-assistant", user_id=current_user_id)
    agent.callbacks = [KynaraCallbackHandler(kynara)]

The handler intercepts ``on_tool_start`` and calls ``kynara.enforce`` using the tool's
name as the action. Denied calls raise, halting the agent before any side-effect.
"""
from __future__ import annotations

from typing import Any

try:
    from langchain_core.callbacks.base import BaseCallbackHandler  # type: ignore
except ImportError:  # pragma: no cover
    BaseCallbackHandler = object  # stub — importing this module still works

from kynara_sdk.client import Kynara
from kynara_sdk.types import Resource


class KynaraCallbackHandler(BaseCallbackHandler):
    def __init__(self, kynara: Kynara, *, action_prefix: str = ""):
        self.kynara = kynara
        self.action_prefix = action_prefix

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        **kwargs: Any,
    ) -> Any:
        name = (self.action_prefix + serialized.get("name", "unknown")).strip(".")
        # LangChain packs the parsed args in kwargs["inputs"] sometimes; best-effort:
        inputs = kwargs.get("inputs") or {}
        resource_id = inputs.get("id") or inputs.get("resource_id")
        self.kynara.enforce(
            action=name,
            resource=Resource(id=str(resource_id) if resource_id else None,
                              attrs=inputs if isinstance(inputs, dict) else {}),
            context={"framework": "langchain"},
        )
