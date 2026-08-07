from __future__ import annotations

import json
from pathlib import Path

import pytest

from legal_skill_guard.data_visibility import (
    Audience,
    assert_lawyer_view_safe,
    project_case,
)

ROOT = Path(__file__).resolve().parents[2]
REVISION = "9f6325f29f07b296fac110a6e1880bdd5d9ca538"
CN_DATA = ROOT / "data/raw/dlawbench" / REVISION / "data/case_backgrounds/cases_cn.jsonl"


@pytest.mark.integration
def test_real_cn_hidden_values_do_not_enter_lawyer_view() -> None:
    if not CN_DATA.is_file():
        pytest.skip("Run scripts/prepare_dlawbench.py first")
    record = json.loads(CN_DATA.read_text(encoding="utf-8").splitlines()[0])
    view = project_case(record, Audience.LAWYER_AGENT)
    assert_lawyer_view_safe(view)
    serialized = json.dumps(view, ensure_ascii=False)

    hidden_values = [
        fact[field] for fact in record["facts"] for field in ("client_belief", "court_record")
    ]
    hidden_values.extend(record["evaluation_criteria"]["expected_inquiries"])
    hidden_values.extend(record["evaluation_criteria"]["memo_expectations"])
    assert all(value not in serialized for value in hidden_values)
