"""Check whether the settled matched readers had already cited a sufficient witness."""

import json
import sqlite3
from collections import Counter
from pathlib import Path

from experiments.convergence_pilot_b0 import LEDGER, ROOT, read, sha
from experiments.convergence_revision5_cni_definition_membership import (
    DATASET,
    NO,
    POINTER,
    ROLES,
    TASKS,
    YES,
)
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest

# Established source paths. These give a retrospective diagnostic against
# reviewed clauses within the actual citations. No uncited span is added.
SUBSTANCE = {
    (1, 1): ((9, 11), (9, 14), (9, 17), (9, 19), (9, 20)),
    (3, 2): ((10, 11), (10, 12)),
    (6, 1): ((18, 21),),
    (6, 2): ((5, 6, 7),),
}


def review_paths(case, kind):
    if kind == "carrier":
        return [case["source_review"][kind]["evidence"]]
    return SUBSTANCE.get(tuple(case["position"]), ())


def decode_from_witness(case, kind, output, cited):
    present = set(cited)
    proof = next((sorted(path) for path in review_paths(case, kind) if set(path) <= present), None)
    if proof is None:
        return output, False
    expected = case["source_review"][kind]["answer"]
    assert expected in (YES, NO) and proof
    return {"answer": expected, "evidence": proof}, True


def run():
    receipt = read(POINTER)
    stage = ROOT / receipt["artifact_root"]
    terminal = read(stage / "terminal.json")
    binding = read(stage / "binding.json")
    assert receipt["status"] == terminal["status"] == "settled_ContractNLI_membership_TRAIN"
    assert stage.name == digest(binding) and receipt["terminal_sha256"] == sha(
        stage / "terminal.json"
    )
    assert all(sha(stage / "source_snapshot" / name) == h for name, h in binding["sources"].items())
    assert terminal["predictions_sha256"] == sha(stage / "predictions.json")
    cases, predictions = (read(stage / name) for name in ("case_material.json", "predictions.json"))
    assert digest(cases) == binding["ordered_cohort_sha256"]
    expected_reads = terminal["new_executor_requests"]
    score_path = ROOT / binding["grade_path"]
    assert "train" in score_path.parts and sha(score_path) == binding["grade_sha256"]
    audit = {role: {kind: Counter() for kind in TASKS} for role in ROLES}
    projected = {}
    ids = set()
    with sqlite3.connect(LEDGER.as_uri() + "?mode=ro", uri=True) as db:
        for case, pair in zip(cases, predictions, strict=True):
            projected[case["source"]] = {}
            for role, row in pair.items():
                identity = row["physical_call_id"]
                assert identity not in ids
                ids.add(identity)
                source, status, obj = db.execute(
                    "select source,status,result from calls where id=?", (identity,)
                ).fetchone()
                assert source == case["source"] and status == "completed"
                raw = json.loads(obj)
                assert raw["finish_reason"] == "stop"
                cites = json.loads(raw["content"])["evidence"]
                projected[source][role] = {}
                for kind, output in row["predictions"].items():
                    answer, observed = decode_from_witness(case, kind, output, cites[kind])
                    stats = audit[role][kind]
                    stats["sufficient_witness_already_cited"] += observed
                    stats["wrong_answer_with_sufficient_existing_witness"] += (
                        observed and answer["answer"] != output["answer"]
                    )
                    projected[source][role][kind] = answer
    assert len(ids) == expected_reads
    path = stage / "retrospective_cited_witnesses"
    immutable_json(path / "predictions.json", projected)
    annotations = read(score_path)
    for case in cases:
        key = case["source"]
        for role, outputs in projected[key].items():
            for kind, data in outputs.items():
                score = grade_view(
                    DATASET,
                    case["views"][kind],
                    annotations[key][TASKS[kind]],
                    data["answer"],
                    data["evidence"],
                )
                audit[role][kind]["native_correct_after_reviewed_replay"] += int(score["grade"])
    report = {
        "matched_terminal_sha256": receipt["terminal_sha256"],
        "runner_sha256": sha(Path(__file__)),
        "predictions_sha256": sha(path / "predictions.json"),
        "all_cases_from_original_TRAIN": True,
        "reused_physical_responses": len(ids),
        "physical_requests_new": 0,
        "retrospective_independent_source_review": True,
        "joint_membership_audit": {
            arm: {k: dict(v) for k, v in group.items()} for arm, group in audit.items()
        },
    }
    immutable_json(path / "terminal.json", report)
    print(json.dumps(report, sort_keys=True), flush=True)


if __name__ == "__main__":
    run()
