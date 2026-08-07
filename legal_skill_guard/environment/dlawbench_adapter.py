"""Leakage-safe access to the pinned DLawBench public CN records and personas."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from legal_skill_guard.data_visibility import Audience, assert_online_view_safe, project_case


class DLawBenchAdapter:
    def __init__(self, cases_path: Path, personas_path: Path) -> None:
        self._records = {
            record["id"]: record
            for line in cases_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
            for record in [json.loads(line)]
        }
        raw_personas = json.loads(personas_path.read_text(encoding="utf-8"))
        self._personas = {
            key: value for key, value in raw_personas.items() if not key.startswith("_")
        }

    @property
    def persona_keys(self) -> tuple[str, ...]:
        return tuple(self._personas)

    def lawyer_case(self, case_id: str) -> dict[str, Any]:
        view = project_case(self._records[case_id], Audience.LAWYER_AGENT)
        assert_online_view_safe(view)
        return view

    def client_case(self, case_id: str) -> dict[str, Any]:
        return project_case(self._records[case_id], Audience.CLIENT_SIMULATOR)

    def evaluator_case(self, case_id: str) -> dict[str, Any]:
        return project_case(self._records[case_id], Audience.EVALUATOR)

    def persona(self, key: str) -> dict[str, Any]:
        return json.loads(json.dumps(self._personas[key], ensure_ascii=False))
