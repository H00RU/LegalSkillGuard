"""Recheck measured MAUD adoptions with shared covenant and knowledge evidence."""

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sqlite3

from experiments.convergence_formal_curves import pointer as dev_pointer
from experiments.convergence_formal_train_fit import EXTERNAL_ARM, ORDINARY, pointer as fit_pointer
from experiments.convergence_formal_train_observe import pointer as observe_pointer
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha
from experiments.convergence_revision5_cni_nonsolicitation import bound_stage
from experiments.convergence_revision5_cni_retention_controls import archive_context
from experiments.convergence_revision5_maud_knowledge_residual import (
    ACTUAL, definitions, facts, INQUIRY, normalize, specialized, view_for, TARGET, EFFECT,
)
from experiments.convergence_revision5_maud_parent_definition_coverage import HOME as COVENANTS
from experiments.convergence_revision5_maud_section_scope import attachment_proof, policies
from experiments.convergence_revision5_maud_sibling_cue import (
    KNOWLEDGE, MAUD, NEGATIVE, ORDINARY_COVENANT, archived_case,
)
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.paired_interfaces.convergence_journal import TrainingJournal
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


HOME = BASE / "revision5_MAUD_adoption_scope_20261119"
TABLE = ROOT / "reports/legal_skill_convergence_20261117/paper/tables/REVISION5_MAUD_ADOPTION_SCOPE_20261119.json"
ADOPTIONS = ((6, ORDINARY), (6, EXTERNAL_ARM), (8, EXTERNAL_ARM))
KNOWN_FACTS = re.compile(r"\bthose facts that are known by\b", re.I)
RECEIVED_NOTICE = re.compile(
    r"\bshall include any facts, matters or circumstances set forth in "
    r"any written notice from any [a-z ]+? or any other material written notice received by such person\b", re.I,
)
IMPUTED = re.compile(
    r"\b(?:ought to|should have|would reasonably|deemed to|regardless of|whether or not|not received)\b", re.I,
)
MODES = ("archived", "shared_knowledge", "shared_scopes", "all_shared_scopes")


def received_notice(public):
    """Bind receipt to an already-known-facts definition on the same public excerpt."""
    anchors = definitions(normalize(public["source_text"]))
    if len(anchors) != 1:
        return False
    (anchor,) = anchors
    text = anchor["text"]
    if not (anchor["closed"] and "<omitted>" not in text and KNOWN_FACTS.search(text)
            and RECEIVED_NOTICE.search(text) and not (INQUIRY.search(text) or IMPUTED.search(text))):
        return False
    known = facts(anchor)
    return known.get(TARGET) == known.get(EFFECT) == "absent"


def replay(native, positive_notice, visible_knowledge, ordinary_scope, negative_scope):
    original = {key: row["answer"] for key, row in native.items()}
    knowledge = original.copy()
    if visible_knowledge is not None:
        knowledge[KNOWLEDGE] = visible_knowledge
    elif positive_notice:
        knowledge[KNOWLEDGE] = "Actual knowledge"
    covenants = {**knowledge, ORDINARY_COVENANT: ordinary_scope}
    full = {**covenants, NEGATIVE: policies(native[NEGATIVE], negative_scope)["attached_exceptions"]}
    return dict(zip(MODES, (original, knowledge, covenants, full), strict=True))


def ordinary_scope(record):
    prior = record["source_definition"]
    merged = bool(prior and prior["new_pandemic_deeming_witness"])
    return "Yes" if merged or record["literal_cues"][ORDINARY_COVENANT] else "No"


def prior_knowledge(partition):
    entry = read(HANDOFF / "run_state.json")["revision5_MAUD_knowledge_residual"]["partition_artifacts"][partition]
    stage = ROOT / entry["artifact_root"]
    assert sha(stage / "terminal.json") == entry["terminal_sha256"]
    terminal = read(stage / "terminal.json")
    binding = read(stage / "binding.json")
    assert digest(binding) == stage.name and binding["partition"] == partition
    assert sha(stage / "predictions.json") == terminal["predictions_sha256"]
    scope = read(stage / "proofs.json")
    assert digest(scope) == binding["proofs_sha256"]
    return binding, scope, read(stage / "predictions.json"), entry["terminal_sha256"]


def verify_views(payload, source):
    (user,) = (m["content"] for m in payload["messages"] if m["role"] == "user")
    document = json.loads(user)
    views = document.get("public", document)["native_views"]
    expected = {v["id"]: v["public"] for v in source["views"]}
    assert {v["id"]: v["public"] for v in views} == expected


def training():
    root, study, batches = archive_context()
    journal = TrainingJournal(root, study, batches)
    coverage = read(COVENANTS / "source_inventory.json")
    cov_receipt = read(COVENANTS / "terminal.json")
    assert sha(COVENANTS / "source_inventory.json") == cov_receipt["source_inventory_sha256"]
    bound, knowledge, _, knowledge_terminal = prior_knowledge("TRAIN")
    sources = {s["key"]: s for b in batches for s in b if s["dataset"] == MAUD}
    assert len(sources) == 24 and set(sources) == set(coverage) == set(knowledge)
    assert all(s["project_split"] == "train" for s in sources.values())
    assert digest(sources) == bound["source_sha256"]
    noticed = {key for key, source in sources.items() if received_notice(view_for(source)["public"])}
    notice_proof = specialized({TARGET: "absent", EFFECT: "absent", ACTUAL: True})
    assert notice_proof["direct_answer"] == "Actual knowledge" and notice_proof["fully_determined"]
    remaining = [row for key, row in knowledge.items()
                 if key not in noticed and not row["excerpt"]["fully_determined"]]
    known, reports, seals, grade = set(), [], {}, {}
    with sqlite3.connect(LEDGER.as_uri() + "?mode=ro", uri=True) as db:
        ledger = dict(db.execute("select status,count(*) from calls group by status"))
        assert not ledger.get("reserved")
        for batch, arm in ADOPTIONS:
            fit, setup, end = bound_stage(fit_pointer(batch))
            stage, conf, observed = bound_stage(observe_pointer(batch))
            assert setup["observations_terminal_sha256"] == sha(stage / "terminal.json")
            assert journal._observations(arm, batch)["train_observation_sha256"] == observed["observation_receipts"][arm]
            seals[str(batch)] = [sha(fit / "terminal.json"), sha(stage / "terminal.json")]
            path = conf["native_grade_paths"][MAUD]
            grade[path] = conf["native_grade_sha256"][path]
            candidate_path = fit / "candidates" / arm / MAUD / "measurements.json"
            adopted = journal.library(arm, batch)
            learned = adopted["programs" if arm == ORDINARY else "schema_proposals"][MAUD]
            assert learned == read(candidate_path)["candidate"]
            tested = []
            for source in (s for s in batches[batch - 1] if s["dataset"] == MAUD):
                key = source["key"]
                part = archived_case(db, journal, fit, end, batch, arm, source)
                (negative_view,) = (v["public"] for v in source["views"] if v["id"] == NEGATIVE)
                negative_scope = attachment_proof(negative_view)
                result = {}
                for side in ("incumbent", "candidate"):
                    row = part[side]
                    verify_views(row["payload"], source)
                    known.add(row["id"])
                    facts = knowledge[key]["excerpt"]
                    result[side] = replay(row["native"], key in noticed, facts["direct_answer"],
                                          ordinary_scope(coverage[key]), negative_scope)
                tested.append((key, result))
            reports.append((batch, arm, tested))
    (path, grade_hash), = grade.items()
    assert "train" in Path(path).parts and sha(ROOT / path) == grade_hash == bound["native_grade_sha256"]
    labels = read(ROOT / path)
    outcomes = []
    for batch, arm, tested in reports:
        outcomes_by_mode = {}
        for mode in MODES:
            before, after, deltas = 0, 0, Counter()
            for key, pair in tested:
                left, right = (pair[role][mode] for role in ("incumbent", "candidate"))
                for task in left:
                    expected = labels[key][task]["answer"]
                    before += left[task] == expected
                    after += right[task] == expected
                    if left[task] != right[task]:
                        deltas[task] += int(right[task] == expected) - int(left[task] == expected)
            outcomes_by_mode[mode] = {"incumbent_correct": before, "candidate_correct": after,
                                      "net_correct_labels": after - before, "native_delta_by_task": dict(deltas),
                                      "candidate_passes_positive_gain_gate": after > before}
        outcomes.append({"batch": batch, "arm": arm, "native_tasks": len(tested) * 3, "policies": outcomes_by_mode})
    return {
        "adoptions": outcomes, "physical_responses_verified": len(known),
        "archive_terminals_sha256": seals, "TRAIN_knowledge_terminal_sha256": knowledge_terminal,
        "TRAIN_covenant_scope_receipt_sha256": sha(COVENANTS / "terminal.json"),
        "written_notice_source_coverage": len(noticed),
        "written_notice_reference_matches": sum(labels[key][KNOWLEDGE]["answer"] == "Actual knowledge" for key in noticed),
        "written_notice_conditioned_consumer": notice_proof,
        "remaining_unresolved_excerpts": len(remaining),
        "remaining_open_or_omitted_excerpts": sum(row["excerpt_has_omission_or_open_tail"] for row in remaining),
        "remaining_fields": {mode: sum(row["excerpt"][mode + "_fields"] for row in remaining)
                             for mode in ("fixed", "synthesized")},
        "ordinary_source_check_reuses_retrospective_parent_scope": True,
        "native_grade_sha256": grade_hash, "continuous_ledger": ledger,
    }


def dev():
    bound, scope, old, receipt = prior_knowledge("DEV")
    stage, conf, end = bound_stage(dev_pointer(8))
    assert bound["original_native_terminals"] == {"B8_DEV": sha(stage / "terminal.json")}
    checkpoint = ROOT / conf["checkpoint_root"]
    cohort = ROOT / conf["b0_dev_data_root"]
    registered = read(cohort / "public_DEV_sources.json")
    assert digest(registered) == read(cohort / "binding.json")["DEV_public_sha256"]
    cases = {s["key"]: s for s in registered if s["dataset"] == MAUD}
    assert len(cases) == 16 and set(cases) == set(scope)
    assert digest(cases) == bound["source_sha256"] and all(s["project_split"] == "dev" for s in cases.values())
    study = read(checkpoint / "binding.json")
    g = study["grading_paths"][MAUD]
    assert "dev" in Path(g).parts and sha(ROOT / g) == bound["native_grade_sha256"]
    assert set(end["cell_sha256"]) >= set(old)
    duty = {key for key, s in cases.items() if received_notice(view_for(s)["public"])}
    labels = read(ROOT / g)
    metrics = {}
    for arm, bank in old.items():
        original, guarded = [], []
        for key, answer in bank.items():
            expected = labels[key][KNOWLEDGE]["answer"]
            score_before = answer["scoped_excerpt"]
            score_after = "Actual knowledge" if key in duty else score_before
            original.append({"source": key, "view": KNOWLEDGE, "grade": float(score_before == expected)})
            guarded.append({"source": key, "view": KNOWLEDGE, "grade": float(score_after == expected)})
        metrics[arm] = {"before": int(sum(v["grade"] for v in original)),
                        "after": int(sum(v["grade"] for v in guarded)),
                        "paired_effect": paired_source_effect(original, guarded)}
    return {"coverage": len(duty), "metrics": metrics,
            "prior_DEV_receipt_sha256": receipt, "DEV_grade_sha256": bound["native_grade_sha256"]}


def run(partition):
    binding = {"runner_sha256": sha(Path(__file__)),
               "training_scope": "actual accepted B6 and B8 MAUD programs",
               "comparison": "equal source checks on both candidate and entering programs"}
    folder = HOME / digest(binding)
    if partition == "train":
        result = training()
        immutable_json(folder / "binding.json", binding)
        immutable_json(folder / "TRAIN.json", result)
        print(result["adoptions"], flush=True)
    else:
        assert read(folder / "binding.json") == binding
        train = folder / "TRAIN.json"
        result = dev()
        immutable_json(TABLE, {"status": "settled_MAUD_adoption_under_shared_source_scopes",
                              "binding": binding, "TRAIN": read(train), "TRAIN_receipt_sha256": sha(train),
                              "DEV": result, "new_requests": 0, "TEST_opened": False})
        print(result, flush=True)


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("partition", choices=("train", "dev"))
    run(cli.parse_args().partition)
