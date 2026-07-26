#!/usr/bin/env python3
"""Render OMP --mode json events as readable, line-buffered CI output."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from typing import Any

MAX_FIELD = 3000


def compact(value: Any, limit: int = MAX_FIELD) -> str:
    if isinstance(value, str):
        text = value
    else:
        text = json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)
    text = text.replace("\r", "\\r")
    if len(text) > limit:
        return text[:limit] + f"... <truncated {len(text) - limit} chars>"
    return text


def first_present(mapping: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = mapping.get(key)
        if value not in (None, "", [], {}):
            return value
    return None


def emit(message: str) -> None:
    now = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[OMP {now}] {message}", flush=True)


def render(event: dict[str, Any]) -> None:
    event_type = str(event.get("type") or "session_header")

    if event_type == "message_update":
        payload = event.get("assistantMessageEvent")
        if isinstance(payload, dict):
            update_type = str(payload.get("type") or "update")
            delta = first_present(payload, "delta", "text", "thinking", "content")
            if delta is not None:
                emit(f"{update_type}: {compact(delta)}")
            else:
                emit(f"{update_type}: {compact(payload)}")
        else:
            emit(f"message_update: {compact(event)}")
        return

    if event_type.startswith("tool_execution"):
        tool = first_present(event, "toolName", "tool_name", "name") or "unknown"
        details = first_present(event, "args", "arguments", "input", "result", "output", "error")
        emit(f"{event_type} tool={tool} details={compact(details) if details is not None else '-'}")
        return

    if event_type in {"message_start", "message_end"}:
        message = event.get("message")
        if isinstance(message, dict):
            role = message.get("role", "unknown")
            content = message.get("content")
            emit(f"{event_type} role={role} content={compact(content)}")
        else:
            emit(f"{event_type}: {compact(event)}")
        return

    if event_type in {"turn_start", "turn_end", "agent_start", "agent_end"}:
        emit(f"{event_type}: {compact(event)}")
        return

    emit(f"{event_type}: {compact(event)}")


def main() -> int:
    for raw_line in sys.stdin:
        line = raw_line.rstrip("\n")
        if not line:
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            emit(f"raw: {compact(line)}")
            continue
        if isinstance(value, dict):
            render(value)
        else:
            emit(f"json: {compact(value)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
