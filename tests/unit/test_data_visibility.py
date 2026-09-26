from __future__ import annotations

from legal_skill_guard.data_visibility import (
    Audience,
    assert_lawyer_view_safe,
    project_case,
)

CASE = {
    "id": "case_cn_test",
    "jurisdiction": "CN",
    "language": "zh",
    "opening": "我想咨询一个问题。",
    "facts": [
        {
            "fact_id": "F1",
            "client_belief": "客户主张",
            "court_record": "法院认定",
            "gap_type": "disputed",
        }
    ],
    "evaluation_criteria": {
        "expected_inquiries": ["隐藏询问标准"],
        "memo_expectations": ["隐藏备忘录标准"],
    },
    "sha256": "0" * 64,
}


def test_lawyer_projection_is_minimum_privilege() -> None:
    view = project_case(CASE, Audience.LAWYER_AGENT)
    assert view == {
        "id": "case_cn_test",
        "jurisdiction": "CN",
        "language": "zh",
        "opening": "我想咨询一个问题。",
    }
    assert_lawyer_view_safe(view)


def test_client_prompt_gets_belief_but_not_record_or_rubrics() -> None:
    view = project_case(CASE, Audience.CLIENT_SIMULATOR_PROMPT)
    assert view["facts"][0]["client_belief"] == "客户主张"
    assert "court_record" not in view["facts"][0]
    assert "gap_type" not in view["facts"][0]
    assert "evaluation_criteria" not in view


def test_evaluator_gets_an_independent_full_copy() -> None:
    view = project_case(CASE, Audience.EVALUATOR)
    assert view == CASE
    view["facts"][0]["court_record"] = "changed"
    assert CASE["facts"][0]["court_record"] == "法院认定"
