"""Replay action-specific ContractNLI evidence outside the copying restriction."""

import argparse
from collections import Counter
from pathlib import Path
import re
import sqlite3
from statistics import mean

from experiments.convergence_formal_curves import pointer as dev_pointer
from experiments.convergence_formal_train_fit import pointer as fit_pointer
from experiments.convergence_formal_train_observe import pointer as observe_pointer
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha
from experiments.convergence_revision5_cni_linked_evidence import span_inventory
from experiments.convergence_revision5_cni_partial_wire import (
    ARMS, DATASET, FIRST, TrainingJournal, bound_stage, checked_result, verify,
)
from experiments.convergence_revision5_cni_retention_controls import archive_context
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest


TASK = "nda-11"
MODES = ("archived", "same_clause", "linked")
ACTION = re.compile(r"\b(?:reverse[\s-]+engineer\w*|de[\s-]?compil\w*|disassembl\w*|deconstruct\w*)\b", re.I)
ANALOGUE = re.compile(
    r"\b(?:ascertain\w*|determin\w*|discover(?:s|ed|ing)?|reconstruct\w*)\b"
    r".{0,95}\b(?:design|composition|manufactur\w*|source code|underlying ideas|formul\w*)\b", re.I,
)
OBJECT = re.compile(
    r"\b(?:samples?|prototypes?|products?|source code|algorithms?|software|programs?|"
    r"confidential information|materials?|equipment|components?|objects?)\b", re.I,
)
MODAL = re.compile(
    r"\b(?:(?:shall|must|will|may) not|agrees? not to|prohibited from|"
    r"no party.{0,45}?\bwill|neither party.{0,45}?\b(?:may|will|shall))\b", re.I,
)
PARTY = re.compile(r"\b(?:receiving part(?:y|ies)|recipient|disclosee|neither party|no party)\b", re.I)
SCOPE_BREAK = re.compile(r"[;:]|\b(?:but|however|provided that)\b", re.I)
GRANT = re.compile(r"\b(?:may|can|has the right to|permitted to)\b", re.I)
ITEM = re.compile(r"^\s*\(?(?P<letter>[a-z])\)\s*", re.I)
LIST_DUTY = re.compile(r"\b(?:undertakes?|agrees?|promises?)\b", re.I)
LIST_NEGATION = re.compile(r"\bnot to\b", re.I)
HOME = BASE / "revision5_CNI_reverse_engineering_20261119"
TABLE = ROOT / "reports/legal_skill_convergence_20261117/paper/tables/REVISION5_CNI_REVERSE_ENGINEERING_20261119.json"


def clean(text):
    return " ".join(text.split())


def source_view(source):
    return next(v for v in source["views"] if v["id"] == TASK)


def parent_index(spans, index):
    item = ITEM.match(spans[index])
    if item is None:
        return None
    offset = ord(item["letter"].lower()) - ord("a") + 1
    head = index - offset
    if head < 0:
        return None
    prefix = spans[head]
    if not (prefix.endswith(":") and PARTY.search(prefix) and LIST_DUTY.search(prefix)):
        return None
    preceding = [ITEM.match(s) for s in spans[head + 1:index]]
    if all(m is not None and ord(m["letter"].lower()) == ord("a") + p
           for p, m in enumerate(preceding)):
        return head
    return None


def source_proof(view):
    spans = [clean(x) for x in span_inventory(view)]
    same, linked = [], []
    for i, clause in enumerate(spans):
        for action in ACTION.finditer(clause):
            before = SCOPE_BREAK.split(clause[:action.start()])[-1]
            after = SCOPE_BREAK.split(clause[action.end():], maxsplit=1)[0]
            if not OBJECT.search(after):
                continue
            modal = MODAL.search(before)
            if modal and PARTY.search(before) and not GRANT.search(before[modal.end():]):
                same.append((i,))
            elif ((negative := LIST_NEGATION.search(before)) and not GRANT.search(before[negative.end():])
                  and (head := parent_index(spans, i)) is not None):
                linked.append((head, i))
    full = clean(view["public"]["source_text"])
    return {"same": list(dict.fromkeys(same)), "linked": list(dict.fromkeys(linked)),
            "no_engineering_cue": not (ACTION.search(full) or ANALOGUE.search(full))}


def apply(native, proof, *, linked=False):
    groups = proof["same"] + (proof["linked"] if linked else [])
    if groups:
        spans = sorted({i for group in groups for i in group})
        return {"answer": "Entailment", "evidence_sentence_ids": spans}
    if proof["no_engineering_cue"]:
        return {"answer": "NotMentioned", "evidence_sentence_ids": []}
    return native


def candidate_replay(db, known, train, original, proofs):
    out = []
    for batch in (3, 4, 5):
        stage, _, terminal = bound_stage(fit_pointer(batch))
        decisions = read(stage / "matched_decisions.json")
        assert digest(decisions) == terminal["matched_decisions_sha256"]
        for arm in ARMS:
            decision = decisions["teacher"][arm][DATASET]
            if decision["native_utility_delta"] <= 0:
                continue
            folder = stage / "candidates" / arm / DATASET
            active = read(folder / "measurements.json")["predictions"]
            previous = read(folder / "prior_TRAIN_regression.json")
            assert digest(active) == decision["predictions_sha256"]
            assert digest(previous) == decision["earlier_TRAIN_regression"]["evidence_sha256"]
            totals = Counter()
            for key, candidate in (previous["candidate"] | active).items():
                before = previous["before"].get(key, original[arm][key])
                pair = []
                for version in (before, candidate):
                    _, replayed = checked_result(db, train[key], version, known)
                    pair.append((version["native"][TASK], replayed[TASK]))
                (left, left_recovered), (right, right_recovered) = pair
                totals["mothers"] += 1
                totals["archived_label_changes"] += left["answer"] != right["answer"]
                totals["complete_record_label_changes"] += left_recovered["answer"] != right_recovered["answer"]
                a, b = (apply(row, proofs[key], linked=True) for row in (left_recovered, right_recovered))
                totals["after_common_rule_label_changes"] += a["answer"] != b["answer"]
            out.append({"batch": batch, "arm": arm, "original_selection": decision["selected"], "counts": dict(totals)})
    return out


def collect(checkpoint, study, roster, partition):
    original = {arm: {} for arm in ARMS}
    if partition == "train":
        journal = TrainingJournal(checkpoint, study, roster)
        sources = {s["key"]: s for cohort in roster for s in cohort if s["dataset"] == DATASET}
        archived = {}
        for batch, cohort in enumerate(roster, 1):
            stage, conf, terminal = bound_stage(FIRST if batch == 1 else observe_pointer(batch))
            archived[str(batch)] = sha(stage / "terminal.json")
            grade = conf["native_grade_paths"][DATASET]
            grade_hash = conf["native_grade_sha256"][grade]
            for arm in ARMS:
                registration = journal._observations(arm, batch)
                assert registration["train_observation_sha256"] == terminal["observation_receipts"][arm]
                for s in (s for s in cohort if s["dataset"] == DATASET):
                    key = s["key"]
                    saved = read(journal.directory(arm, batch) / "predictions" / (digest(key) + ".json"))
                    assert digest(saved) == registration["predictions"][key] and saved["source"] == key
                    original[arm][key] = saved["result"]
    else:
        stage, conf, terminal = bound_stage(dev_pointer(8))
        archived = {"B8_DEV": sha(stage / "terminal.json")}
        dev = ROOT / conf["b0_dev_data_root"]
        registered = read(dev / "public_DEV_sources.json")
        assert digest(registered) == read(dev / "binding.json")["DEV_public_sha256"]
        sources = {s["key"]: s for s in registered if s["dataset"] == DATASET}
        grade = study["grading_paths"][DATASET]
        grade_hash = study["grading_file_sha256"][grade]
        for arm in ARMS:
            folder = checkpoint / "dev" / "B8" / arm
            seal = verify(read(folder / "prediction_seal.json"), "prediction_seal_sha256")
            cell = verify(read(folder / "scores.json"), "cell_sha256")
            assert cell["partition"] == "dev" and cell["cell_sha256"] == terminal["cell_sha256"][arm]
            assert seal["task_sha256"] == digest(read(folder / "task.json"))
            assert cell["prediction_seal_sha256"] == seal["prediction_seal_sha256"]
            for key in sources:
                saved = read(folder / "predictions" / (digest(key) + ".json"))
                assert seal["predictions_sha256"][key] == digest(saved) and saved["source"] == key
                assert saved["library_sha256"] == cell["libraries"][DATASET]
                original[arm][key] = saved["result"]
    assert len(sources) == (24 if partition == "train" else 16)
    assert all(s["project_split"] == partition for s in sources.values())
    assert partition in Path(grade).parts and sha(ROOT / grade) == grade_hash
    return sources, original, ROOT / grade, archived


def grades(source, annotation, native, proof):
    results = (native, apply(native, proof), apply(native, proof, linked=True))
    return {mode: grade_view(DATASET, source_view(source), annotation, row["answer"], row["evidence_sentence_ids"])
            for mode, row in zip(MODES, results, strict=True)}


def analyze(partition):
    checkpoint, study, roster = archive_context()
    sources, original, grade, archived = collect(checkpoint, study, roster, partition)
    proofs = {key: source_proof(source_view(s)) for key, s in sources.items()}
    labels = read(grade)
    results = {}
    known = {}
    with sqlite3.connect(LEDGER.as_uri() + "?mode=ro", uri=True) as db:
        counts = dict(db.execute("select status,count(*) from calls group by status"))
        assert not counts.get("reserved")
        for arm in ARMS:
            bank = {mode: [] for mode in MODES}
            for key, source in sources.items():
                entry = original[arm][key]
                _, verified = checked_result(db, source, entry, known, dev=partition == "dev")
                assert verified == entry["native"]
                for mode, g in grades(source, labels[key][TASK], verified[TASK], proofs[key]).items():
                    bank[mode].append({"source": key, "view": TASK, "grade": g["grade"], "evidence": g["evidence_f1"]})
            results[arm] = {mode: {
                "correct": int(sum(r["grade"] for r in rows)),
                "evidence_F1": mean(r["evidence"] for r in rows),
                "paired_label_change": paired_source_effect(bank["archived"], rows),
                "paired_evidence_change": paired_source_effect(*(
                    [{**r, "grade": r["evidence"]} for r in entries] for entries in (bank["archived"], rows)
                )),
            } for mode, rows in bank.items()}
        native_count = len(known)
        proposals = candidate_replay(db, known, sources, original, proofs) if partition == "train" else []
    disagreements = []
    for key, proof in proofs.items():
        expected = labels[key][TASK]
        if proof["no_engineering_cue"] and expected["answer"] == "Entailment":
            view = source_view(sources[key])
            clauses = span_inventory(view)
            assert any(re.search(r"\bpublish, copy, or use\b", clauses[i], re.I) for i in expected["evidence"])
            disagreements.append({"source_public_sha256": digest(view["public"]),
                                  "construction": "publication_copying_or_use_without_engineering_action"})
    return {
        "partition": partition,
        "metrics": results,
        "native_mothers": len(sources),
        "same_clause_prohibitions": sum(bool(row["same"]) for row in proofs.values()),
        "linked_only_prohibitions": sum(bool(row["linked"]) and not row["same"] for row in proofs.values()),
        "no_cue_sources": sum(row["no_engineering_cue"] for row in proofs.values()),
        "native_reference_scope_disagreements": disagreements,
        "physical_observation_responses_verified": native_count,
        "physical_total_responses_verified": len(known),
        "archived_proposals": proposals,
        "observation_terminals_sha256": archived,
        "native_grade_sha256": sha(grade),
        "continuous_ledger": counts,
    }


def run(partition):
    binding = {"runner_sha256": sha(Path(__file__)), "scope": TASK,
               "link_scope": "ordered recipient obligations with a separate operative introducer",
               "linked_replay_uses_existing_DEV_feedback": True}
    folder = HOME / digest(binding)
    result = analyze(partition)
    if partition == "train":
        immutable_json(folder / "binding.json", binding)
        immutable_json(folder / "TRAIN.json", result)
    else:
        path = folder / "TRAIN.json"
        assert read(folder / "binding.json") == binding
        immutable_json(TABLE, {"status": "settled_CNI_reverse_engineering_scope",
                              "binding": binding, "TRAIN": read(path), "TRAIN_sha256": sha(path),
                              "DEV": result, "new_requests": 0, "TEST_opened": False})
    print({arm: {mode: (r["correct"], r["evidence_F1"]) for mode, r in modes.items()}
           for arm, modes in result["metrics"].items()}, flush=True)


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("partition", choices=("train", "dev"))
    run(cli.parse_args().partition)
