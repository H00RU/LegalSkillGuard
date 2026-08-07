from __future__ import annotations

import json
from pathlib import Path

import pytest

from legal_skill_guard.data_visibility import (
    Audience,
    assert_online_view_safe,
    project_case,
)

ROOT = Path(__file__).resolve().parents[2]
UPSTREAM_CN = ROOT / "third_party" / "DLawBench" / "data" / "case_backgrounds" / "cases_cn.jsonl"


@pytest.fixture
def case() -> dict:
    with UPSTREAM_CN.open(encoding="utf-8") as handle:
        return json.loads(next(line for line in handle if line.strip()))


@pytest.mark.parametrize("audience", [Audience.LAWYER_AGENT, Audience.ONLINE_STATE])
def test_online_views_exclude_all_hidden_fields(case: dict, audience: Audience) -> None:
    view = project_case(case, audience)
    assert set(view) == {"id", "jurisdiction", "language", "opening"}
    assert_online_view_safe(view)


def test_client_view_contains_beliefs_but_not_court_records_or_rubrics(case: dict) -> None:
    view = project_case(case, Audience.CLIENT_SIMULATOR)
    serialized = json.dumps(view, ensure_ascii=False)
    assert view["facts"]
    assert "client_belief" in view["facts"][0]
    assert "court_record" not in serialized
    assert "evaluation_criteria" not in serialized
    assert "expected_inquiries" not in serialized
    assert "memo_expectations" not in serialized


def test_evaluator_receives_full_deep_copy(case: dict) -> None:
    view = project_case(case, Audience.EVALUATOR)
    assert view == case
    assert view is not case
    assert view["facts"] is not case["facts"]


def test_safety_assertion_rejects_hidden_fields() -> None:
    with pytest.raises(ValueError, match="court_record"):
        assert_online_view_safe({"facts": [{"court_record": "hidden"}]})
