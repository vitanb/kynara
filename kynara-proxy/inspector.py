"""
Kynara Proxy - request / response inspector.

Identifies tool calls inside OpenAI, Anthropic, and generic JSON payloads so
the proxy knows what to check policy against before forwarding.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCall:
    tool_name: str
    arguments: dict[str, Any]
    tool_call_id: str | None = None
    source: str = "generic"   # "openai" | "anthropic" | "generic"


@dataclass
class InspectionResult:
    tool_calls: list[ToolCall] = field(default_factory=list)
    has_tool_definitions: bool = False
    body: dict[str, Any] | None = None

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0


def inspect_request(raw_body: bytes, content_type: str, path: str) -> InspectionResult:
    result = InspectionResult()

    if "json" not in content_type.lower():
        return result

    try:
        body = json.loads(raw_body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return result

    if not isinstance(body, dict):
        return result

    result.body = body

    # Check Anthropic FIRST — it also uses "messages" so must come before OpenAI check
    if "anthropic-version" in path.lower() or _looks_like_anthropic(body):
        _extract_anthropic(body, result)
    elif "messages" in body or _looks_like_openai(path, body):
        _extract_openai(body, result)
    else:
        _extract_generic(body, result)

    return result


def inspect_response(raw_body: bytes, content_type: str) -> InspectionResult:
    result = InspectionResult()

    if "json" not in content_type.lower():
        return result

    try:
        body = json.loads(raw_body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return result

    if not isinstance(body, dict):
        return result

    result.body = body

    # OpenAI response: choices[].message.tool_calls
    for choice in body.get("choices", []):
        msg = choice.get("message", {})
        for tc in msg.get("tool_calls", []):
            fn = tc.get("function", {})
            try:
                args = json.loads(fn.get("arguments", "{}"))
            except json.JSONDecodeError:
                args = {"_raw": fn.get("arguments", "")}
            result.tool_calls.append(ToolCall(
                tool_name=fn.get("name", "unknown"),
                arguments=args,
                tool_call_id=tc.get("id"),
                source="openai",
            ))

    # Anthropic response: content[].type == "tool_use"
    for block in body.get("content", []):
        if block.get("type") == "tool_use":
            result.tool_calls.append(ToolCall(
                tool_name=block.get("name", "unknown"),
                arguments=block.get("input", {}),
                tool_call_id=block.get("id"),
                source="anthropic",
            ))

    return result


def _looks_like_openai(path: str, body: dict) -> bool:
    return (
        "completions" in path
        or "chat" in path
        or ("model" in body and "messages" in body and "max_tokens" not in body)
    )


def _looks_like_anthropic(body: dict) -> bool:
    model = str(body.get("model", "")).lower()
    return (
        "anthropic" in model
        or "claude" in model
        or ("messages" in body and "max_tokens" in body)
    )


def _extract_openai(body: dict, result: InspectionResult) -> None:
    if body.get("tools"):
        result.has_tool_definitions = True
    for msg in body.get("messages", []):
        for tc in msg.get("tool_calls", []):
            fn = tc.get("function", {})
            try:
                args = json.loads(fn.get("arguments", "{}"))
            except json.JSONDecodeError:
                args = {"_raw": fn.get("arguments", "")}
            result.tool_calls.append(ToolCall(
                tool_name=fn.get("name", "unknown"),
                arguments=args,
                tool_call_id=tc.get("id"),
                source="openai",
            ))


def _extract_anthropic(body: dict, result: InspectionResult) -> None:
    if body.get("tools"):
        result.has_tool_definitions = True
    for msg in body.get("messages", []):
        content = msg.get("content", [])
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    result.tool_calls.append(ToolCall(
                        tool_name=block.get("name", "unknown"),
                        arguments=block.get("input", {}),
                        tool_call_id=block.get("id"),
                        source="anthropic",
                    ))


def _extract_generic(body: dict, result: InspectionResult) -> None:
    tool_name = (
        body.get("tool")
        or body.get("function")
        or body.get("action")
        or body.get("name")
    )
    if tool_name and isinstance(tool_name, str):
        arguments = (
            body.get("params")
            or body.get("arguments")
            or body.get("input")
            or body.get("kwargs")
            or {k: v for k, v in body.items()
                if k not in ("tool", "function", "action", "name")}
        )
        result.tool_calls.append(ToolCall(
            tool_name=tool_name,
            arguments=arguments if isinstance(arguments, dict) else {},
            source="generic",
        ))


def rewrite_deny_in_response(
    body: dict[str, Any], tc: ToolCall, reason: str
) -> None:
    """Mutate body in-place to strip a denied tool call from an LLM response."""
    if tc.source == "openai":
        for choice in body.get("choices", []):
            msg = choice.get("message", {})
            msg["tool_calls"] = [
                t for t in msg.get("tool_calls", [])
                if t.get("function", {}).get("name") != tc.tool_name
            ]
            if not msg["tool_calls"]:
                choice["finish_reason"] = "stop"
                msg["content"] = (
                    f"[Kynara] Tool '{tc.tool_name}' is not permitted. Reason: {reason}"
                )
    elif tc.source == "anthropic":
        new_content = []
        for block in body.get("content", []):
            if block.get("type") == "tool_use" and block.get("name") == tc.tool_name:
                new_content.append({
                    "type": "text",
                    "text": f"[Kynara] Tool '{tc.tool_name}' was blocked. Reason: {reason}",
                })
            else:
                new_content.append(block)
        body["content"] = new_content
        body["stop_reason"] = "end_turn"
