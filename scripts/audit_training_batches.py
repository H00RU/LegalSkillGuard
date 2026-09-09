"""Audit frozen 8x16 sequential direct skill-accumulation blocks."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

from legal_skill_guard.environment.dlawbench_adapter import DLawBenchAdapter
from legal_skill_guard.experiment.batches import load_training_batch_plan
from legal_skill_guard.utils.hashing import sha256_file

ROOT = Path(__file__).resolve().parents[1]


def jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def summarize_cases(
    case_ids: list[str], core: dict[str, dict[str, Any]], provenance: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    domains = Counter(provenance[item]["annotation"]["legal_domain"] for item in case_ids)
    sources = Counter(provenance[item]["source"]["source_id"] for item in case_ids)
    source_pages = Counter(provenance[item]["source"]["page_sha256"] for item in case_ids)
    years = Counter(str(provenance[item]["source"]["published_at"])[:4] for item in case_ids)
    return {
        "cases": len(case_ids),
        "domains": dict(sorted(domains.items())),
        "domain_count": len(domains),
        "source_count": len(sources),
        "maximum_cases_from_one_source": max(sources.values()),
        "source_page_count": len(source_pages),
        "maximum_cases_from_one_source_page": max(source_pages.values()),
        "years": dict(sorted(years.items())),
        "facts": sum(len(core[item]["facts"]) for item in case_ids),
        "disputed_facts": sum(
            fact["gap_type"] == "disputed" for item in case_ids for fact in core[item]["facts"]
        ),
        "expected_inquiries": sum(
            len(core[item]["evaluation_criteria"]["expected_inquiries"]) for item in case_ids
        ),
        "memo_expectations": sum(
            len(core[item]["evaluation_criteria"]["memo_expectations"]) for item in case_ids
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "reports/artifacts/main_training_batch_audit.json",
    )
    args = parser.parse_args()
    plan_path = ROOT / "configs/data/main_training_batches.yaml"
    plan = yaml.safe_load(plan_path.read_text(encoding="utf-8"))
    adapter = DLawBenchAdapter(
        ROOT / "data/training/legal_skill_guard_dlawbench_style_cn.jsonl",
        ROOT / "third_party/DLawBench/config/personas.json",
        ROOT / "data/training/legal_skill_guard_dlawbench_style_cn.provenance.jsonl",
    )
    validated_plan = load_training_batch_plan(plan_path, adapter)
    core = {
        item["id"]: item
        for item in jsonl(ROOT / "data/training/legal_skill_guard_dlawbench_style_cn.jsonl")
    }
    provenance = {
        item["id"]: item
        for item in jsonl(
            ROOT / "data/training/legal_skill_guard_dlawbench_style_cn.provenance.jsonl"
        )
    }
    cumulative: set[str] = set()
    batches: dict[str, Any] = {}
    for item in plan["batches"]:
        cumulative.update(item["case_ids"])
        summary = summarize_cases(item["case_ids"], core, provenance)
        summary["persona_counts"] = dict(
            sorted(Counter(item["persona_assignment"].values()).items())
        )
        summary["cumulative_cases"] = len(cumulative)
        summary["cumulative_domains"] = len(
            {provenance[case_id]["annotation"]["legal_domain"] for case_id in cumulative}
        )
        batches[item["batch_id"]] = summary
    official = json.loads(
        (ROOT / "third_party/DLawBench/metadata/dataset_summary.json").read_text(encoding="utf-8")
    )["statistics"]["CN"]
    all_ids = [case_id for item in plan["batches"] for case_id in item["case_ids"]]
    errors: list[str] = []
    if len(validated_plan.batches) != 8 or [
        len(item.case_ids) for item in validated_plan.batches
    ] != [16] * 8:
        errors.append("training plan is not exactly eight blocks of sixteen cases")
    minimum_pages = int(plan["coverage_requirements"]["minimum_source_pages_per_batch"])
    maximum_per_page = int(
        plan["coverage_requirements"]["maximum_cases_from_one_source_page_per_batch"]
    )
    for batch_id, summary in batches.items():
        if int(summary["source_page_count"]) < minimum_pages:
            errors.append(f"{batch_id} has too few source pages")
        if int(summary["maximum_cases_from_one_source_page"]) > maximum_per_page:
            errors.append(f"{batch_id} concentrates too many cases from one source page")
    report = {
        "schema_version": 3,
        "status": "passed" if not errors else "failed",
        "design": plan["design"],
        "evidence_boundary": "formal_corpus_and_frozen_batch_plan_only",
        "training": summarize_cases(all_ids, core, provenance),
        "controlled_training_persona": plan["coverage_requirements"]["training_persona"],
        "batches": batches,
        "training_batch_plan_sha256": sha256_file(plan_path),
        "skill_accumulation": plan["skill_accumulation"],
        "candidate_outcome_validation_pool": False,
        "all_blocks_generate_skills": bool(
            plan["skill_accumulation"]["final_batch_generates_skills"]
        ),
        "official_public_cn_release": official,
        "official_public_cn_file_cases": len(
            jsonl(ROOT / "third_party/DLawBench/data/case_backgrounds/cases_cn.jsonl")
        ),
        "errors": errors,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if errors:
        raise SystemExit("main training batch audit failed")


if __name__ == "__main__":
    main()
