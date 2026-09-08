from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

import scripts.qualify_client_simulator as qualification_script
from legal_skill_guard.environment.client_response import (
    CLIENT_DISCLOSURE_SIGNALS_SCHEMA,
    CLIENT_FACT_SELECTION_SCHEMA,
)
from legal_skill_guard.evaluation.qualification import (
    CLIENT_QUALIFICATION_FIXTURE_SCHEMA_VERSION,
    CLIENT_QUALIFICATION_REPORT_SCHEMA_VERSION,
    client_simulator_qualification_component_hashes,
)
from legal_skill_guard.experiment.storage import ImmutableArtifactConflictError
from legal_skill_guard.utils.hashing import canonical_json_sha256, sha256_file
from scripts.qualify_client_simulator import (
    QualificationFixtureError,
    _advance_expected_disclosure_state,
    _expected_response_kind,
    load_qualification_chains,
    validate_fixture_references,
    write_qualification_artifacts,
)

ROOT = Path(__file__).resolve().parents[2]


def test_unsafe_run_id_is_rejected_before_model_client_construction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_model_client(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("unsafe run-id reached model client construction")

    monkeypatch.setattr(qualification_script, "ChatClient", unexpected_model_client)
    monkeypatch.setattr(
        sys,
        "argv",
        ["qualify_client_simulator.py", "--run-id", "../escape"],
    )
    with pytest.raises(SystemExit) as exc_info:
        qualification_script.main()
    assert exc_info.value.code == 2


def test_current_fixture_uses_only_two_axis_expectations_and_linked_resistance() -> None:
    path = ROOT / "configs/qualification/client_simulator_cases.json"
    document, chains = load_qualification_chains(path)

    serialized = json.dumps(document, ensure_ascii=False)
    assert document["schema_version"] == CLIENT_QUALIFICATION_FIXTURE_SCHEMA_VERSION
    assert '"expected_fact_id"' not in serialized
    assert '"expected_fact_ids"' not in serialized
    assert len(document["cases"]) == 139
    assert len(document["chains"]) == 2
    assert sum(len(chain["turns"]) for chain in chains) == 143

    renewal_date = next(
        chain["turns"][0]
        for chain in chains
        if chain["chain_id"] == "single_077"
    )
    assert renewal_date["expected_matched_fact_id"] == "F2"

    cases = {
        case["id"]: case
        for case in (
            json.loads(line)
            for line in (
                ROOT / "data/training/legal_skill_guard_dlawbench_style_cn.jsonl"
            ).read_text(encoding="utf-8").splitlines()
            if line
        )
    }
    personas = json.loads(
        (ROOT / "third_party/DLawBench/config/personas.json").read_text(encoding="utf-8")
    )
    validate_fixture_references(chains, cases=cases, personas=personas)

    linked = {chain["persona_id"]: chain for chain in chains if len(chain["turns"]) > 1}
    assert set(linked) == {"P_CS", "P_CD"}
    for chain in linked.values():
        first, second = chain["turns"]
        assert first["expected_matched_fact_id"] == second["expected_matched_fact_id"]
        assert first["expected_disclosure"] == "withhold"
        assert second["expected_disclosure"] == "disclose"


def test_legacy_flat_or_legacy_expected_fact_fixture_fails_closed(tmp_path: Path) -> None:
    flat = tmp_path / "flat.json"
    flat.write_text(
        json.dumps([{"case_id": "c", "question": "q", "expected_fact_id": "F1"}]),
        encoding="utf-8",
    )
    with pytest.raises(QualificationFixtureError, match="legacy flat"):
        load_qualification_chains(flat)

    old_field = tmp_path / "old_field.json"
    old_field.write_text(
        json.dumps(
            {
                "schema_version": CLIENT_QUALIFICATION_FIXTURE_SCHEMA_VERSION,
                "cases": [
                    {
                        "case_id": "c",
                        "question": "q",
                        "expected_fact_id": "F1",
                        "expected_disclosure": "disclose",
                    }
                ],
                "chains": [],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(QualificationFixtureError, match="keys invalid"):
        load_qualification_chains(old_field)


def test_withhold_requires_matched_hidden_fact_and_resistant_persona(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.json"
    invalid.write_text(
        json.dumps(
            {
                "schema_version": CLIENT_QUALIFICATION_FIXTURE_SCHEMA_VERSION,
                "cases": [
                    {
                        "case_id": "c",
                        "persona_id": "P_WD",
                        "question": "q",
                        "expected_matched_fact_id": "F1",
                        "expected_disclosure": "withhold",
                    }
                ],
                "chains": [],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(QualificationFixtureError, match="only resistant"):
        load_qualification_chains(invalid)


def test_response_kind_is_derived_from_match_disclosure_and_prior_state() -> None:
    assert _expected_response_kind(None, "disclose", set()) == "unavailable"
    assert _expected_response_kind("O1", "disclose", set()) == "opening_repeat"
    assert _expected_response_kind("F1", "withhold", set()) == "withheld"
    assert _expected_response_kind("F1", "disclose", set()) == "new_hidden_fact"
    assert _expected_response_kind("F1", "disclose", {"F1"}) == "repeated_hidden_fact"


def test_expected_transition_state_is_independent_of_observed_disclosure() -> None:
    expected_state: set[str] = set()
    _advance_expected_disclosure_state(expected_state, "F1", "withhold")
    assert expected_state == set()
    assert _expected_response_kind("F1", "disclose", expected_state) == "new_hidden_fact"
    _advance_expected_disclosure_state(expected_state, "F1", "disclose")
    assert expected_state == {"F1"}


def test_named_component_hashes_bind_current_prompts_schema_and_fixture() -> None:
    hashes = client_simulator_qualification_component_hashes(ROOT)

    assert hashes == {
        "selector_prompt_sha256": sha256_file(
            ROOT / "configs/prompts/client_fact_selector_zh.txt"
        ),
        "disclosure_prompt_sha256": sha256_file(
            ROOT / "configs/prompts/client_fact_disclosure_zh.txt"
        ),
        "selector_schema_sha256": canonical_json_sha256(CLIENT_FACT_SELECTION_SCHEMA),
        "disclosure_signals_schema_sha256": canonical_json_sha256(
            CLIENT_DISCLOSURE_SIGNALS_SCHEMA
        ),
        "fixture_file_sha256": sha256_file(
            ROOT / "configs/qualification/client_simulator_cases.json"
        ),
    }


def _binding(run_id: str) -> dict[str, object]:
    return {
        "schema_version": 1,
        "run_id": run_id,
        "qualification_protocol": 28,
        "fixture_schema_version": CLIENT_QUALIFICATION_FIXTURE_SCHEMA_VERSION,
        "report_schema_version": CLIENT_QUALIFICATION_REPORT_SCHEMA_VERSION,
        "model": "Qwen/Qwen3-8B",
        "model_revision": "frozen",
        "disclosure_model": "Qwen/Qwen3-8B",
        "disclosure_model_revision": "frozen",
        "selector_endpoint_contract": {"ready": True, "model": "Qwen/Qwen3-8B"},
        "disclosure_endpoint_contract": {"ready": True, "model": "Qwen/Qwen3-8B"},
        "client_simulator_qualification_contract_sha256": "1" * 64,
        "selector_prompt_sha256": "2" * 64,
        "disclosure_prompt_sha256": "7" * 64,
        "selector_schema_sha256": "4" * 64,
        "disclosure_signals_schema_sha256": "6" * 64,
        "fixture_file_sha256": "5" * 64,
    }


def _report(root: Path, run_id: str, binding: dict[str, object]) -> dict[str, object]:
    return {
        **binding,
        "schema_version": CLIENT_QUALIFICATION_REPORT_SCHEMA_VERSION,
        "qualification_binding_path": (
            f"runs/{run_id}/qualifications/client_simulator/binding.json"
        ),
        "qualification_binding_sha256": canonical_json_sha256(binding),
        "fixture_canonical_sha256": "6" * 64,
        "passed": True,
        "results": [],
    }


def test_report_is_run_bound_immutable_and_legacy_report_is_rejected(tmp_path: Path) -> None:
    run_id = "qualification_run"
    binding = _binding(run_id)
    report = _report(tmp_path, run_id, binding)
    binding_path, report_path = write_qualification_artifacts(
        root=tmp_path,
        run_id=run_id,
        binding=binding,
        report=report,
    )
    first_bytes = report_path.read_bytes()
    assert binding_path.is_file()

    write_qualification_artifacts(
        root=tmp_path,
        run_id=run_id,
        binding=binding,
        report=report,
    )
    assert report_path.read_bytes() == first_bytes

    changed = dict(report)
    changed["passed"] = False
    with pytest.raises(ImmutableArtifactConflictError, match="immutable JSON artifact conflict"):
        write_qualification_artifacts(
            root=tmp_path,
            run_id=run_id,
            binding=binding,
            report=changed,
        )

    legacy = {"schema_version": 2, "passed": True}
    with pytest.raises(ValueError, match="run binding mismatch"):
        write_qualification_artifacts(
            root=tmp_path,
            run_id=run_id,
            binding=binding,
            report=legacy,
        )
