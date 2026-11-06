"""Audit acquired adapters without displaying or evaluating held-out answers."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from legal_skill_guard.rr.adapters import contractnli, openexempt, rulearena_airline, sara_v2
from legal_skill_guard.rr.coverage import digest

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    raw = ROOT / "data/cache/rr_v2"
    audit = {}
    datasets = [sara_v2(raw / "sara_v2.tar.gz"), contractnli(raw / "contract-nli.zip"),
                rulearena_airline(raw / "RuleArena/airline"),
                openexempt(raw / "openexempt_generated.json")]
    for data in datasets:
        dataset = data.sources[0].dataset
        train = {s.key for s in data.sources if s.native_split == "train"}
        test = {s.key for s in data.sources if s.native_split == "test"}
        dev = {s.key for s in data.sources if s.native_split == "dev"}
        audit[dataset] = {
            "counts_by_native_partition": dict(Counter(s.native_split for s in data.sources)),
            "clean_native_train_groups": len(train - test - dev),
            "cross_train_test_clusters": len(train & test),
            "public_sources_sha256": digest(data.sources), "grading_sha256": digest(data.grading),
            "audit": data.audit}
    target = ROOT / "reports/rr_v2_evidence/adapter_audit_partial.json"
    target.write_text(json.dumps(audit, indent=2) + "\n")
    print(json.dumps({d: {"native_counts": v["counts_by_native_partition"],
                         "cross_train_test_clusters": v["cross_train_test_clusters"]}
                      for d, v in audit.items()}, indent=2))


if __name__ == "__main__":
    main()
