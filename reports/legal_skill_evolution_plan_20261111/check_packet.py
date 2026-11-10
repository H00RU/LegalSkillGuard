"""Offline packet integrity and protocol checks; does not open native test gold."""
import hashlib
import json
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parent


def read(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def canonical_check(obj):
    payload = dict(obj)
    expected = payload.pop("sha256")
    actual = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                      separators=(",", ":")).encode()).hexdigest()
    assert actual == expected, (actual, expected)
    return actual


def main():
    protocol = read("protocol.json")
    base = read(protocol["data"]["manifest"])
    pilot = read(protocol["pilot"]["manifest"])
    assert canonical_check(base) == protocol["data"]["manifest_canonical_sha256"]
    assert canonical_check(pilot) == protocol["pilot"]["manifest_canonical_sha256"]
    assert hashlib.sha256((ROOT / "candidate_source_manifest.json").read_bytes()).hexdigest() == pilot["base_manifest_file_sha256"]
    totals = Counter()
    train_keys = set()
    for dataset, partitions in base["datasets"].items():
        groups = {}
        for split in ["train", "dev", "test"]:
            rows = partitions[split]
            assert len(rows) == protocol["data"]["quotas"][dataset][split]
            group_field = "full_contract_hash" if dataset == "MAUD" else "group"
            groups[split] = {r[group_field] for r in rows}
            assert len(groups[split]) == len(rows)
            totals[split] += len(rows)
            if split == "train":
                train_keys.update(r["key"] for r in rows)
        assert not (groups["train"] & groups["dev"] or groups["train"] & groups["test"] or groups["dev"] & groups["test"])
    assert dict(totals) == protocol["data"]["source_total"]
    sequence = base["source_sequence"]
    assert len(sequence) == 8
    batch_keys = []
    for batch in sequence:
        counts = Counter(r["dataset"] for r in batch["sources"])
        assert counts == {"OpenExempt": 4, "SARA_v2_Binary": 3, "ContractNLI": 3, "RuleArena_Airline": 3, "MAUD": 3}
        batch_keys.extend(r["source_key"] for r in batch["sources"])
    assert len(batch_keys) == len(set(batch_keys)) == 128
    assert set(batch_keys) == train_keys
    pseq = pilot["source_sequence"]
    assert len(pseq) == len({r["key"] for r in pseq}) == 20
    assert all(r["key"] in train_keys and r["parent_split"] == "TRAIN" for r in pseq)
    assert Counter(r["dataset"] for r in pseq) == protocol["pilot"]["parent_source_counts"]
    assert sum(r["native_view_count"] for r in pseq) == 50
    assert sum(r["controlled_view_count"] for r in pseq) == 32
    assert len(protocol["formal_systems"]) == 7
    assert protocol["pilot"]["learning_passes"] == 1
    assert protocol["models"]["executor"]["weights_frozen"]
    assert not protocol["models"]["executor"]["thinking"]
    assert not protocol["current_action_authorization"]["resume_server"]
    assert not protocol["current_action_authorization"]["model_calls"]
    for name in ["PLAN.md", "SERVER_GOAL.md", "DATA_PLAN.md", "CONTROLLED_LAYER.md",
                 "METHOD_ACQUISITION.md", "METHOD_EVOLUTION.md", "ACQUISITION_PRIOR_ART.md",
                 "EVOLUTION_PRIOR_ART.md", "CONTROLLED_LAYER_EVIDENCE.json"]:
        assert (ROOT / name).is_file(), name
    result = {"packet_checks": "passed", "sources": dict(totals), "training_batches": 8,
              "pilot_parent_sources": 20, "pilot_views": {"native": 50, "controlled": 32},
              "formal_systems": 7, "model_calls": 0, "server_resumed": False,
              "native_test_gold_read_by_this_check": False,
              "pending_runtime_exposure_audit": True}
    (ROOT / "PACKET_CHECK.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
