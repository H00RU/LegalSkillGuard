from __future__ import annotations

import sys
from pathlib import Path

import pytest

import scripts.qualify_local_judge as qualification_script
from legal_skill_guard.evaluation.qualification import (
    SEMANTIC_JUDGE_QUALIFICATION_CASE_COUNT,
    SEMANTIC_JUDGE_QUALIFICATION_CASES,
    semantic_judge_qualification_component_hashes,
    semantic_judge_qualification_data_contract_checks,
)
from legal_skill_guard.utils.hashing import canonical_json_sha256, sha256_file
from scripts.qualify_local_judge import _parse_args, _select_training_cases

ROOT = Path(__file__).resolve().parents[2]


def _judge_role() -> dict[str, object]:
    return {
        "base_url": "http://127.0.0.1:8002/v1",
        "model_id": "openai/gpt-oss-20b",
        "reasoning_effort": "medium",
    }


def test_formal_judge_panel_is_the_exact_frozen_eight_domain_set() -> None:
    rows = _select_training_cases()
    observed = tuple((str(row["id"]), str(row["legal_domain"])) for row in rows)

    assert SEMANTIC_JUDGE_QUALIFICATION_CASE_COUNT == 8
    assert observed == SEMANTIC_JUDGE_QUALIFICATION_CASES
    assert len({domain for _, domain in observed}) == 8


def test_cases_argument_cannot_shorten_or_expand_the_formal_panel() -> None:
    assert _parse_args(_judge_role(), []).cases == 8
    assert _parse_args(_judge_role(), ["--cases", "8"]).cases == 8
    with pytest.raises(SystemExit):
        _parse_args(_judge_role(), ["--cases", "7"])
    with pytest.raises(SystemExit):
        _parse_args(_judge_role(), ["--cases", "9"])
    assert _parse_args(_judge_role(), ["--workers", "8"]).workers == 8
    with pytest.raises(SystemExit):
        _parse_args(_judge_role(), ["--workers", "4"])


def test_base_url_override_is_rejected_before_client_construction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frozen_url = str(_judge_role()["base_url"])
    assert _parse_args(_judge_role(), []).base_url == frozen_url
    assert _parse_args(_judge_role(), ["--base-url", frozen_url]).base_url == frozen_url
    with pytest.raises(SystemExit):
        _parse_args(_judge_role(), ["--base-url", "http://127.0.0.1:8999/v1"])

    def unexpected_client(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("mismatched base URL reached judge client construction")

    monkeypatch.setattr(
        qualification_script, "StructuredOpenAIClient", unexpected_client
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "qualify_local_judge.py",
            "--base-url",
            "http://127.0.0.1:8999/v1",
        ],
    )
    with pytest.raises(SystemExit) as exc_info:
        qualification_script.main()
    assert exc_info.value.code == 2


def test_model_and_reasoning_overrides_are_rejected_by_argument_parsing() -> None:
    role = _judge_role()
    assert _parse_args(role, []).model == role["model_id"]
    assert _parse_args(role, []).reasoning_effort == role["reasoning_effort"]
    with pytest.raises(SystemExit):
        _parse_args(role, ["--model", "different-model"])
    with pytest.raises(SystemExit):
        _parse_args(role, ["--reasoning-effort", "low"])


def test_judge_qualification_components_bind_panel_and_both_source_files() -> None:
    components = semantic_judge_qualification_component_hashes(ROOT)

    assert components["qualification_case_contract_sha256"] == canonical_json_sha256(
        [
            {"case_id": case_id, "legal_domain": legal_domain}
            for case_id, legal_domain in SEMANTIC_JUDGE_QUALIFICATION_CASES
        ]
    )
    assert components["training_cases_file_sha256"] == sha256_file(
        ROOT / "data/training/legal_skill_guard_dlawbench_style_cn.jsonl"
    )
    assert components["training_provenance_file_sha256"] == sha256_file(
        ROOT
        / "data/training/legal_skill_guard_dlawbench_style_cn.provenance.jsonl"
    )


def test_report_data_contract_rejects_a_shortened_or_reordered_panel() -> None:
    components = semantic_judge_qualification_component_hashes(ROOT)
    report = {
        "training_cases_only": True,
        "case_count": SEMANTIC_JUDGE_QUALIFICATION_CASE_COUNT,
        "qualification_case_ids": [
            case_id for case_id, _ in SEMANTIC_JUDGE_QUALIFICATION_CASES
        ],
        "qualification_legal_domains": [
            domain for _, domain in SEMANTIC_JUDGE_QUALIFICATION_CASES
        ],
        "cases": [
            {"case_id": case_id, "legal_domain": domain}
            for case_id, domain in SEMANTIC_JUDGE_QUALIFICATION_CASES
        ],
        **components,
    }
    assert all(semantic_judge_qualification_data_contract_checks(ROOT, report).values())

    shortened = {**report, "case_count": 7, "cases": report["cases"][:7]}
    shortened_checks = semantic_judge_qualification_data_contract_checks(ROOT, shortened)
    assert shortened_checks["case_count_matches"] is False
    assert shortened_checks["case_rows_match_frozen_panel"] is False

    reordered = {**report, "cases": list(reversed(report["cases"]))}
    assert (
        semantic_judge_qualification_data_contract_checks(ROOT, reordered)[
            "case_rows_match_frozen_panel"
        ]
        is False
    )
