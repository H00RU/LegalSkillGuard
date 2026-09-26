"""Leakage-safe access to the pinned DLawBench public CN records and personas."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from legal_skill_guard.data_visibility import Audience, assert_online_view_safe, project_case


class DLawBenchAdapter:
    """Load DLawBench-compatible cases with optional formal split provenance."""

    def __init__(
        self,
        cases_path: Path,
        personas_path: Path,
        provenance_path: Path | None = None,
    ) -> None:
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
        self._splits: dict[str, str] = {}
        self._domains: dict[str, str] = {}
        if provenance_path is not None:
            for line in provenance_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                item = json.loads(line)
                case_id = str(item["id"])
                if case_id not in self._records:
                    raise ValueError(f"provenance references unknown case: {case_id}")
                self._splits[case_id] = str(item["split"])
                annotation = item.get("annotation") or {}
                self._domains[case_id] = str(annotation.get("legal_domain") or "general")
            missing = sorted(set(self._records) - set(self._splits))
            if missing:
                raise ValueError(f"cases missing provenance split: {missing[:5]}")

    @property
    def persona_keys(self) -> tuple[str, ...]:
        return tuple(self._personas)

    def case_ids(self, split: str | None = None) -> tuple[str, ...]:
        """Return stable case IDs, optionally restricted by provenance split."""

        if split is None:
            return tuple(self._records)
        if not self._splits:
            raise ValueError("split requested without a provenance file")
        return tuple(case_id for case_id in self._records if self._splits[case_id] == split)

    def lawyer_case(self, case_id: str) -> dict[str, Any]:
        view = project_case(self._records[case_id], Audience.LAWYER_AGENT)
        assert_online_view_safe(view)
        return view

    def case_domain(self, case_id: str) -> str:
        """Return public corpus taxonomy metadata, never hidden case-record content."""

        return self._domains.get(case_id, "general")

    def client_case(self, case_id: str) -> dict[str, Any]:
        return project_case(self._records[case_id], Audience.CLIENT_SIMULATOR)

    def evaluator_case(self, case_id: str) -> dict[str, Any]:
        return project_case(self._records[case_id], Audience.EVALUATOR)

    def persona(self, key: str) -> dict[str, Any]:
        persona = json.loads(json.dumps(self._personas[key], ensure_ascii=False))
        persona["persona_id"] = key
        return persona
