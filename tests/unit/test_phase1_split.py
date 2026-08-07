from __future__ import annotations

import json
from pathlib import Path

from scripts.make_phase1_pilot_split import build_manifest


def record(case_id: str) -> dict:
    return {
        "id": case_id,
        "opening": f"opening {case_id}",
        "facts": [
            {
                "client_belief": f"belief {case_id}",
                "court_record": f"record {case_id}",
                "gap_type": "disputed",
            }
        ],
        "evaluation_criteria": {
            "expected_inquiries": ["ask"],
            "memo_expectations": ["memo"],
        },
    }


def test_phase1_split_is_disjoint_complete_and_deterministic(tmp_path: Path) -> None:
    records = [record(f"case_cn_{index:04d}") for index in range(1, 31)]
    source = tmp_path / "cases.jsonl"
    source.write_text("\n".join(json.dumps(item) for item in records), encoding="utf-8")
    first = build_manifest(records, 42, source)
    second = build_manifest(list(reversed(records)), 42, source)

    first.pop("manifest_sha256")
    second.pop("manifest_sha256")
    assert first == second

    partitions = first["partitions"]
    assert [partitions[name]["stats"]["cases"] for name in partitions] == [20, 5, 5]
    case_sets = [set(value["case_ids"]) for value in partitions.values()]
    assert len(set.union(*case_sets)) == 30
    assert not any(case_sets[i] & case_sets[j] for i in range(3) for j in range(i + 1, 3))
