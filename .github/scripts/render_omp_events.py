#!/usr/bin/env python3
"""Render OMP --mode json events as concise, line-buffered CI output."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from typing import Any

MAX_MESSAGE_FIELD = 1200
MAX_TOOL_FIELD = 500
IGNORED_MESSAGE_UPDATE_TYPES = {"thinking_delta", "toolcall_delta"}


def compact(value: Any, limit: int) -> str:
    if isinstance(value, str):
        text = value
    else:
        text = json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)
    text = text.replace("\r", "\\r").replace("\n", "\\n")
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


def task_tool_summary(details: Any) -> str:
    if not isinstance(details, dict):
        return compact(details, MAX_TOOL_FIELD)

    parts: list[str] = []
    tasks = details.get("tasks")
    if isinstance(tasks, list):
        names = [str(task.get("name")) for task in tasks if isinstance(task, dict) and task.get("name")]
        parts.append(f"tasks={len(tasks)}")
        if names:
            parts.append("names=" + ",".join(names[:8]))

    context = details.get("context")
    if isinstance(context, str):
        parts.append(f"context_chars={len(context)}")

    for key in ("status", "state", "agentId", "agent_id", "jobId", "job_id", "isError", "error"):
        value = details.get(key)
        if value not in (None, "", [], {}):
            parts.append(f"{key}={compact(value, 160)}")

    result = details.get("result")
    if isinstance(result, dict):
        for key in ("status", "agentId", "agent_id", "jobId", "job_id", "commit", "branch"):
            value = result.get(key)
            if value not in (None, "", [], {}):
                parts.append(f"result.{key}={compact(value, 160)}")
    elif result not in (None, "", [], {}):
        parts.append(f"result={compact(result, 240)}")

    return " ".join(parts) if parts else compact(details, MAX_TOOL_FIELD)


def tool_summary(tool: str, event: dict[str, Any]) -> str:
    details = first_present(event, "args", "arguments", "input", "result", "output", "error")
    if details is None:
        return "details=-"
    if tool == "task":
        return task_tool_summary(details)
    return "details=" + compact(details, MAX_TOOL_FIELD)


def render(event: dict[str, Any], last_tool_updates: dict[str, str]) -> None:
    event_type = str(event.get("type") or "session_header")

    if event_type == "message_update":
        payload = event.get("assistantMessageEvent")
        if isinstance(payload, dict):
            update_type = str(payload.get("type") or "update")
            if update_type in IGNORED_MESSAGE_UPDATE_TYPES:
                return
            delta = first_present(payload, "delta", "text", "thinking", "content")
            if isinstance(delta, str) and not delta.strip():
                delta = None
            if delta is not None:
                emit(f"{update_type}: {compact(delta, MAX_MESSAGE_FIELD)}")
            elif update_type in {"done", "error"}:
                emit(f"{update_type}: {compact(payload, MAX_MESSAGE_FIELD)}")
        return

    if event_type.startswith("tool_execution"):
        tool = str(first_present(event, "toolName", "tool_name", "name") or "unknown")
        call_id = str(first_present(event, "toolCallId", "tool_call_id", "id") or tool)
        summary = tool_summary(tool, event)

        if event_type == "tool_execution_update":
            if last_tool_updates.get(call_id) == summary:
                return
            last_tool_updates[call_id] = summary

        emit(f"{event_type} tool={tool} {summary}")
        if event_type == "tool_execution_end":
            last_tool_updates.pop(call_id, None)
        return

    if event_type in {"message_start", "message_end"}:
        message = event.get("message")
        if isinstance(message, dict):
            role = message.get("role", "unknown")
            content = message.get("content")
            emit(f"{event_type} role={role} content={compact(content, MAX_MESSAGE_FIELD)}")
        else:
            emit(f"{event_type}: {compact(event, MAX_MESSAGE_FIELD)}")
        return

    if event_type in {"turn_start", "turn_end", "agent_start", "agent_end"}:
        emit(f"{event_type}: {compact(event, MAX_MESSAGE_FIELD)}")
        return

    emit(f"{event_type}: {compact(event, MAX_MESSAGE_FIELD)}")


def main() -> int:
    emit("renderer START")
    last_tool_updates: dict[str, str] = {}
    for raw_line in sys.stdin:
        line = raw_line.rstrip("\n")
        if not line:
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            emit(f"raw: {compact(line, MAX_MESSAGE_FIELD)}")
            continue
        if isinstance(value, dict):
            render(value, last_tool_updates)
        else:
            emit(f"json: {compact(value, MAX_MESSAGE_FIELD)}")
    emit("renderer DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
