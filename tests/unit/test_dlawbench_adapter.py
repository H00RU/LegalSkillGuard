from __future__ import annotations

import json
from pathlib import Path

from legal_skill_guard.environment.dlawbench_adapter import DLawBenchAdapter


def test_adapter_keeps_online_and_evaluator_views_separate(tmp_path: Path) -> None:
    case = {
        "id": "c1",
        "jurisdiction": "CN",
        "language": "zh",
        "opening": "咨询",
        "facts": [
            {
                "fact_id": "F1",
                "client_belief": "客户认知",
                "court_record": "法院记录",
                "gap_type": "disputed",
            }
        ],
        "evaluation_criteria": {
            "expected_inquiries": ["隐藏询问"],
            "memo_expectations": ["隐藏标准"],
        },
        "sha256": "x",
    }
    cases = tmp_path / "cases.jsonl"
    cases.write_text(json.dumps(case, ensure_ascii=False), encoding="utf-8")
    personas = tmp_path / "personas.json"
    personas.write_text(json.dumps({"P": {"who": "w", "voice": "v"}}), encoding="utf-8")
    adapter = DLawBenchAdapter(cases, personas)

    assert set(adapter.lawyer_case("c1")) == {"id", "jurisdiction", "language", "opening"}
    assert "court_record" not in json.dumps(adapter.client_case("c1"), ensure_ascii=False)
    assert adapter.evaluator_case("c1")["facts"][0]["court_record"] == "法院记录"

    provenance = tmp_path / "provenance.jsonl"
    provenance.write_text(
        json.dumps(
            {
                "id": "c1",
                "split": "train",
                "annotation": {"client_role": "被欠薪的劳动者"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    split_adapter = DLawBenchAdapter(cases, personas, provenance)
    assert split_adapter.case_ids() == ("c1",)
    assert split_adapter.case_ids("train") == ("c1",)
    assert split_adapter.case_ids("validation") == ()
    assert "client_role" not in split_adapter.lawyer_case("c1")
    assert "client_role" not in split_adapter.client_case("c1")
    assert "client_role" not in split_adapter.evaluator_case("c1")
