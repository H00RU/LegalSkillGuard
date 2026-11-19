"""Replay the B5 candidate retention gate with common ContractNLI scope checks."""

import argparse
import re
import sqlite3
from collections import Counter
from pathlib import Path

from experiments.convergence_formal_train_fit import ORDINARY
from experiments.convergence_revision5_cni_disclosure_objects import source_rule
from experiments.convergence_revision5_cni_linked_evidence import span_inventory
from experiments.convergence_revision5_cni_nonsolicitation import project, provision
from experiments.convergence_revision5_cni_partial_wire import (
    ARMS,
    BOOTSTRAP,
    DATASET,
    FIRST,
    LEDGER,
    ROOT,
    TrainingJournal,
    bound_stage,
    brief,
    checked_result,
    dev_pointer,
    digest,
    fit_pointer,
    load_roster,
    read,
    score,
    sha,
    verify,
)
from experiments.convergence_pilot_b0 import BASE
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.rr.checkpoint import immutable_json


AGREEMENT = "nda-10"
SOLICITATION = "nda-18"
PUBLICITY = re.compile(
    r"\b(?:existence|publicity|advertis\w*|press releases?|news releases?|"
    r"(?:public(?:ly)?|press|media)\s+(?:notice|mention|announc\w*|communicat\w*|"
    r"disclos\w*|statements?|discussions?)|announc\w*)\b",
    re.I,
)
AGREEMENT_EVENT = re.compile(
    r"\b(?:(?:fact|whether|terms|content|nature|status|details?)\b.{0,125}\b"
    r"(?:agreement|negotiat\w*|discussions?|transaction|arrangement)|"
    r"(?:discuss|discussing|disclose|disclosing|reveal|revealing|publish|publishing)\s+"
    r"(?:to\s+\w+\s+)?(?:(?:a|the|this|any|such)\s+)?"
    r"(?:agreement|negotiat\w*|discussions?|transaction|arrangement))\b",
    re.I,
)
POSSIBLE_RESTRICTION = re.compile(
    r"\b(?:disclos\w*|confidential\w*|non.public|communicat\w*|reveal\w*|inform\w*|"
    r"share\w*|neither party|shall not|not to|shall keep|advertis\w*)\b",
    re.I,
)
AGREEMENT_CONFIDENTIAL = re.compile(
    r"\b(?:this|the) agreement\b[^.;]{0,230}\b(?:shall|must|will) be (?:kept |held )?confidential\b|"
    r"\b(?:keep|hold) (?:this|the) agreement(?: itself)? confidential\b",
    re.I,
)
ROOT_RUN = BASE / "revision5_CNI_retention_controls_20261119"
TABLE = (
    ROOT / "reports/legal_skill_convergence_20261117/paper/tables/"
    "REVISION5_CNI_RETENTION_CONTROLS_20261119.json"
)
MODES = ("archived", "prefix", "agreement", "joint", "guarded_agreement", "guarded_joint")


def absence_applies(view, *, protect_agreement_itself=False):
    text = " ".join(view["public"]["source_text"].split())
    if PUBLICITY.search(text) or (protect_agreement_itself and AGREEMENT_CONFIDENTIAL.search(text)):
        return False
    return not any(
        POSSIBLE_RESTRICTION.search(text[max(0, m.start() - 175) : m.end() + 175])
        for m in AGREEMENT_EVENT.finditer(text)
    )


def case_views(source):
    return {view["id"]: view for view in source["views"]}


def controls(source, native, *, protect_agreement_itself=False):
    views = case_views(source)
    adjusted = native.copy()
    if absence_applies(views[AGREEMENT], protect_agreement_itself=protect_agreement_itself):
        adjusted[AGREEMENT] = {
            **native[AGREEMENT], "handled": True, "answer": "NotMentioned",
            "evidence_sentence_ids": [], "reason": None,
        }
    linked = project(provision(views[SOLICITATION]), native[SOLICITATION], use_links=True)
    joint = adjusted.copy()
    if linked["answer"] is not None:
        joint[SOLICITATION] = {**native[SOLICITATION], **linked, "handled": True, "reason": None}
    return adjusted, joint


def archive_context():
    checkpoint = ROOT / read(BOOTSTRAP)["artifact_root"]
    study = read(checkpoint / "binding.json")
    assert checkpoint.name == digest(study)
    roster = load_roster(study)
    return checkpoint, study, roster


def train(db, checkpoint, study, roster):
    stage, _, terminal = bound_stage(fit_pointer(5))
    matched = read(stage / "matched_decisions.json")
    assert digest(matched) == terminal["matched_decisions_sha256"]
    decision = matched["teacher"][ORDINARY][DATASET]
    fold = stage / "candidates" / ORDINARY / DATASET
    earlier = read(fold / "prior_TRAIN_regression.json")
    current = read(fold / "measurements.json")["predictions"]
    assert digest(earlier) == decision["earlier_TRAIN_regression"]["evidence_sha256"]
    assert digest(current) == decision["predictions_sha256"]
    _, grade_binding, _ = bound_stage(FIRST)
    grade = grade_binding["native_grade_paths"][DATASET]
    assert "train" in Path(grade).parts and sha(ROOT / grade) == grade_binding["native_grade_sha256"][grade]
    annotations = read(ROOT / grade)
    numbered = {
        (batch, position): s for batch, rows in enumerate(roster, 1)
        for position, s in enumerate(x for x in rows if x["dataset"] == DATASET)
    }
    assert len(numbered) == 24 and all(s["project_split"] == "train" for s in numbered.values())
    prior_scope_anchors = [
        (position, source_rule(position, span_inventory(case_views(source)[AGREEMENT]))["family"])
        for position, source in numbered.items()
        if absence_applies(case_views(source)[AGREEMENT])
    ]
    covered = [
        annotations[numbered[position]["key"]][AGREEMENT]["answer"] for position, _ in prior_scope_anchors
    ]
    assert set(kind for _, kind in prior_scope_anchors) == {"unreviewed"}

    journal = TrainingJournal(checkpoint, study, roster)
    observed = journal._observations(ORDINARY, 5)
    comparisons = {}
    known = {}
    for scope in ("earlier", "current"):
        rows = {side: {mode: Counter() for mode in MODES} for side in ("incumbent", "proposal")}
        target_profile = {task: Counter() for task in (AGREEMENT, SOLICITATION)}
        cutoff_credit = Counter()
        for (batch, _), source in numbered.items():
            key = source["key"]
            if scope == "earlier" and batch < 5:
                bank = {"incumbent": earlier["before"][key], "proposal": earlier["candidate"][key]}
            elif scope == "current" and batch == 5:
                path = journal.directory(ORDINARY, 5) / "predictions" / (digest(key) + ".json")
                saved = read(path)
                assert digest(saved) == observed["predictions"][key]
                bank = {"incumbent": saved["result"], "proposal": current[key]}
            else:
                continue
            for side, entry in bank.items():
                _, prefix = checked_result(db, source, entry, known)
                replayed = (*controls(source, prefix), *controls(source, prefix, protect_agreement_itself=True))
                for mode, native in zip(MODES, (entry["native"], prefix, *replayed), strict=True):
                    measured = score(source, annotations[key], native)
                    rows[side][mode].update(measured)
                    if side == "proposal" and prefix != entry["native"]:
                        cutoff_credit[mode] += measured["tasks"] - measured["correct"]
                    for task in target_profile:
                        target_profile[task][side + "_" + mode] += native[task]["answer"] == annotations[key][task]["answer"]
        comparisons[scope] = {
            "native_metrics": {s: {m: brief(v) for m, v in totals.items()} for s, totals in rows.items()},
            "target_correct_counts": {task: dict(v) for task, v in target_profile.items()},
            "proposal_upper_bound_with_perfect_cutoff_response": {
                mode: rows["proposal"][mode]["correct"] + credit for mode, credit in cutoff_credit.items()
            },
        }

    selections = {}
    for mode in MODES:
        differences = {
            scope: row["native_metrics"]["proposal"][mode]["correct"] -
            row["native_metrics"]["incumbent"][mode]["correct"]
            for scope, row in comparisons.items()
        }
        selects = differences["earlier"] >= 0 and differences["current"] > 0
        selections[mode] = {"deltas_in_correct_labels": differences, "candidate_selected": selects}
    assert selections["archived"]["candidate_selected"] == (decision["selected"] == "candidate")
    return {
        "archived_physical_responses_verified": len(known),
        "comparison": comparisons,
        "selection": selections,
        "training_support": {"absence_covered": len(covered), "matching_labels": covered.count("NotMentioned"),
                             "cohort": len(numbered)},
        "fit_terminal_sha256": sha(stage / "terminal.json"),
        "native_grade_sha256": sha(ROOT / grade),
    }


def dev(db, checkpoint, study):
    stage, binding, terminal = bound_stage(dev_pointer(8))
    assert binding["checkpoint_binding_sha256"] == digest(study)
    directory = ROOT / binding["b0_dev_data_root"]
    roster = read(directory / "public_DEV_sources.json")
    assert digest(roster) == read(directory / "binding.json")["DEV_public_sha256"] == study["DEV_public_sha256"]
    cni = [source for source in roster if source["dataset"] == DATASET]
    assert len(cni) == 16 and all(s["project_split"] == "dev" for s in cni)
    grade = study["grading_paths"][DATASET]
    assert "dev" in Path(grade).parts and sha(ROOT / grade) == study["grading_file_sha256"][grade]
    annotations = read(ROOT / grade)
    coverage = {}
    for policy, guarded in (("agreement", False), ("guarded_agreement", True)):
        covered = [s for s in cni if absence_applies(case_views(s)[AGREEMENT], protect_agreement_itself=guarded)]
        coverage[policy] = {"coverage": len(covered), "matching_labels": sum(
            annotations[s["key"]][AGREEMENT]["answer"] == "NotMentioned" for s in covered
        )}

    known, by_arm = {}, {}
    for arm in ARMS:
        cell = checkpoint / "dev" / "B8" / arm
        seal = verify(read(cell / "prediction_seal.json"), "prediction_seal_sha256")
        scores = verify(read(cell / "scores.json"), "cell_sha256")
        assert scores["partition"] == "dev" and scores["cell_sha256"] == terminal["cell_sha256"][arm]
        assert seal["prediction_seal_sha256"] == scores["prediction_seal_sha256"]
        assert seal["task_sha256"] == digest(read(cell / "task.json"))
        aggregate = {m: Counter() for m in MODES[1:]}
        native_scope = {m: [] for m in aggregate}
        for source in cni:
            key = source["key"]
            saved = read(cell / "predictions" / (digest(key) + ".json"))
            assert seal["predictions_sha256"][key] == digest(saved) and saved["source"] == key
            assert saved["library_sha256"] == scores["libraries"][DATASET]
            _, prefix = checked_result(db, source, saved["result"], known, dev=True)
            assert prefix == saved["result"]["native"]
            replayed = (*controls(source, prefix), *controls(source, prefix, protect_agreement_itself=True))
            for mode, native in zip(aggregate, (prefix, *replayed), strict=True):
                aggregate[mode].update(score(source, annotations[key], native))
                native_scope[mode].append({
                    "source": key,
                    "view": AGREEMENT,
                    "grade": float(native[AGREEMENT]["answer"] == annotations[key][AGREEMENT]["answer"]),
                })
        by_arm[arm] = {
            "metrics": {m: brief(a) for m, a in aggregate.items()},
            "agreement_correct": {m: int(sum(r["grade"] for r in a)) for m, a in native_scope.items()},
            "agreement_delta": {mode: paired_source_effect(native_scope["prefix"], native_scope[mode])
                                for mode in ("agreement", "guarded_agreement")},
        }
    return {
        "archived_physical_responses_verified": len(known),
        "DEV_terminal_sha256": sha(stage / "terminal.json"),
        "native_grade_sha256": sha(ROOT / grade),
        "coverage": coverage,
        "by_arm": by_arm,
    }


def run(partition):
    checkpoint, study, roster = archive_context()
    files = (Path(__file__).resolve(), *(
        ROOT / "experiments" / (name + ".py") for name in (
            "convergence_revision5_cni_partial_wire",
            "convergence_revision5_cni_nonsolicitation",
            "convergence_revision5_cni_disclosure_objects",
        )
    ))
    binding = {
        "source_hashes": {str(p.relative_to(ROOT)): sha(p) for p in files},
        "TRAIN_checkpoint_sha256": digest(study),
        "design": "common complete-record recovery, agreement-event coverage, and existing solicitation check",
    }
    out = ROOT_RUN / digest(binding)
    stage = out / "TRAIN.json"
    with sqlite3.connect(LEDGER.as_uri() + "?mode=ro", uri=True) as db:
        ledger = dict(db.execute("select status,count(*) from calls group by status"))
        assert not ledger.get("reserved")
        if partition == "train":
            immutable_json(out / "binding.json", binding)
            evidence = train(db, checkpoint, study, roster)
            immutable_json(stage, evidence)
            print(out)
            print(evidence["selection"], evidence["training_support"])
        else:
            assert read(out / "binding.json") == binding
            training = read(stage)
            assert training["training_support"]["absence_covered"] == training["training_support"]["matching_labels"]
            evidence = dev(db, checkpoint, study)
            summary = {
                "status": "settled_CNI_B5_common_retention_controls",
                "binding": binding,
                "guarded_policy_reviewed_on_same_DEV": True,
                "TRAIN": training,
                "TRAIN_report_sha256": sha(stage),
                "DEV": evidence,
                "new_requests": 0,
                "continuous_ledger": ledger,
                "TEST_opened": False,
            }
            immutable_json(TABLE, summary)
            print(evidence)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("partition", choices=("train", "dev"))
    run(parser.parse_args().partition)
