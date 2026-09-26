#!/usr/bin/env python3
"""CPU-only, source-grounded quality audit for the 128-case main corpus.

This audit intentionally separates deterministic/source checks from the later
independent model review of the opening-information boundary.  It does not turn
AI-authored labels into a lawyer-expert gold claim.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
AUTHORING = ROOT / "data/annotations/main_corpus"
CORE = ROOT / "data/training/legal_skill_guard_dlawbench_style_cn.jsonl"
PROVENANCE = ROOT / "data/training/legal_skill_guard_dlawbench_style_cn.provenance.jsonl"
SELECTION = ROOT / "data/manifests/main_corpus_selection.json"
EXCLUSIONS = ROOT / "data/manifests/main_corpus_exclusions.json"
OFFICIAL = ROOT / "third_party/DLawBench/data/case_backgrounds/cases_cn.jsonl"
OFFICIAL_SCHEMA = ROOT / "third_party/DLawBench/schema/case.schema.json"
OUTPUT = ROOT / "reports/artifacts/main_corpus_casewise_quality_audit.json"
SOURCES = (
    ROOT / "data/source_pool/spc_typical_cases.jsonl",
    ROOT / "data/source_pool/spc_reference_cases.jsonl",
    ROOT / "data/source_pool/spc_labor_consumer_cases.jsonl",
    ROOT / "data/source_pool/spc_procedure_insurance_cases.jsonl",
    ROOT / "data/source_pool/spc_expansion_128_cases.jsonl",
)
REQUIRED_EDITORIAL_CHECKS = {
    "source_read_in_full",
    "single_client_role",
    "pre_outcome_timeline",
    "opening_has_no_outcome",
    "opening_information_boundary_checked",
    "beliefs_are_natural",
    "gap_labels_semantically_checked",
    "inquiries_are_answerable",
    "memo_points_are_substantive",
}


class UniqueKeyLoader(yaml.SafeLoader):
    """Reject duplicate YAML keys instead of silently taking the last value."""


def _unique_mapping(loader: UniqueKeyLoader, node: yaml.MappingNode, deep: bool = False) -> Any:
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            mark = key_node.start_mark
            raise ValueError(f"{mark.name}:{mark.line + 1}: duplicate YAML key {key!r}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _unique_mapping,
)


def jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def normalized(text: str) -> str:
    return re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", text)


def grams(text: str, size: int = 5) -> set[str]:
    text = normalized(text)
    return {text[index : index + size] for index in range(max(0, len(text) - size + 1))}


def case_text(case: dict[str, Any]) -> str:
    return "".join(
        [
            case["opening"],
            *(fact["client_belief"] + fact["court_record"] for fact in case["facts"]),
            *case["evaluation_criteria"]["expected_inquiries"],
            *case["evaluation_criteria"]["memo_expectations"],
        ]
    )


def corpus_shape(cases: list[dict[str, Any]]) -> dict[str, Any]:
    fact_counts = [len(case["facts"]) for case in cases]
    inquiry_counts = [len(case["evaluation_criteria"]["expected_inquiries"]) for case in cases]
    memo_counts = [len(case["evaluation_criteria"]["memo_expectations"]) for case in cases]
    gaps = Counter(fact["gap_type"] for case in cases for fact in case["facts"])
    return {
        "cases": len(cases),
        "facts": {"total": sum(fact_counts), "mean": round(mean(fact_counts), 3),
                  "minimum": min(fact_counts), "maximum": max(fact_counts)},
        "gap_types": {"disputed": gaps["disputed"], "undisputed": gaps["undisputed"],
                      "disputed_share": round(gaps["disputed"] / sum(gaps.values()), 4)},
        "expected_inquiries": {"total": sum(inquiry_counts),
                               "mean": round(mean(inquiry_counts), 3),
                               "minimum": min(inquiry_counts), "maximum": max(inquiry_counts)},
        "memo_expectations": {"total": sum(memo_counts), "mean": round(mean(memo_counts), 3),
                              "minimum": min(memo_counts), "maximum": max(memo_counts)},
    }


def main() -> None:
    errors: list[str] = []
    annotations: list[dict[str, Any]] = []
    for path in sorted(AUTHORING.glob("batch_*.yaml")):
        try:
            payload = yaml.load(path.read_text(encoding="utf-8"), Loader=UniqueKeyLoader)
        except Exception as exc:  # duplicate keys and malformed YAML are audit failures
            errors.append(str(exc))
            continue
        annotations.extend(payload.get("annotations") or [])

    sources = [item for path in SOURCES for item in jsonl(path)]
    core = jsonl(CORE)
    provenance = jsonl(PROVENANCE)
    selection = json.loads(SELECTION.read_text(encoding="utf-8"))
    exclusions = json.loads(EXCLUSIONS.read_text(encoding="utf-8"))
    official = jsonl(OFFICIAL)
    core_by_id = {item["id"]: item for item in core}
    provenance_by_id = {item["id"]: item for item in provenance}
    annotation_by_id = {item["id"]: item for item in annotations}
    selection_by_id = {item["id"]: item for item in selection["records"]}

    expected_ids = set(core_by_id)
    canonical_ids = {f"lsg_cn_{index:04d}" for index in range(1, 129)}
    if expected_ids != canonical_ids:
        errors.append("core case IDs are not the exact contiguous lsg_cn_0001..0128 set")
    for name, rows in (
        ("core", core), ("provenance", provenance), ("authoring", annotations),
        ("selection", selection["records"]),
    ):
        ids = [item["id"] for item in rows]
        if len(ids) != 128 or len(ids) != len(set(ids)) or set(ids) != expected_ids:
            errors.append(f"{name}: expected the same 128 unique case ids")

    selected_lines = {int(item["source_line"]) for item in selection["records"]}
    if len(selected_lines) != len(selection["records"]):
        errors.append("one official source case was selected more than once")
    excluded_lines = {
        int(line)
        for category in exclusions["categories"]
        for line in category["source_lines"]
    }
    if selected_lines & excluded_lines:
        errors.append("selection and exclusion manifests overlap")
    if selected_lines | excluded_lines != set(range(1, len(sources) + 1)):
        errors.append("selection and exclusion manifests do not partition the source pool")
    if exclusions.get("source_pool_cases") != len(sources) or len(excluded_lines) != 51:
        errors.append("source-pool/exclusion counts are stale")

    page_hash_cache: dict[str, str] = {}
    for index, source in enumerate(sources, 1):
        value = dict(source)
        stored_case_hash = value.pop("source_case_sha256", None)
        actual_case_hash = hashlib.sha256(
            json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()
        if stored_case_hash != actual_case_hash:
            errors.append(f"source line {index}: canonical case hash mismatch")
        source_id = str(source["source_id"])
        if source_id not in page_hash_cache:
            page = ROOT / "data/source_pool/raw_pages" / f"{source_id}.html"
            page_hash_cache[source_id] = (
                hashlib.sha256(page.read_bytes()).hexdigest() if page.is_file() else "missing"
            )
        if page_hash_cache[source_id] != source["source_page_sha256"]:
            errors.append(f"source line {index}: raw official page hash mismatch")

    evidence_quotes = 0
    unsupported_fact_ids: list[str] = []
    source_authority_failures: list[str] = []
    authoring_identity_failures: list[str] = []
    fact_id_failures: list[str] = []
    empty_or_whitespace_fields: list[str] = []
    within_case_duplicate_fields: list[str] = []
    case_digest_failures: list[str] = []
    page_splits: dict[str, set[str]] = defaultdict(set)
    split_domains: dict[str, Counter[str]] = defaultdict(Counter)
    for case_id in sorted(expected_ids):
        annotation = annotation_by_id[case_id]
        source_line = int(annotation["source_line"])
        source = sources[source_line - 1]
        selected = selection_by_id[case_id]
        prov = provenance_by_id[case_id]
        if annotation["source_case_sha256"] != source["source_case_sha256"]:
            errors.append(f"{case_id}: authoring source hash mismatch")
        if selected["source_line"] != source_line or selected["split"] != annotation["split"]:
            errors.append(f"{case_id}: selection manifest is stale")
        if prov["source"]["page_sha256"] != source["source_page_sha256"]:
            errors.append(f"{case_id}: provenance page hash mismatch")
        if prov["split"] != annotation["split"]:
            errors.append(f"{case_id}: provenance split mismatch")
        if not str(annotation.get("client_role") or "").strip():
            empty_or_whitespace_fields.append(f"{case_id}/client_role")
        if not str(annotation.get("consultation_stage") or "").strip():
            empty_or_whitespace_fields.append(f"{case_id}/consultation_stage")
        if not str(annotation.get("editorial_note") or "").strip():
            empty_or_whitespace_fields.append(f"{case_id}/editorial_note")
        if not (
            source.get("publisher")
            == "Supreme People's Court of the People's Republic of China"
            and str(source.get("source_url") or "").startswith(
                "https://www.court.gov.cn/"
            )
        ):
            source_authority_failures.append(case_id)
        pipeline = prov.get("annotation_pipeline") or {}
        if not (
            pipeline.get("authoring_model") == "gpt-5.6-sol"
            and pipeline.get("reasoning_effort") == "high"
            and pipeline.get("prior_rejected_draft_used_as_annotation_input") is False
            and pipeline.get("source_level_reconstruction") is True
        ):
            authoring_identity_failures.append(case_id)
        page_splits[source["source_page_sha256"]].add(annotation["split"])
        split_domains[annotation["split"]][annotation["legal_domain"]] += 1
        review = annotation.get("editorial_review") or {}
        missing_checks = sorted(REQUIRED_EDITORIAL_CHECKS - {
            key for key, value in review.items() if value is True
        })
        if missing_checks:
            errors.append(f"{case_id}: incomplete casewise review {missing_checks}")
        for fact in annotation["facts"]:
            if not fact.get("evidence"):
                unsupported_fact_ids.append(f"{case_id}/{fact.get('fact_id')}")
            for evidence in fact["evidence"]:
                evidence_quotes += 1
                if evidence["quote"] not in source[evidence["section"]]:
                    errors.append(f"{case_id}: non-verbatim source evidence")

        case = core_by_id[case_id]
        expected_fact_ids = [f"F{index}" for index in range(1, len(case["facts"]) + 1)]
        actual_fact_ids = [str(fact["fact_id"]) for fact in case["facts"]]
        if actual_fact_ids != expected_fact_ids:
            fact_id_failures.append(case_id)
        core_content = {key: value for key, value in case.items() if key != "sha256"}
        actual_case_digest = hashlib.sha256(
            json.dumps(
                core_content,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        if case.get("sha256") != actual_case_digest:
            case_digest_failures.append(case_id)
        if prov.get("core_sha256") != case.get("sha256"):
            case_digest_failures.append(f"{case_id}/provenance")
        local_fields: dict[str, list[str]] = {
            "fact_beliefs": [str(fact["client_belief"]) for fact in case["facts"]],
            "fact_records": [str(fact["court_record"]) for fact in case["facts"]],
            "inquiries": [
                str(value)
                for value in case["evaluation_criteria"]["expected_inquiries"]
            ],
            "memo_expectations": [
                str(value)
                for value in case["evaluation_criteria"]["memo_expectations"]
            ],
        }
        for field_name, values in local_fields.items():
            if any(not value.strip() or value != value.strip() for value in values):
                empty_or_whitespace_fields.append(f"{case_id}/{field_name}")
            normalized_values = [normalized(value) for value in values]
            if len(normalized_values) != len(set(normalized_values)):
                within_case_duplicate_fields.append(f"{case_id}/{field_name}")

    if Counter(item["split"] for item in provenance) != {"train": 128}:
        errors.append("formal corpus is not exactly 128 training cases")
    if len(split_domains["train"]) != 14:
        errors.append("training corpus must cover exactly 14 declared domains")

    schema = json.loads(OFFICIAL_SCHEMA.read_text(encoding="utf-8"))
    schema_errors = [
        f"{case['id']}: {error.message}"
        for case in core
        for error in Draft202012Validator(schema).iter_errors(case)
    ]
    errors.extend(schema_errors)

    duplicate_groups: dict[str, list[list[str]]] = {}
    text_fields: dict[str, list[tuple[str, str]]] = defaultdict(list)
    opening_containment: list[dict[str, str]] = []
    for case in core:
        text_fields["opening"].append((case["id"], case["opening"]))
        opening_norm = normalized(case["opening"])
        for fact in case["facts"]:
            label = f"{case['id']}/{fact['fact_id']}"
            text_fields["client_belief"].append((label, fact["client_belief"]))
            text_fields["court_record"].append((label, fact["court_record"]))
            belief_norm = normalized(fact["client_belief"])
            if belief_norm in opening_norm or opening_norm in belief_norm:
                opening_containment.append({"case_fact": label})
        for index, value in enumerate(case["evaluation_criteria"]["expected_inquiries"], 1):
            text_fields["expected_inquiry"].append((f"{case['id']}/Q{index}", value))
        for index, value in enumerate(case["evaluation_criteria"]["memo_expectations"], 1):
            text_fields["memo_expectation"].append((f"{case['id']}/M{index}", value))
    for field, rows in text_fields.items():
        grouped: dict[str, list[str]] = defaultdict(list)
        for label, value in rows:
            grouped[normalized(value)].append(label)
        duplicate_groups[field] = [labels for labels in grouped.values() if len(labels) > 1]
    if any(duplicate_groups.values()):
        errors.append("normalized exact duplicate authoring text exists")
    if opening_containment:
        errors.append("an opening fully contains a hidden belief (or vice versa)")
    if fact_id_failures:
        errors.append("fact IDs are not contiguous within one or more cases")
    if empty_or_whitespace_fields:
        errors.append("empty or edge-whitespace semantic fields exist")
    if within_case_duplicate_fields:
        errors.append("within-case duplicate semantic fields exist")
    if case_digest_failures:
        errors.append("core case or provenance case digest drift exists")
    if unsupported_fact_ids:
        errors.append("one or more formal facts lack verbatim source evidence")
    if source_authority_failures:
        errors.append("one or more selected sources are not bound to the official SPC host")
    if authoring_identity_failures:
        errors.append("one or more provenance records have an inconsistent authoring identity")

    case_grams = {case["id"]: grams(case_text(case)) for case in core}
    train_ids = [item["id"] for item in provenance if item["split"] == "train"]
    similarities: list[dict[str, Any]] = []
    for left_index, train_id in enumerate(train_ids):
        for other_id in train_ids[left_index + 1:]:
            left, right = case_grams[train_id], case_grams[other_id]
            score = len(left & right) / len(left | right) if left | right else 0.0
            similarities.append({"left_id": train_id, "right_id": other_id,
                                 "fivegram_jaccard": round(score, 6)})
    similarities.sort(key=lambda item: item["fivegram_jaccard"], reverse=True)
    maximum_similarity = similarities[0]["fivegram_jaccard"] if similarities else 0.0
    if maximum_similarity >= 0.20:
        errors.append("within-corpus five-gram similarity exceeds the 0.20 duplicate threshold")

    payload = {
        "schema_version": 1,
        "status": "passed" if not errors else "failed",
        "scope": "all_128_cases_cpu_source_and_casewise_editorial_audit",
        "claim_boundary": {
            "source_grounded_ai_authored": True,
            "current_session_casewise_semantic_review": True,
            "opening_information_boundary": (
                "owned_by_separate_current_report_models_screen_researcher_adjudicates"
            ),
            "lawyer_expert_gold": False,
        },
        "counts": {
            "cases": len(core),
            "source_pool_cases": len(sources),
            "selected_source_cases": len(selected_lines),
            "excluded_source_cases": len(excluded_lines),
            "selected_official_pages": len(page_splits),
            "evidence_quotes_verified": evidence_quotes,
        },
        "splits": {
            "train": 128,
            "train_pages": len(page_splits),
            "train_domains": dict(sorted(split_domains["train"].items())),
            "maximum_within_corpus_fivegram_jaccard": maximum_similarity,
            "highest_within_corpus_similarity_pairs": similarities[:10],
        },
        "text_integrity": {
            "normalized_exact_duplicate_groups": duplicate_groups,
            "exact_opening_hidden_belief_containment": opening_containment,
            "official_schema_passed": not schema_errors,
            "official_schema_errors": schema_errors,
        },
        "edge_integrity": {
            "canonical_contiguous_case_ids": expected_ids == canonical_ids,
            "unique_selected_source_case_per_formal_case": (
                len(selected_lines) == len(selection["records"])
            ),
            "fact_id_failures": fact_id_failures,
            "empty_or_whitespace_fields": empty_or_whitespace_fields,
            "within_case_duplicate_fields": within_case_duplicate_fields,
            "case_digest_failures": case_digest_failures,
            "unsupported_fact_ids": unsupported_fact_ids,
            "source_authority_failures": source_authority_failures,
            "authoring_identity_failures": authoring_identity_failures,
        },
        "shape_comparison": {
            "main_corpus": corpus_shape(core),
            "official_public_cn30": corpus_shape(official),
            "interpretation": "task_schema_aligned_but_distribution_not_forced_to_match",
        },
        "bounded_source_ambiguities": [
            {
                "case_id": "lsg_cn_0045",
                "issue": (
                    "official_page_uses_both_ready_mixed_concrete_and_"
                    "substandard_cement_wording"
                ),
                "handling": (
                    "preserved_as_source_uncertainty_and_requires_original_contract_"
                    "test_report_and_penalty_decision"
                ),
            }
        ],
        "core_sha256": hashlib.sha256(CORE.read_bytes()).hexdigest(),
        "provenance_sha256": hashlib.sha256(PROVENANCE.read_bytes()).hexdigest(),
        "selection_sha256": hashlib.sha256(SELECTION.read_bytes()).hexdigest(),
        "errors": errors,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if errors:
        raise SystemExit("main corpus casewise quality audit failed")


if __name__ == "__main__":
    main()
