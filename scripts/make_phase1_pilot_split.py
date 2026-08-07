#!/usr/bin/env python3
"""Create a deterministic non-formal pilot split for the 30 public CN cases."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from legal_skill_guard.utils.hashing import canonical_json_sha256, sha256_file

ROOT = Path(__file__).resolve().parents[1]
REVISION = "9f6325f29f07b296fac110a6e1880bdd5d9ca538"
DEFAULT_CASES = (
    ROOT
    / "data"
    / "raw"
    / "dlawbench"
    / REVISION
    / "data"
    / "case_backgrounds"
    / "cases_cn.jsonl"
)
DEFAULT_OUTPUT = ROOT / "data" / "splits" / "dlawbench_public30_phase1_seed42.json"


def load_records(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def order_key(case_id: str, seed: int) -> str:
    return hashlib.sha256(f"{seed}:{case_id}".encode()).hexdigest()


def normalize_text(value: str) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff]", "", value.casefold())


def shingles(value: str, width: int = 3) -> set[str]:
    text = normalize_text(value)
    if len(text) < width:
        return {text} if text else set()
    return {text[index : index + width] for index in range(len(text) - width + 1)}


def jaccard(left: set[str], right: set[str]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 0.0


def record_text(record: dict[str, Any]) -> str:
    fields = [record["opening"]]
    for fact in record["facts"]:
        fields.extend((fact["client_belief"], fact["court_record"]))
    return "\n".join(fields)


def partition_stats(records: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "cases": len(records),
        "facts": sum(len(record["facts"]) for record in records),
        "disputed_facts": sum(
            fact["gap_type"] == "disputed" for record in records for fact in record["facts"]
        ),
        "inquiry_rubrics": sum(
            len(record["evaluation_criteria"]["expected_inquiries"]) for record in records
        ),
        "memo_rubrics": sum(
            len(record["evaluation_criteria"]["memo_expectations"]) for record in records
        ),
        "case_persona_cells": len(records) * 4,
    }


def cross_partition_similarity(
    left: list[dict[str, Any]], right: list[dict[str, Any]], threshold: float = 0.85
) -> dict[str, Any]:
    pairs = []
    for left_record in left:
        left_shingles = shingles(record_text(left_record))
        for right_record in right:
            similarity = jaccard(left_shingles, shingles(record_text(right_record)))
            pairs.append((similarity, left_record["id"], right_record["id"]))
    pairs.sort(reverse=True)
    return {
        "metric": "character_3gram_jaccard_on_opening_and_all_fact_text",
        "threshold": threshold,
        "pairs_compared": len(pairs),
        "near_duplicate_pairs": sum(similarity >= threshold for similarity, _, _ in pairs),
        "maximum_similarity": round(pairs[0][0], 6) if pairs else 0.0,
        "maximum_pair": list(pairs[0][1:]) if pairs else [],
    }


def build_manifest(records: list[dict[str, Any]], seed: int, source: Path) -> dict[str, Any]:
    if len(records) != 30 or len({record["id"] for record in records}) != 30:
        raise ValueError("Phase 1 pilot protocol requires exactly 30 unique public CN cases")
    ordered = sorted(records, key=lambda record: (order_key(record["id"], seed), record["id"]))
    partitions = {
        "pilot_generation": ordered[:20],
        "pilot_acceptance": ordered[20:25],
        "pilot_reserve": ordered[25:],
    }
    try:
        source_path = str(source.relative_to(ROOT))
    except ValueError:
        source_path = str(source.resolve())
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "protocol": "public30_engineering_pilot_not_formal_paper_split",
        "seed": seed,
        "algorithm": "sort by sha256(f'{seed}:{case_id}') then slice 20/5/5",
        "source": {
            "revision": REVISION,
            "path": source_path,
            "sha256": sha256_file(source),
        },
        "constraints": {
            "case_id_is_group": True,
            "all_personas_inherit_partition": True,
            "domain_stratified": False,
            "domain_stratification_reason": "public release has no per-case domain metadata",
            "formal_held_out_test": False,
        },
        "partitions": {
            name: {
                "case_ids": [record["id"] for record in items],
                "stats": partition_stats(items),
            }
            for name, items in partitions.items()
        },
        "near_duplicate_checks": {
            "generation_vs_acceptance": cross_partition_similarity(
                partitions["pilot_generation"], partitions["pilot_acceptance"]
            ),
            "generation_vs_reserve": cross_partition_similarity(
                partitions["pilot_generation"], partitions["pilot_reserve"]
            ),
        },
    }
    manifest["manifest_sha256"] = canonical_json_sha256(manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    manifest = build_manifest(load_records(args.cases), args.seed, args.cases)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "partition_sizes": {
                    key: value["stats"]["cases"]
                    for key, value in manifest["partitions"].items()
                },
                "manifest_sha256": manifest["manifest_sha256"],
            }
        )
    )


if __name__ == "__main__":
    main()
