"""Parsing and prompt-safe helpers for the no-skill Phase 1 policies."""

from __future__ import annotations

import json
from typing import Any

from legal_skill_guard.schemas.trajectory import Action


def _balanced_json_objects(text: str) -> list[str]:
    objects: list[str] = []
    start: int | None = None
    depth = 0
    quoted = False
    escaped = False
    for index, char in enumerate(text):
        if escaped:
            escaped = False
            continue
        if char == "\\" and quoted:
            escaped = True
            continue
        if char == '"':
            quoted = not quoted
            continue
        if quoted:
            continue
        if char == "{":
            if depth == 0:
                start = index
            depth += 1
        elif char == "}" and depth:
            depth -= 1
            if depth == 0 and start is not None:
                objects.append(text[start : index + 1])
                start = None
    return objects


def _action_from_object(value: Any, raw: str, mode: str) -> Action | None:
    if not isinstance(value, dict):
        return None
    tool = value.get("tool")
    if tool == "talk_to_client":
        content = str(value.get("message") or "").strip()
    elif tool == "write_memo":
        content = str(value.get("content") or "").strip()
    else:
        return None
    if not content:
        return None
    return Action(tool=tool, content=content, parse_mode=mode, raw_model_output=raw)


def parse_lawyer_action(text: str) -> Action:
    raw = text.strip()
    try:
        action = _action_from_object(json.loads(raw), raw, "json")
    except json.JSONDecodeError:
        action = None
    if action is not None:
        return action
    for candidate in _balanced_json_objects(raw):
        try:
            action = _action_from_object(json.loads(candidate), raw, "json_fragment")
        except json.JSONDecodeError:
            continue
        if action is not None:
            return action
    return Action(
        tool="talk_to_client",
        content=raw,
        parse_mode="fallback",
        raw_model_output=raw,
    )
