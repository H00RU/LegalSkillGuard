"""Audience-specific DLawBench projections.

This module is intentionally small and deterministic. It is the Phase 0 trust
boundary that prevents hidden benchmark labels from entering online components.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping
from enum import StrEnum
from typing import Any


class Audience(StrEnum):
    LAWYER_AGENT = "lawyer_agent"
    ONLINE_STATE = "online_state"
    CLIENT_SIMULATOR = "client_simulator"
    CLIENT_SIMULATOR_PROMPT = "client_simulator"
    EVALUATOR = "evaluator"


PUBLIC_KEYS = ("id", "jurisdiction", "language", "opening")
HIDDEN_TOP_LEVEL_KEYS = frozenset({"facts", "evaluation_criteria", "sha256"})
HIDDEN_FACT_KEYS = frozenset({"client_belief", "court_record"})
HIDDEN_RUBRIC_KEYS = frozenset({"expected_inquiries", "memo_expectations"})
ONLINE_PAYLOAD_FORBIDDEN_KEYS = HIDDEN_FACT_KEYS | HIDDEN_RUBRIC_KEYS | frozenset(
    {"evaluation_criteria", "sha256"}
)


def _public_case_fields(case: Mapping[str, Any]) -> dict[str, Any]:
    return {key: copy.deepcopy(case[key]) for key in PUBLIC_KEYS if key in case}


def project_case(case: Mapping[str, Any], audience: Audience) -> dict[str, Any]:
    """Return the minimum case view allowed for an online component.

    The evaluator receives a deep copy of the full record. The official DLawBench
    client prompt uses only client beliefs, so the client view excludes court records
    even though an evaluator may use them after the consultation.
    """

    if audience is Audience.EVALUATOR:
        return copy.deepcopy(dict(case))

    view = _public_case_fields(case)
    if audience is Audience.CLIENT_SIMULATOR:
        view["facts"] = [
            {
                key: copy.deepcopy(fact[key])
                for key in ("fact_id", "client_belief", "gap_type")
                if key in fact
            }
            for fact in case.get("facts", [])
        ]
    elif audience not in (Audience.LAWYER_AGENT, Audience.ONLINE_STATE):
        raise ValueError(f"Unsupported audience: {audience!r}")
    return view


def find_hidden_field_names(value: Any) -> set[str]:
    """Recursively find benchmark-only field names in a projected object."""

    found: set[str] = set()
    if isinstance(value, Mapping):
        for key, child in value.items():
            if key in HIDDEN_TOP_LEVEL_KEYS | HIDDEN_FACT_KEYS | HIDDEN_RUBRIC_KEYS:
                found.add(str(key))
            found.update(find_hidden_field_names(child))
    elif isinstance(value, list | tuple):
        for child in value:
            found.update(find_hidden_field_names(child))
    return found


def find_online_payload_forbidden_fields(value: Any) -> set[str]:
    """Find benchmark labels forbidden inside state/action/trajectory payloads.

    A structured online state legitimately owns a ``facts`` collection. What it may
    never contain are the benchmark's paired belief/record text or its rubrics.
    """

    found: set[str] = set()
    if isinstance(value, Mapping):
        for key, child in value.items():
            if key in ONLINE_PAYLOAD_FORBIDDEN_KEYS:
                found.add(str(key))
            found.update(find_online_payload_forbidden_fields(child))
    elif isinstance(value, list | tuple):
        for child in value:
            found.update(find_online_payload_forbidden_fields(child))
    return found


def assert_online_payload_safe(value: Mapping[str, Any]) -> None:
    hidden = find_online_payload_forbidden_fields(value)
    if hidden:
        raise ValueError(f"Online payload contains benchmark-only fields: {sorted(hidden)}")


def assert_online_view_safe(view: Mapping[str, Any]) -> None:
    hidden = find_hidden_field_names(view)
    if hidden:
        raise ValueError(f"Online view contains hidden benchmark fields: {sorted(hidden)}")


# A precise alias retained for call sites that only validate the lawyer-facing view.
assert_lawyer_view_safe = assert_online_view_safe
