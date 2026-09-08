"""Content fingerprints for frozen local-role qualification contracts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from legal_skill_guard.utils.hashing import canonical_json_sha256, sha256_file

CLIENT_QUALIFICATION_FIXTURE_SCHEMA_VERSION = 4
CLIENT_QUALIFICATION_REPORT_SCHEMA_VERSION = 10
SEMANTIC_JUDGE_QUALIFICATION_REPORT_SCHEMA_VERSION = 22

# The formal semantic-judge qualification is an immutable cross-domain panel,
# not a caller-selected sample.  Keep the case/domain pairs together so a case
# cannot silently retain its identifier while moving to a different legal-domain
# stratum in provenance.
SEMANTIC_JUDGE_QUALIFICATION_CASES: tuple[tuple[str, str], ...] = (
    ("lsg_cn_0005", "marriage_family"),
    ("lsg_cn_0007", "insurance_contract"),
    ("lsg_cn_0011", "labor_employment"),
    ("lsg_cn_0017", "consumer_contract"),
    ("lsg_cn_0024", "company_commercial"),
    ("lsg_cn_0030", "intellectual_property"),
    ("lsg_cn_0037", "personality_privacy"),
    ("lsg_cn_0043", "administrative"),
)
SEMANTIC_JUDGE_QUALIFICATION_CASE_COUNT = len(SEMANTIC_JUDGE_QUALIFICATION_CASES)


def semantic_judge_qualification_component_hashes(root: Path) -> dict[str, str]:
    """Expose the frozen judge-panel and source-data fingerprints."""

    return {
        "qualification_case_contract_sha256": canonical_json_sha256(
            [
                {"case_id": case_id, "legal_domain": legal_domain}
                for case_id, legal_domain in SEMANTIC_JUDGE_QUALIFICATION_CASES
            ]
        ),
        "training_cases_file_sha256": sha256_file(
            root / "data/training/legal_skill_guard_dlawbench_style_cn.jsonl"
        ),
        "training_provenance_file_sha256": sha256_file(
            root / "data/training/legal_skill_guard_dlawbench_style_cn.provenance.jsonl"
        ),
    }


def semantic_judge_qualification_data_contract_checks(
    root: Path, report: dict[str, Any]
) -> dict[str, bool]:
    """Revalidate that a report used the complete frozen judge panel."""

    expected_case_ids = [case_id for case_id, _ in SEMANTIC_JUDGE_QUALIFICATION_CASES]
    expected_domains = [domain for _, domain in SEMANTIC_JUDGE_QUALIFICATION_CASES]
    expected_components = semantic_judge_qualification_component_hashes(root)
    rows = report.get("cases")
    if isinstance(rows, list) and all(isinstance(row, dict) for row in rows):
        observed_rows = [(str(row.get("case_id")), str(row.get("legal_domain"))) for row in rows]
    else:
        observed_rows = []
    return {
        "training_cases_only": report.get("training_cases_only") is True,
        "case_count_matches": report.get("case_count") == SEMANTIC_JUDGE_QUALIFICATION_CASE_COUNT,
        "qualification_case_ids_match": report.get("qualification_case_ids") == expected_case_ids,
        "qualification_legal_domains_match": report.get("qualification_legal_domains")
        == expected_domains,
        "case_rows_match_frozen_panel": observed_rows == list(SEMANTIC_JUDGE_QUALIFICATION_CASES),
        "qualification_case_contract_hash_matches": report.get("qualification_case_contract_sha256")
        == expected_components["qualification_case_contract_sha256"],
        "training_cases_file_hash_matches": report.get("training_cases_file_sha256")
        == expected_components["training_cases_file_sha256"],
        "training_provenance_file_hash_matches": report.get("training_provenance_file_sha256")
        == expected_components["training_provenance_file_sha256"],
    }


def semantic_judge_qualification_sha256(root: Path, judge_role: dict[str, Any]) -> str:
    """Hash only inputs that can change what the qualified judge does.

    A qualification must become stale when the judge model/runtime, judge prompt,
    parser/scorer, structured transport, or qualification protocol implementation
    changes.  Unrelated roles such as the lawyer planner or skill teacher are not
    part of that claim and must not invalidate an otherwise identical judge.
    """

    relative_paths = (
        "configs/prompts/semantic_judge_zh.txt",
        "data/training/legal_skill_guard_dlawbench_style_cn.jsonl",
        "data/training/legal_skill_guard_dlawbench_style_cn.provenance.jsonl",
        "legal_skill_guard/evaluation/semantic.py",
        "legal_skill_guard/inference/structured_openai_client.py",
        "scripts/qualify_local_judge.py",
    )
    return canonical_json_sha256(
        {
            "semantic_judge_role": judge_role,
            "qualification_cases": [
                {"case_id": case_id, "legal_domain": legal_domain}
                for case_id, legal_domain in SEMANTIC_JUDGE_QUALIFICATION_CASES
            ],
            "contract_files": {path: sha256_file(root / path) for path in relative_paths},
        }
    )


def client_simulator_qualification_sha256(
    root: Path,
    selector_role: dict[str, Any],
    disclosure_role: dict[str, Any],
) -> str:
    """Fingerprint the complete grounded client-observation contract."""

    relative_paths = (
        "configs/prompts/client_fact_selector_zh.txt",
        "configs/prompts/client_fact_disclosure_zh.txt",
        "configs/qualification/client_simulator_cases.json",
        "data/training/legal_skill_guard_dlawbench_style_cn.jsonl",
        "third_party/DLawBench/config/personas.json",
        "legal_skill_guard/environment/client_response.py",
        "legal_skill_guard/evaluation/qualification.py",
        "legal_skill_guard/experiment/storage.py",
        "legal_skill_guard/schemas/experiment.py",
        "legal_skill_guard/inference/openai_client.py",
        "scripts/qualify_client_simulator.py",
    )
    return canonical_json_sha256(
        {
            "client_fact_selector_role": selector_role,
            "client_disclosure_classifier_role": disclosure_role,
            "contract_files": {path: sha256_file(root / path) for path in relative_paths},
        }
    )


def client_simulator_qualification_component_hashes(root: Path) -> dict[str, str]:
    """Return the human-auditable hashes that define client qualification.

    The aggregate contract fingerprint above intentionally covers the complete
    implementation.  These named hashes additionally make the three most important
    compatibility boundaries visible in every report: routing/disclosure prompts,
    the structured match/disclosure schema, and the fixture document. A report
    created before the closed-set client router contract therefore cannot be mistaken
    for a current qualification merely because it used the same model identifier.
    """

    # Local import avoids loading the comparatively large simulator module for
    # callers that only need the semantic-judge fingerprint.
    from legal_skill_guard.environment.client_response import (
        CLIENT_DISCLOSURE_SIGNALS_SCHEMA,
        CLIENT_FACT_SELECTION_SCHEMA,
    )

    return {
        "selector_prompt_sha256": sha256_file(root / "configs/prompts/client_fact_selector_zh.txt"),
        "disclosure_prompt_sha256": sha256_file(
            root / "configs/prompts/client_fact_disclosure_zh.txt"
        ),
        "selector_schema_sha256": canonical_json_sha256(CLIENT_FACT_SELECTION_SCHEMA),
        "disclosure_signals_schema_sha256": canonical_json_sha256(CLIENT_DISCLOSURE_SIGNALS_SCHEMA),
        "fixture_file_sha256": sha256_file(
            root / "configs/qualification/client_simulator_cases.json"
        ),
    }
