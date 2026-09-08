#!/usr/bin/env python3
"""Audit the real DLawBench release without inventing unavailable metadata."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from collections import Counter
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REVISION = "9f6325f29f07b296fac110a6e1880bdd5d9ca538"
DEFAULT_DATASET = ROOT / "data" / "raw" / "dlawbench" / REVISION
DEFAULT_OUTPUT = ROOT / "reports" / "artifacts" / "dlawbench_audit.json"

PAPER_CORPUS = {
    "CN": {
        "cases": 264,
        "fact_pairs": 2877,
        "disputed_fact_pairs": 2043,
        "inquiry_rubrics": 1735,
        "issue_rubrics": 1642,
    },
    "US": {
        "cases": 197,
        "fact_pairs": 2655,
        "disputed_fact_pairs": 1757,
        "inquiry_rubrics": 1676,
        "issue_rubrics": 1706,
    },
}

# These are aggregate labels printed in assets/domain_distribution.png for the paper
# corpus. They are not per-record metadata and cannot be used for stratified splitting.
PAPER_CN_DOMAINS = {
    "corporate_finance_bankruptcy": 48,
    "ip_and_competition": 41,
    "administrative_law": 36,
    "criminal_law": 28,
    "family_and_succession": 25,
    "internet_virtual_property": 23,
    "labor_social_security": 21,
    "torts_personality": 17,
    "contracts_and_claims": 13,
    "real_estate_construction": 12,
}


def canonical_record_sha256(record: dict[str, Any]) -> str:
    payload = dict(record)
    payload.pop("sha256", None)
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            record = json.loads(line)
            record["_source_line"] = line_number
            records.append(record)
    return records


def numeric_summary(values: Iterable[int]) -> dict[str, float | int | dict[str, int]]:
    numbers = list(values)
    histogram = Counter(numbers)
    return {
        "count": len(numbers),
        "sum": sum(numbers),
        "min": min(numbers) if numbers else 0,
        "max": max(numbers) if numbers else 0,
        "mean": round(statistics.fmean(numbers), 4) if numbers else 0.0,
        "median": statistics.median(numbers) if numbers else 0.0,
        "histogram": {str(key): histogram[key] for key in sorted(histogram)},
    }


def field_presence(records: list[dict[str, Any]]) -> dict[str, Any]:
    top = Counter()
    fact = Counter()
    criteria = Counter()
    for record in records:
        top.update(key for key in record if not key.startswith("_"))
        for item in record.get("facts", []):
            fact.update(item)
        criteria.update(record.get("evaluation_criteria", {}))
    return {
        "top_level": dict(sorted(top.items())),
        "fact": dict(sorted(fact.items())),
        "evaluation_criteria": dict(sorted(criteria.items())),
    }


def audit_jurisdiction(records: list[dict[str, Any]]) -> dict[str, Any]:
    facts = [fact for record in records for fact in record["facts"]]
    inquiries = [
        text for record in records for text in record["evaluation_criteria"]["expected_inquiries"]
    ]
    memo_expectations = [
        text for record in records for text in record["evaluation_criteria"]["memo_expectations"]
    ]
    gap_counts = Counter(fact["gap_type"] for fact in facts)
    return {
        "cases": len(records),
        "case_style_cells": len(records) * 4,
        "languages": dict(Counter(record["language"] for record in records)),
        "facts": {
            "total": len(facts),
            "gap_type": dict(sorted(gap_counts.items())),
            "per_case": numeric_summary(len(record["facts"]) for record in records),
        },
        "rubrics": {
            "expected_inquiries_total": len(inquiries),
            "memo_expectations_total": len(memo_expectations),
            "expected_inquiries_per_case": numeric_summary(
                len(record["evaluation_criteria"]["expected_inquiries"]) for record in records
            ),
            "memo_expectations_per_case": numeric_summary(
                len(record["evaluation_criteria"]["memo_expectations"]) for record in records
            ),
        },
        "text_lengths_characters": {
            "opening": numeric_summary(len(record["opening"]) for record in records),
            "client_belief": numeric_summary(len(fact["client_belief"]) for fact in facts),
            "court_record": numeric_summary(len(fact["court_record"]) for fact in facts),
            "expected_inquiry": numeric_summary(len(text) for text in inquiries),
            "memo_expectation": numeric_summary(len(text) for text in memo_expectations),
        },
    }


def validate_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    ids = [record["id"] for record in records]
    checksum_failures = []
    for record in records:
        public_record = {key: value for key, value in record.items() if not key.startswith("_")}
        if canonical_record_sha256(public_record) != record["sha256"]:
            checksum_failures.append(record["id"])
    return {
        "unique_ids": len(set(ids)) == len(ids),
        "checksum_failures": checksum_failures,
        "valid": len(set(ids)) == len(ids) and not checksum_failures,
    }


def audit(dataset_root: Path) -> dict[str, Any]:
    """Return the complete deterministic audit for a prepared snapshot."""

    cn = load_jsonl(dataset_root / "data" / "case_backgrounds" / "cases_cn.jsonl")
    us = load_jsonl(dataset_root / "data" / "case_backgrounds" / "cases_us.jsonl")
    all_records = cn + us
    personas = json.loads((dataset_root / "config" / "personas.json").read_text(encoding="utf-8"))
    persona_items = {key: value for key, value in personas.items() if not key.startswith("_")}

    observed = {"CN": audit_jurisdiction(cn), "US": audit_jurisdiction(us)}
    observed["TOTAL"] = audit_jurisdiction(all_records)
    release_matches_paper = all(
        observed[jurisdiction]["cases"] == PAPER_CORPUS[jurisdiction]["cases"]
        for jurisdiction in ("CN", "US")
    )

    report = {
        "audited_at": datetime.now(UTC).isoformat(),
        "dataset_root": str(dataset_root.resolve()),
        "revision": REVISION,
        "validation": validate_records(all_records),
        "observed_public_release": observed,
        "paper_reported_corpus": PAPER_CORPUS,
        "release_matches_paper_corpus_size": release_matches_paper,
        "release_gap": {
            **{
                jurisdiction: PAPER_CORPUS[jurisdiction]["cases"] - observed[jurisdiction]["cases"]
                for jurisdiction in ("CN", "US")
            },
            "full_corpus_present": release_matches_paper,
        },
        "domains": {
            "per_case_field_available": all("domain" in record for record in all_records),
            "case_level_metadata_available": all("domain" in record for record in all_records),
            "public_release_distribution": None,
            "reason": (
                "Neither public case JSONL nor metadata includes a domain field; assigning "
                "the 60 records to domains would require unverified manual relabeling."
            ),
            "paper_cn_aggregate_from_figure": PAPER_CN_DOMAINS,
            "paper_cn_aggregate_sum": sum(PAPER_CN_DOMAINS.values()),
            "provenance": "third_party/DLawBench/assets/domain_distribution.png",
        },
        "personas": {
            "count": len(persona_items),
            "keys": list(persona_items),
            "names_cn": {key: value["name_cn"] for key, value in persona_items.items()},
            "public_cn_case_style_cells_by_persona": {key: len(cn) for key in persona_items},
        },
        "field_presence": field_presence(all_records),
        "schema_top_level_required": [
            "id",
            "jurisdiction",
            "language",
            "opening",
            "facts",
            "evaluation_criteria",
            "sha256",
        ],
        "known_upstream_issue": "https://github.com/SKYLENAGE-AI/DLawBench/issues/1",
    }
    report["jurisdictions"] = {
        jurisdiction: {
            "cases": observed[jurisdiction]["cases"],
            "facts": observed[jurisdiction]["facts"]["total"],
            "disputed_facts": observed[jurisdiction]["facts"]["gap_type"].get("disputed", 0),
            "inquiry_rubrics": observed[jurisdiction]["rubrics"]["expected_inquiries_total"],
            "memo_rubrics": observed[jurisdiction]["rubrics"]["memo_expectations_total"],
        }
        for jurisdiction in ("CN", "US")
    }
    report["integrity"] = {
        "record_hashes_valid": report["validation"]["valid"],
        "checksum_failures": report["validation"]["checksum_failures"],
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-root", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    report = audit(args.dataset_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "CN_cases": report["jurisdictions"]["CN"]["cases"],
                "US_cases": report["jurisdictions"]["US"]["cases"],
                "valid": report["validation"]["valid"],
                "release_matches_paper": report["release_matches_paper_corpus_size"],
            }
        )
    )


if __name__ == "__main__":
    main()
