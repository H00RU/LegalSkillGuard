"""Trace the survival hypothesis through the archived native-positive CNI proposals."""

import re
import sqlite3
from collections import Counter
from pathlib import Path

from experiments.convergence_formal_train_fit import pointer as fit
from experiments.convergence_pilot_b0 import LEDGER, ROOT, read, sha
from experiments.convergence_revision5_cni_survival_scope import (
    ARMS,
    DATASET,
    TASK,
    TRAIN,
    YES,
    archive,
    bound_proofs,
    bound_stage,
    normalize,
    replay,
    response,
    verify_prediction,
    verify_request,
)
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest

EXECUTION_REFERENCE = re.compile(r"\bsurvive the execution and delivery\b", re.I)


def verdict(native):
    return {"answer": native["answer"], "evidence": native["evidence_sentence_ids"]}


def candidate_trace(views, baseline, labels):
    clauses = {key: normalize(view) for key, view in views.items()}
    proofs = {key: bound_proofs(spans) for key, spans in clauses.items()}
    stages, proposals, seen = {}, [], set()
    with sqlite3.connect(LEDGER.as_uri() + "?mode=ro", uri=True) as db:
        assert not db.execute("select 1 from calls where status='reserved'").fetchone()
        for batch in (3, 4, 5):
            stage, _, end = bound_stage(fit(batch))
            stages[str(batch)] = sha(stage / "terminal.json")
            matched = read(stage / "matched_decisions.json")
            assert digest(matched) == end["matched_decisions_sha256"]
            for arm in ARMS:
                decision = matched["teacher"][arm][DATASET]
                if decision["native_utility_delta"] <= 0:
                    continue
                path = stage / "candidates" / arm / DATASET
                assert read(path / "decision.json") == decision
                measured = read(path / "measurements.json")["predictions"]
                inherited = read(path / "prior_TRAIN_regression.json")
                assert digest(measured) == decision["predictions_sha256"]
                assert digest(inherited) == decision["earlier_TRAIN_regression"]["evidence_sha256"]
                counts = Counter()
                for key, after in (inherited["candidate"] | measured).items():
                    before = inherited["before"].get(key)
                    for row in (before, after):
                        if row is None:
                            continue
                        ident = verify_prediction(db, key, row)
                        if ident not in seen:
                            _, wire = response(db, key, ident)
                            verify_request(wire, {TASK: views[key]})
                            seen.add(ident)
                    old = (
                        verdict(before["native"][TASK])
                        if before is not None
                        else baseline[arm][key]
                    )
                    new = verdict(after["native"][TASK])
                    expected = labels[key][TASK]
                    corrected_before = replay(old, proofs[key], True)
                    corrected_after = replay(new, proofs[key], True)
                    counts["paired_mothers"] += 1
                    counts["changed_after_shared_source_control"] += (
                        corrected_before["answer"] != corrected_after["answer"]
                    )
                    counts["any_output_changed_after_source_control"] += (
                        corrected_before != corrected_after
                    )
                    if old["answer"] == new["answer"]:
                        continue
                    counts["native_label_changed"] += 1
                    counts["native_improved"] += new["answer"] == expected["answer"]
                    counts["native_regressed"] += old["answer"] == expected["answer"]
                    counts["changed_with_strict_source_proof"] += bool(proofs[key])
                    if new["answer"] == YES and new["answer"] == expected["answer"]:
                        counts["native_entailment_improvements_with_execution_reference"] += any(
                            EXECUTION_REFERENCE.search(clauses[key][i])
                            for i in expected["evidence"]
                        )
                proposals.append(
                    {
                        "fit_batch": batch,
                        "arm": arm,
                        "original_library_decision": decision["selected"],
                        "counts": dict(counts),
                    }
                )
    return stages, proposals, len(seen)


def run():
    receipt = read(TRAIN)
    stage = ROOT / receipt["artifact_root"]
    binding = read(stage / "binding.json")
    assert (
        digest(binding) == stage.name and sha(stage / "terminal.json") == receipt["terminal_sha256"]
    )
    runner = Path(__file__).with_name("convergence_revision5_cni_survival_scope.py")
    assert sha(runner) == binding["runner_sha256"]
    views, baseline, grade, checksum, *_ = archive("train")
    assert digest(views) == binding["views_sha256"] and checksum == binding["native_grade_sha256"]
    stages, proposals, physical = candidate_trace(views, baseline, read(grade))
    total = Counter()
    for proposal in proposals:
        total.update(proposal["counts"])
    report = {
        "status": "settled_CNI_survival_candidate_TRAIN_scope_replay",
        "paired_proposals": len(proposals),
        "totals": dict(total),
        "candidate_archive_physical_responses_verified": physical,
        "proposal_coordinates": proposals,
        "original_fit_terminal_sha256": stages,
        "source_control_TRAIN_terminal_sha256": receipt["terminal_sha256"],
        "runner_sha256": sha(Path(__file__)),
        "original_selection_preserved": True,
        "new_requests": 0,
    }
    out = stage / "archived_candidate_scope"
    immutable_json(out / "terminal.json", report)
    import json

    print(json.dumps(report, sort_keys=True), flush=True)


if __name__ == "__main__":
    run()
