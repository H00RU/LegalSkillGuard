"""Audit formal corpus and behavior assets against the external public benchmark."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OFFICIAL = ROOT / "third_party/DLawBench/data/case_backgrounds/cases_cn.jsonl"
SOURCES = (
    ROOT / "data/source_pool/spc_typical_cases.jsonl",
    ROOT / "data/source_pool/spc_reference_cases.jsonl",
    ROOT / "data/source_pool/spc_labor_consumer_cases.jsonl",
    ROOT / "data/source_pool/spc_procedure_insurance_cases.jsonl",
    ROOT / "data/source_pool/spc_expansion_128_cases.jsonl",
)
SELECTION = ROOT / "data/manifests/main_corpus_selection.json"
CORE = ROOT / "data/training/legal_skill_guard_dlawbench_style_cn.jsonl"
REPORT = ROOT / "reports/artifacts/main_corpus_contamination.json"


def normalize(value: str) -> str:
    return re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", value)


def grams(value: str, size: int) -> set[str]:
    value = normalize(value)
    return {value[index : index + size] for index in range(max(0, len(value) - size + 1))}


def all_case_text(record: dict) -> str:
    return (
        record["opening"]
        + "".join(fact["client_belief"] + fact["court_record"] for fact in record["facts"])
        + "".join(record["evaluation_criteria"]["expected_inquiries"])
        + "".join(record["evaluation_criteria"]["memo_expectations"])
    )


def main() -> None:
    official = [
        json.loads(line) for line in OFFICIAL.read_text(encoding="utf-8").splitlines() if line
    ]
    core = [json.loads(line) for line in CORE.read_text(encoding="utf-8").splitlines() if line]
    selected_shas = {
        item["source_case_sha256"]
        for item in json.loads(SELECTION.read_text(encoding="utf-8"))["records"]
    }
    sources = [
        item
        for source_path in SOURCES
        for line in source_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
        for item in [json.loads(line)]
        if item["source_case_sha256"] in selected_shas
    ]
    external = [(item["id"], all_case_text(item)) for item in official]
    candidates = [
        (item["source_case_sha256"], item["basic_facts"] + item["adjudication"]) for item in sources
    ] + [(item["id"], all_case_text(item)) for item in core]

    external_five = [(case_id, grams(text, 5)) for case_id, text in external]
    external_fifty = [(case_id, grams(text, 50)) for case_id, text in external]
    similarities: list[dict[str, object]] = []
    exact_long_overlap: list[dict[str, object]] = []
    for candidate_id, text in candidates:
        candidate_five = grams(text, 5)
        candidate_fifty = grams(text, 50)
        for (official_id, official_five), (_, official_fifty) in zip(
            external_five, external_fifty, strict=True
        ):
            union = candidate_five | official_five
            score = len(candidate_five & official_five) / len(union) if union else 0.0
            if score:
                similarities.append(
                    {
                        "candidate_id": candidate_id,
                        "official_id": official_id,
                        "fivegram_jaccard": round(score, 6),
                    }
                )
            overlap = candidate_fifty & official_fifty
            if overlap:
                exact_long_overlap.append(
                    {
                        "candidate_id": candidate_id,
                        "official_id": official_id,
                        "sample": sorted(overlap)[0],
                    }
                )

    asset_roots = [ROOT / "configs/prompts", ROOT / "skills/bootstrap"]
    asset_text = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for directory in asset_roots
        for path in directory.rglob("*")
        if path.is_file()
    )
    leaked_ids = sorted(item["id"] for item in official if item["id"] in asset_text)
    top = sorted(similarities, key=lambda item: float(item["fivegram_jaccard"]), reverse=True)[:20]
    max_similarity = float(top[0]["fivegram_jaccard"]) if top else 0.0
    status = (
        "passed"
        if not exact_long_overlap and not leaked_ids and max_similarity < 0.05
        else "failed"
    )
    payload = {
        "status": status,
        "external_cases": len(official),
        "selected_source_cases": len(sources),
        "formal_core_cases": len(core),
        "formal_core_sha256": hashlib.sha256(CORE.read_bytes()).hexdigest(),
        "selection_sha256": hashlib.sha256(SELECTION.read_bytes()).hexdigest(),
        "exact_50_character_overlaps": exact_long_overlap,
        "external_case_ids_in_behavior_assets": leaked_ids,
        "maximum_fivegram_jaccard": max_similarity,
        "highest_similarity_pairs": top,
        "thresholds": {"exact_50_character_overlaps": 0, "fivegram_jaccard_exclusive_upper": 0.05},
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if status != "passed":
        raise SystemExit("formal corpus contamination audit failed")


if __name__ == "__main__":
    main()
