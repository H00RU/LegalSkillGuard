"""Parsing and prompt-safe helpers for the no-skill Phase 1 policies."""

from __future__ import annotations

import json
import re
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
    repaired_alias = tool == "talk_to_to_client"
    if tool == "talk_to_client" or repaired_alias:
        content = str(value.get("message") or "").strip()
    elif tool == "write_memo":
        content = str(value.get("content") or "").strip()
    else:
        return None
    if not content:
        return None
    normalized_tool = "talk_to_client" if repaired_alias else tool
    return Action(
        tool=normalized_tool,
        content=content,
        parse_mode="fallback" if repaired_alias else mode,
        raw_model_output=raw,
    )


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
    if re.search(r'"tool"\s*:\s*"write_memo"', raw):
        # A memo JSON may hit the generation cap after declaring its tool. It must
        # never be reinterpreted as a client-facing question.
        match = re.search(r'"content"\s*:\s*"(.*)', raw, flags=re.DOTALL)
        content = match.group(1) if match else raw
        if content.endswith('"}'):
            content = content[:-2]
        content = content.replace(r"\n", "\n").replace(r'\"', '"').replace(r"\\", "\\")
        return Action(
            tool="write_memo",
            content=content.strip() or raw,
            parse_mode="fallback",
            raw_model_output=raw,
        )
    return Action(
        tool="talk_to_client",
        content=raw,
        parse_mode="fallback",
        raw_model_output=raw,
    )
