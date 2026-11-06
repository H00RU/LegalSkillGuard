"""State roundtrip, frozen integrity, source isolation and open-world behavior."""
import json

import pytest

from legal_skill_guard.rr.checkpoint import Checkpoints, immutable_json
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.horn import Atom, Rule, closure
from legal_skill_guard.rr.ledger import DATASETS, BudgetLedger
from legal_skill_guard.rr.partitions import Source, preflight_sources, split_sources


def records():
    return [Source(d, str(i), {"facts": f"{d}:public:{i}"})
            for d in DATASETS for i in range(80)]


def test_fixed_dataset_counts_group_disjoint_and_deterministic():
    source_records = records()
    m = split_sources(source_records)
    assert split_sources(list(reversed(source_records))) == m
    assert sum(len(v["train"]) for v in m["datasets"].values()) == 128
    assert sum(len(v["dev"]) for v in m["datasets"].values()) == 40
    assert sum(len(v["test"]) for v in m["datasets"].values()) == 160
    for splits in m["datasets"].values():
        sets = [{r["key"] for r in splits[p]} for p in ("train", "dev", "test")]
        assert not sets[0] & sets[1] and not sets[0] & sets[2] and not sets[1] & sets[2]
    allowlist = preflight_sources(m)
    assert all(len(v) == 4 for v in allowlist.values())
    assert all(set(allowlist[d]) <= {r["key"] for r in m["datasets"][d]["train"]} for d in DATASETS)


def test_native_partitions_and_cross_split_stem_exclusion():
    rs = [Source(d, f"{s}:{i}", {"facts": f"{d}:{s}:{i}"}, s)
          for d in DATASETS for s in ("train", "dev", "test") for i in range(80)]
    rs += [Source("SARA_v2_Binary", "shared_stem", {"facts": "shared"}, s)
           for s in ("train", "test")]
    m = split_sources(rs)
    key = rs[-1].key
    assert {"source": key, "reason": "cross_native_partition_cluster"} in m["excluded"]
    assert all(r["key"] != key for s in ("train", "dev")
               for r in m["datasets"]["SARA_v2_Binary"][s])
    assert all(r["native_split"] == s for v in m["datasets"].values()
               for s, rows in v.items() for r in rows)


def test_duplicate_inputs_and_insufficient_groups_are_not_silently_resampled():
    rs = records()
    rs.append(Source(DATASETS[0], "new_id_same_case", rs[0].public))
    with pytest.raises(ValueError, match="Duplicate"):
        split_sources(rs)
    with pytest.raises(ValueError, match="Insufficient"):
        split_sources(records()[:10])


def test_tampered_manifest_cannot_authorize_model_sources():
    m = split_sources(records())
    m["datasets"][DATASETS[0]]["train"][0]["key"] = "test_injection"
    with pytest.raises(ValueError, match="hash"):
        preflight_sources(m)


def test_checkpoint_restores_partial_library_and_charged_calls(tmp_path):
    manifest = split_sources(records())
    b = BudgetLedger(tmp_path / "budget.sqlite3", sources=preflight_sources(manifest),
                     code_hash="code", config_hash="cfg")
    s = preflight_sources(manifest)[DATASETS[0]][0]
    b.reserve("c1", role="executor", purpose="pilot_ingestion", source=s, request={"step": 1})
    b.finish("c1", status="completed", result={"answer": "Unknown"})
    binding = {"code_hash": "code", "config_hash": "cfg", "data_hash": "data",
               "source_manifest_hash": manifest["sha256"]}
    checkpoints = Checkpoints(tmp_path / "state", binding)
    state = {"processed": [s], "pending": ["next"], "patterns": [{"fields": ["entity_equality"]}]}
    key = checkpoints.save(state, stage="preflight", ledger_export=b.export())
    restored = Checkpoints(tmp_path / "state", binding).load(key)
    assert restored["state"] == state and restored["ledger"]["executor_used"] == 1
    frozen = checkpoints.freeze_preflight(key)
    assert frozen["frozen"] and not frozen["formal_B8"]
    assert checkpoints.load(key) == restored
    with pytest.raises(ValueError, match="binding"):
        Checkpoints(tmp_path / "state", {**binding, "code_hash": "new"}).load(key)


def test_immutable_and_content_addressed_state_refuses_overwrite_and_tampering(tmp_path):
    path = tmp_path / "record.json"
    immutable_json(path, {"value": 1})
    immutable_json(path, {"value": 1})
    with pytest.raises(FileExistsError):
        immutable_json(path, {"value": 2})
    binding = {k: k for k in ("code_hash", "config_hash", "data_hash", "source_manifest_hash")}
    c = Checkpoints(tmp_path / "state", binding)
    key = c.save({"v": 1}, stage="preflight", ledger_export={})
    p = c.root / f"{key}.json"
    payload = json.loads(p.read_text())
    payload["state"]["v"] = 2
    p.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="corrupted"):
        c.load(key)
    with pytest.raises(ValueError):
        c.save({}, stage="B8", ledger_export={})
    with pytest.raises(ValueError):
        c.load("../../file")


def test_open_world_shared_variables_negative_evidence_and_conflict():
    a, b = Atom("A", ("alice",)), Atom("B", ("bob",))
    q = Atom("Eligible", ("alice",))
    rule = Rule((Atom("A", ("?x",)), Atom("B", ("?x",))),
                Atom("Eligible", ("?x",)), "source_clause")
    assert closure({a, b}, [rule], q)["answer"] == "Unknown"
    assert closure({a, Atom("B", ("alice",))}, [rule], q)["answer"] == "True"
    assert closure({a, b, q.negate()}, [rule], q)["answer"] == "False"
    assert closure({q, q.negate()}, [], q)["status"] == "conflict"


def test_horn_limits_range_restriction_and_exact_trace():
    q = Atom("P", ("a",))
    assert closure({q}, [], q, seconds=0)["status"] == "budget_exhausted"
    r = Rule((Atom("P", ("?x",)),), Atom("Q", ("?x",)), "clause2")
    result = closure({q}, [r], Atom("Q", ("a",)))
    assert result["answer"] == "True" and result["trace"][0]["source"] == "clause2"
    assert digest(result)
    assert closure({q}, [r], Atom("Q", ("a",)), max_rounds=1)["status"] == "budget_exhausted"
    with pytest.raises(ValueError, match="range"):
        closure({q}, [Rule((), Atom("Q", ("?x",)), "bad")], q)
