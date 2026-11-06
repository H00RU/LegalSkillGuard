"""Prepare immutable five-benchmark packets and the fixed 20-source allowlist.

This does not perform model inference, formal training or frozen evaluation.
Annotations are separated mechanically into grading-only files, never logged.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from legal_skill_guard.rr.adapters import (
    contractnli,
    openexempt,
    proofwriter,
    rulearena_airline,
    sara_v2,
)
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.ledger import DATASETS
from legal_skill_guard.rr.oracles import airline
from legal_skill_guard.rr.partitions import preflight_sources, split_sources

ROOT = Path(__file__).resolve().parents[1]


def main():
    raw = ROOT / "data/cache/rr_v2"
    destination = ROOT / "data/packets/rr_v2"
    datasets = [openexempt(raw / "openexempt_generated.json"),
                rulearena_airline(raw / "RuleArena/airline"), sara_v2(raw / "sara_v2.tar.gz"),
                proofwriter(raw / "ProofWriter"), contractnli(raw / "contract-nli.zip")]
    records = [s for dataset in datasets for s in dataset.sources]
    split = split_sources(records)
    source_index = {(s.key, s.native_split, s.content_key): s for s in records}
    grade_index = {k: value for dataset in datasets for k, value in dataset.grading.items()}
    public_packets, grading_packets = {}, {}
    for partition in ("train", "dev", "test"):
        public_rows, grade_rows = [], {}
        for dataset in DATASETS:
            for entry in split["datasets"][dataset][partition]:
                source = source_index[(entry["key"], entry["native_split"], entry["content_hash"])]
                public_rows.append({**asdict(source), "key": source.key, "content_hash": source.content_key})
                grade_key = digest({"key": source.key, "split": source.native_split,
                                    "content": source.content_key})
                grade = grade_index[grade_key]
                if dataset == "RuleArena_Airline":
                    grade = {**grade, "answer": airline(grade["reference_arguments"])}
                grade_rows[source.key] = grade
        public_packets[partition] = {"split": partition, "sources": public_rows,
                                     "split_manifest_sha256": split["sha256"],
                                     "contains_gold_or_reference_program": False}
        grading_packets[partition] = {"split": partition, "never_to_actor_or_teacher": True,
                                      "sealed_until_formal_B8": partition == "test", "sources": grade_rows}
    allowlist = preflight_sources(split)
    pilot_order = [allowlist[d][i] for i in range(4) for d in DATASETS]
    train_keys = [s["key"] for s in public_packets["train"]["sources"]]
    formal_order = pilot_order + [s for s in train_keys if s not in pilot_order]
    if len(set(formal_order)) != 128 or len(formal_order) != 128:
        raise ValueError("Full build must have exactly 128 distinct sources")
    files = {}
    for partition, packet in public_packets.items():
        files[f"public_{partition}"] = immutable_json(destination / f"public_{partition}.json", packet)
        files[f"grading_{partition}"] = immutable_json(destination / "grading_only" / f"{partition}.json",
                                                       grading_packets[partition])
    member_receipt = json.loads((raw / "ProofWriter/acquisition.json").read_text())
    for entry in member_receipt["files"]:
        if hashlib.sha256((raw / "ProofWriter" / Path(entry["member"]).name).read_bytes()).hexdigest() != entry["sha256"]:
            raise ValueError("Official ProofWriter member hash changed")
    source_manifest = {"schema": 1, "protocol": "LSG-RR-v2", "split": split,
                       "allowlist": allowlist, "pilot_order": pilot_order,
                       "first_teacher_batch": pilot_order[:16], "formal_train_order": formal_order,
                       "packet_sha256": files, "data_hash": digest(files),
                       "test_labels_processed_mechanically_for_packet": True,
                       "test_predictions_started": False, "real_model_requests": 0,
                       "proofwriter_official_member_receipt_sha256": digest(member_receipt)}
    manifest_path = ROOT / "reports/rr_v2_evidence/data_manifest.json"
    immutable_json(manifest_path, source_manifest)
    audit = {d.sources[0].dataset: {**d.audit, "native_groups": len(d.sources),
                                   "public_sources_sha256": digest(d.sources)} for d in datasets}
    immutable_json(ROOT / "reports/rr_v2_evidence/five_adapter_audit.json", audit)
    print(json.dumps({"manifest": str(manifest_path), "data_hash": source_manifest["data_hash"],
                      "train_sources": len(train_keys), "dev_sources": len(public_packets["dev"]["sources"]),
                      "test_sources": len(public_packets["test"]["sources"]),
                      "preflight_sources": len(pilot_order), "requests": 0}, indent=2))


if __name__ == "__main__":
    main()
