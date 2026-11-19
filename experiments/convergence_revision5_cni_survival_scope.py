"""Replay ContractNLI survival using the agreement, trigger, and preserved duty."""

import argparse
import json
import re
import sqlite3
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean

from experiments.convergence_formal_b1_observe import POINTER as FIRST
from experiments.convergence_formal_curves import pointer as dev_pointer
from experiments.convergence_formal_train_observe import pointer as observe_pointer
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from experiments.convergence_revision5_cni_definition_binding import (
    ARMS,
    BOOTSTRAP,
    DATASET,
    load_roster,
    spans_for,
    verify_request,
)
from experiments.convergence_revision5_cni_nonsolicitation import bound_stage
from experiments.convergence_revision5_cni_oral_dev import verify_wire
from experiments.convergence_revision5_maud_sibling_cue import response, verify_prediction
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.paired_interfaces.convergence_journal import TrainingJournal
from legal_skill_guard.paired_interfaces.formal_evaluation import verify
from legal_skill_guard.paired_interfaces.shared_semantics import (
    SourceCase,
    Theory,
    allowed_relation,
    source_variant,
)
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest

TASK = "nda-19"
YES = "Entailment"
HOME = BASE / "revision5_CNI_survival_scope_20261119"
TRAIN = HANDOFF / "revision5_CNI_survival_scope_TRAIN_current.json"
PREVIEW = HANDOFF / "revision5_CNI_survival_scope_preflight_20261119.json"

EVENT = r"(?:terminat(?:ion|ed)|expir(?:ation|y)|rescission|(?:end|term))"
SAME_AGREEMENT = r"of (?:this|the) (?:Non[- ]Disclosure |Confidentiality )?Agreement\b"
TIMING = re.compile(rf"\b{EVENT}\s+{SAME_AGREEMENT}", re.I)
DUTY = re.compile(
    r"\b(?:obligations?|dut(?:y|ies)|terms|provisions|covenants?|restrictions?|confidentiality)\b",
    re.I,
)
PERSIST = re.compile(r"\b(?:shall\s+)?survive(?:s|d)?\b|\b(?:shall|will) remain effective\b", re.I)
SIGNING = re.compile(r"^\s*(?:the )?(?:execution|signing|delivery)\b", re.I)
NEGATION = re.compile(r"\b(?:no|not|never|shall cease to)\b[^,;]{0,25}$", re.I)
FORCE_ONLY = re.compile(r"\bpurported termination\b", re.I)
AFTER_PERSIST = re.compile(r"^\s*(?:after|following|beyond)\b", re.I)
RELIEF = re.compile(
    r"\btermination of this (?:Confidentiality )?Agreement shall not relieve\b.{0,200}\bobligations?\b",
    re.I,
)
AFTER = re.compile(
    r"\b(?:following|notwithstanding) (?:any )?(?:termination(?: or expiration)?|expiration) of this "
    r"(?:Non[- ]Disclosure |Confidentiality )?Agreement\b.{0,200}"
    r"\b(?:confidentiality shall still be maintained|(?:will|shall) hold in strict confidence)\b",
    re.I,
)
PRIOR_TERM = re.compile(
    r"^This Agreement shall become effective from the date hereof and continue in force for a period of "
    r"(?:[a-z-]+\s+)?(?:\(\d+\)\s+)?(?:year|month)s?\.",
    re.I,
)
SUCH_TERMINATION = re.compile(r"\bshall survive any such termination\b", re.I)
END_OF_CONTRACT = re.compile(
    r"^\d+\. Except as otherwise provided in paragraph (?P<ref>\d+) above, this Agreement and all obligations "
    r"of the parties hereunder, notwithstanding anything to the contrary that may be contained herein, "
    r"shall terminate (?P<amount>[a-z-]+ \((?P<number>\d+)\))\s+(?P<unit>years?|months?) "
    r"from the date of this Agreement\.",
    re.I,
)
EXCEPTION_TERM = re.compile(
    r"^(?P<section>\d+)\. .{0,45}?agrees that,? for a period of "
    r"(?P<amount>[a-z-]+ \((?P<number>\d+)\))\s+(?P<unit>years?|months?) from the date of this Agreement,",
    re.I,
)
OPERATIVE_CONTINUATION = re.compile(
    r"^\([a-z]\)\s+(?:effect|solicit|seek|acquire|buy|take)\b", re.I
)


@dataclass(frozen=True)
class ScopeProof:
    spans: tuple[int, ...]
    kind: str


def months(match):
    unit = match["unit"].lower()
    return int(match["number"]) * (12 if unit.startswith("year") else 1)


def terminal_exception(clauses):
    """Find a unique same-date exception whose operative text is present."""
    proofs = []
    for i, span in enumerate(clauses):
        if not (end := END_OF_CONTRACT.match(span)):
            continue
        targets = [
            (j, term)
            for j, other in enumerate(clauses[:i])
            if (term := EXCEPTION_TERM.match(other)) and term["section"] == end["ref"]
        ]
        if len(targets) != 1:
            continue
        ((j, exception),) = targets
        if not OPERATIVE_CONTINUATION.search(clauses[j + 1]):
            continue
        proofs.append(
            {
                "evidence": (j, j + 1, i),
                "exception_months": months(exception),
                "agreement_months": months(end),
                "replacement": exception["amount"],
            }
        )
    return proofs


def bound_proofs(clauses):
    """Identify the agreement's termination, its own duty, and the governing continuation."""
    found = []
    for i, text in enumerate(clauses):
        if not DUTY.search(text) or FORCE_ONLY.search(text):
            continue
        if RELIEF.search(text) or AFTER.search(text):
            found.append(ScopeProof((i,), "express_after_termination"))
        for marker in PERSIST.finditer(text):
            prefix = text[: marker.start()]
            if not DUTY.search(prefix) or NEGATION.search(prefix):
                continue
            clause = text[marker.end() :].split(";", 1)[0]
            if marker[0].lower().endswith("effective") and not AFTER_PERSIST.match(clause):
                continue
            if not SIGNING.match(clause) and TIMING.search(clause):
                found.append(ScopeProof((i,), "same_agreement_trigger"))
                break
        if i and SUCH_TERMINATION.search(text) and PRIOR_TERM.search(clauses[i - 1]):
            found.append(ScopeProof((i - 1, i), "same_term_reference"))
    found.extend(
        ScopeProof(tuple(row["evidence"]), "longer_explicit_exception")
        for row in terminal_exception(clauses)
        if row["exception_months"] > row["agreement_months"]
    )
    return sorted(set(found), key=lambda item: (len(item.spans), item.spans, item.kind))


def proposed_label(values, _law):
    """Evaluate only the named §8 duration comparison inside the termination clause."""
    return values["exception_months"] > values["agreement_months"]


def counterfactual(view, key, clauses):
    """Rebind the same published clause after substituting its stated length."""
    rows = terminal_exception(clauses)
    assert len(rows) == 1
    (one,) = rows
    part = one["evidence"][0]
    text = view["public"]["source_text"]
    lower, upper = view["public"]["sentence_spans"][part]
    fragment = one["replacement"]
    assert text[lower:upper].count(fragment) == 1
    start = text.index(fragment, lower, upper)
    original = one["exception_months"]
    limit = one["agreement_months"]
    # These are complete counterfactual source strings, not new benchmark cases.
    render = {6: "six (6)", 12: "twelve (12)", 18: "eighteen (18)"}
    assert limit == 12 and original == 18
    law = digest({"rule": "express exception and a common date origin"})
    theory = Theory(
        {law: [{}]},
        {key: [{}]},
        proposed_label,
        sha(Path(__file__)),
        provenance=({"kind": "explicit_source", "evidence_sha256": digest(view)},),
        allowed_edits=frozenset({"exception_months"}),
    )
    first = SourceCase(
        key + ":base",
        key,
        law,
        {"document": text},
        {"agreement_months": limit, "exception_months": original},
        spans={"exception_months": ("document", start, start + len(fragment))},
    )
    cases = [first]
    for length in (12, 6):
        created = source_variant(
            first, theory, {"exception_months": length}, {"exception_months": render.__getitem__}
        )
        assert created["status"] == "REALIZABLE"
        changed = created["case"]
        assert (
            changed.public["document"]
            == text[:start] + render[length] + text[start + len(fragment) :]
        )
        replayed = clauses.copy()
        replayed[part] = replayed[part].replace(fragment, render[length], 1)
        (check,) = terminal_exception(replayed)
        assert check["exception_months"] == length and check["agreement_months"] == limit
        cases.append(changed)
    expected = [True, False, False]
    for mode in ("shared", "independent_completions", "single_interpretation"):
        (signature,) = allowed_relation(theory, cases, mode=mode)["signatures"].values()
        assert signature == expected
    return {
        "source_edits": 2,
        "exception_months": [18, 12, 6],
        "main_term_months": 12,
        "signed_scope_component": expected,
        "one_signature_in_each_condition": True,
        "direct_duration_comparison_identical": True,
        "new_physical_reads": 0,
    }


def normalize(view):
    return [" ".join(s.split()) for s in spans_for(view)]


def archive(partition):
    root = ROOT / read(BOOTSTRAP)["artifact_root"]
    study = read(root / "binding.json")
    assert root.name == digest(study)
    roster = load_roster(study)
    journal = TrainingJournal(root, study, roster)
    data = {arm: {} for arm in ARMS}
    refs = {}
    if partition == "train":
        cohort = [row for rows in roster for row in rows if row["dataset"] == DATASET]
        for b, batch in enumerate(roster, 1):
            stage, conf, end = bound_stage(FIRST if b == 1 else observe_pointer(b))
            refs[str(b)] = sha(stage / "terminal.json")
            grade = conf["native_grade_paths"][DATASET]
            grade_hash = conf["native_grade_sha256"][grade]
            for arm in ARMS:
                registered = journal._observations(arm, b)
                assert registered["train_observation_sha256"] == end["observation_receipts"][arm]
                for source in (s for s in batch if s["dataset"] == DATASET):
                    key = source["key"]
                    saved = read(
                        journal.directory(arm, b) / "predictions" / (digest(key) + ".json")
                    )
                    assert (
                        digest(saved) == registered["predictions"][key] and saved["source"] == key
                    )
                    data[arm][key] = saved["result"]
    else:
        stage, conf, end = bound_stage(dev_pointer(8))
        refs["B8_DEV"] = sha(stage / "terminal.json")
        input_dir = ROOT / conf["b0_dev_data_root"]
        dev_sources = read(input_dir / "public_DEV_sources.json")
        assert digest(dev_sources) == read(input_dir / "binding.json")["DEV_public_sha256"]
        cohort = [s for s in dev_sources if s["dataset"] == DATASET]
        grade = study["grading_paths"][DATASET]
        grade_hash = study["grading_file_sha256"][grade]
        for arm in ARMS:
            directory = root / "dev" / "B8" / arm
            seal = verify(read(directory / "prediction_seal.json"), "prediction_seal_sha256")
            cell = verify(read(directory / "scores.json"), "cell_sha256")
            assert cell["partition"] == "dev" and cell["cell_sha256"] == end["cell_sha256"][arm]
            assert seal["prediction_seal_sha256"] == cell["prediction_seal_sha256"]
            assert seal["task_sha256"] == digest(read(directory / "task.json"))
            for source in cohort:
                key = source["key"]
                saved = read(directory / "predictions" / (digest(key) + ".json"))
                assert (
                    seal["predictions_sha256"][key] == digest(saved)
                    and saved["source"] == key
                    and saved["library_sha256"] == cell["libraries"][DATASET]
                )
                data[arm][key] = saved["result"]
    assert all(s["project_split"] == partition for s in cohort)
    assert len(cohort) == (24 if partition == "train" else 16)
    views = {s["key"]: next(view for view in s["views"] if view["id"] == TASK) for s in cohort}
    bank = {arm: {} for arm in ARMS}
    verified = set()
    with sqlite3.connect(LEDGER.as_uri() + "?mode=ro", uri=True) as db:
        ledger = dict(db.execute("select status, count(*) from calls group by status"))
        assert not ledger.get("reserved")
        for arm, records in data.items():
            for key, res in records.items():
                if partition == "train":
                    identity = verify_prediction(db, key, res)
                    if identity not in verified:
                        _, payload = response(db, key, identity)
                        verify_request(payload, {TASK: views[key]})
                        verified.add(identity)
                    native = res["native"][TASK]
                else:
                    old = verified.copy()
                    native = verify_wire(db, key, res, verified)[TASK]
                    for identity in verified - old:
                        (payload,) = db.execute(
                            "select result from calls where id=?", (identity,)
                        ).fetchone()
                        folder = Path(json.loads(payload)["artifact_directory"])
                        verify_request(read(folder / "request.json")["payload"], {TASK: views[key]})
                bank[arm][key] = {
                    "answer": native["answer"],
                    "evidence": native["evidence_sentence_ids"],
                }
    assert partition in Path(grade).parts and sha(ROOT / grade) == grade_hash
    return views, bank, ROOT / grade, grade_hash, refs, len(verified), ledger


def replay(native, proofs, linked):
    applicable = [row for row in proofs if linked or len(row.spans) == 1]
    if not applicable:
        return native
    if native["answer"] == YES and any(
        set(row.spans) <= set(native["evidence"]) for row in applicable
    ):
        return native
    return {"answer": YES, "evidence": list(applicable[0].spans)}


def score(views, forecasts, labels):
    summaries = {}
    for arm, bank in forecasts.items():
        cells = {}
        for key, entries in bank.items():
            for mode, prediction in entries.items():
                grade = grade_view(
                    DATASET,
                    views[key],
                    labels[key][TASK],
                    prediction["answer"],
                    prediction["evidence"],
                )
                cells.setdefault(mode, []).append(
                    {
                        "source": key,
                        "view": TASK,
                        "grade": grade["grade"],
                        "evidence": grade["evidence_f1"],
                    }
                )
        summaries[arm] = {
            mode: {
                "correct": int(sum(r["grade"] for r in rows)),
                "evidence_F1": mean(r["evidence"] for r in rows),
                "paired": paired_source_effect(cells["original"], rows)
                if mode != "original"
                else None,
            }
            for mode, rows in cells.items()
        }
    return summaries


def run(partition):
    views, bank, grade, checksum, archived, physical, ledger = archive(partition)
    clauses = {k: normalize(v) for k, v in views.items()}
    proofs = {k: bound_proofs(c) for k, c in clauses.items()}
    predictions = {
        arm: {
            k: {
                "original": pred,
                "same_clause": replay(pred, proofs[k], linked=False),
                "linked_source": replay(pred, proofs[k], linked=True),
            }
            for k, pred in by_key.items()
        }
        for arm, by_key in bank.items()
    }
    if partition == "train":
        preflight = read(PREVIEW)
        (key,) = (k for k, v in views.items() if digest(v) == preflight["source_view_sha256"])
        assert all(
            digest(clauses[key][int(i)]) == h
            for i, h in preflight["exception_and_expiry_span_sha256"].items()
        )
        edits = counterfactual(views[key], key, clauses[key])
        previous = None
    else:
        previous = read(TRAIN)
        stage = ROOT / previous["artifact_root"]
        assert previous["terminal_sha256"] == sha(stage / "terminal.json")
        assert read(stage / "binding.json")["runner_sha256"] == sha(Path(__file__))
    bind = {
        "partition": partition,
        "runner_sha256": sha(Path(__file__)),
        "views_sha256": digest(views),
        "native_grade_sha256": checksum,
        "original_terminal_sha256": archived,
        "TRAIN_terminal_sha256": previous["terminal_sha256"] if previous else None,
    }
    out = HOME / partition / digest(bind)
    immutable_json(out / "binding.json", bind)
    immutable_json(out / "predictions.json", predictions)
    immutable_json(
        out / "scope_proofs.json", {k: [asdict(p) for p in v] for k, v in proofs.items()}
    )
    labels = read(grade)
    agreement = Counter(labels[k][TASK]["answer"] for k, record in proofs.items() if record)
    report = {
        "partition": partition,
        "mothers": len(views),
        "original_responses_verified": physical,
        "ledger": ledger,
        "new_requests": 0,
        "source_supported_by_native_reference": dict(agreement),
        "forms": dict(Counter(p.kind for rows in proofs.values() for p in rows)),
        "evidence_sha256": sha(out / "scope_proofs.json"),
        "predictions_sha256": sha(out / "predictions.json"),
        "native": score(views, predictions, labels),
    }
    if partition == "train":
        report["source_bound_duration_edits"] = edits
        assert labels[key][TASK] == preflight["native_reference"]
    immutable_json(out / "terminal.json", report)
    if partition == "train":
        write_status(
            out, {"status": "TRAIN_settled", "terminal_sha256": sha(out / "terminal.json")}, TRAIN
        )
    print(
        json.dumps({"artifact_root": str(out.relative_to(ROOT)), **report}, sort_keys=True),
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("partition", choices=("train", "dev"))
    run(parser.parse_args().partition)
