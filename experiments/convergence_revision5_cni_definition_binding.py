"""Bind named types and modes to an operative ContractNLI definition."""

import argparse
import json
import re
import sqlite3
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from statistics import mean

from experiments.convergence_formal_curves import pointer as dev_pointer
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from experiments.convergence_revision5_cni_definition_membership import (
    BOOTSTRAP,
    DATASET,
    EXTERNAL_ARM,
    NO,
    ORDINARY,
    ROLES,
    TASKS,
    YES,
    archive,
    layouts,
    load_roster,
    spans_for,
)
from experiments.convergence_revision5_cni_definition_membership import (
    POINTER as MEMBERSHIP,
)
from experiments.convergence_revision5_cni_nonsolicitation import bound_stage
from experiments.convergence_revision5_cni_oral_dev import verify_wire
from experiments.convergence_revision5_cni_oral_scope import (
    DEFINITION,
    DUTY_PROVIDER,
    PROVIDER,
    oral_proof,
)
from legal_skill_guard.paired_interfaces import residual
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.paired_interfaces.formal_evaluation import verify
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest

HOME = BASE / "revision5_CNI_definition_binding_20261119"
TRAIN = HANDOFF / "revision5_CNI_definition_binding_TRAIN_current.json"
ARMS = (ORDINARY, EXTERNAL_ARM)

CONTENT_TYPE = re.compile(
    r"\b(?:business plans?|business planning|acquisition plans?|expansion plans?|business development plans?"
    r"|financial (?:information|data|statements|documents|reports|records)|finances|marketing plans?"
    r"|customer (?:lists?|data|information)|employee (?:lists?|data|information)|personnel information"
    r"|human resources (?:data|information)|administration of (?:components of )?(?:the )?certification programs?|ethics cases"
    r"|commercial (?:information|data)|commercial, corporate|membership data|market opportunities|business affairs"
    r"|business records|business forecasts?|procurement requirements)\b",
    re.I,
)
COORDINATED_CONTENT = re.compile(
    r"\b(?:business|financial|contractual|marketing|commercial)\s*,"
    r"\s*(?:(?:and(?:/or)?|or)\s+)?(?:business|financial|contractual|marketing|commercial|technical)"
    r"(?:\s*,\s*(?:(?:and(?:/or)?|or)\s+)?(?:business|financial|contractual|marketing|commercial|technical))*"
    r"(?:\s+(?:and(?:/or)?|or)\s+(?:business|financial|contractual|marketing|commercial|technical))?"
    r"\s+(?:information|data)\b",
    re.I,
)
DEFINING = re.compile(
    r'\b(?:Confidential Information["”\x27]?\s+(?:shall also include|shall include|means?|shall mean)'
    r"|(?:the )?following are deemed Confidential Information)\b",
    re.I,
)
ENUM = re.compile(r"^\s*(?:[\uf0b7•]|\([a-z]|\d{1,2}\.\s)", re.I)
SUBJECT = re.compile(r"\b(?:the )?following\b|\bnamely\b|\binclud(?:e|es|ing)\b", re.I)
LIST_INTRO = re.compile(r"(?:[:;]|(?:including|include but not be limited to))\s*$", re.I)
OTHER_SECTION = re.compile(
    r"^\d{1,2}\.\s+(?:The Parties|This Agreement|Each party|Neither party)\b", re.I
)
EXCLUSION = re.compile(
    r"\b(?:but shall exclude|but excludes?|except (?:such )?information|does not include"
    r"|shall not include|excluding|not including|other than|not be deemed|shall exclude)\b",
    re.I,
)
RESTRICTED = re.compile(
    r"\b(?:only|solely|exclusively)\s+(?:to|include|of)?\s*technical (?:data|information)\b"
    r"|\ball confidential information (?:must|shall) be technical\b",
    re.I,
)
INTRO = re.compile(r"\baccess to selected information\b.{0,350}\bincluding\b", re.I)
CATEGORIES = re.compile(
    r"^Some of the information in each of these categories is confidential\b", re.I
)
DEEMED = re.compile(
    r"^This information received from a party\b.*\bshall be deemed to be confidential information\b",
    re.I,
)
ASSIGNED_INFORMATION = re.compile(r"^Recipient agrees that all information disclosed\b", re.I)
ASSIGNED_END = re.compile(r"\bshall be considered Confidential Information[.\s]*$", re.I)
NAMED_INFORMATION = re.compile(
    r"^Information within the meaning of this Agreement shall include\b", re.I
)


@dataclass(frozen=True)
class Witness:
    kind: str
    spans: tuple[int, ...]
    members: tuple[int, ...]
    rule: str


def content(text):
    """Return a named substantive category on the affirmative side of a clause."""
    affirmative = EXCLUSION.split(text, maxsplit=1)[0]
    return bool(CONTENT_TYPE.search(affirmative) or COORDINATED_CONTENT.search(affirmative))


def definition(text):
    if text.upper().startswith("WHEREAS"):
        return None
    return DEFINITION.search(text) or DEFINING.search(text)


def types_in_scope(clauses):
    """Recognize complete definitions, continuations, and a bounded backward reference."""
    if any(RESTRICTED.search(s) for s in clauses):
        return []
    witnesses = []
    for i, span in enumerate(clauses):
        if ASSIGNED_INFORMATION.search(span) and ASSIGNED_END.search(span) and content(span):
            witnesses.append(Witness("substance", (i,), (i,), "classifying_assignment"))
        if NAMED_INFORMATION.search(span) and content(span) and (provider := PROVIDER.search(span)):
            for j in range(i + 1, min(i + 5, len(clauses))):
                duty = DUTY_PROVIDER.search(clauses[j])
                if duty and duty[1] == provider[1]:
                    witnesses.append(Witness("substance", (i, j), (i,), "same_provider_definition"))
                    break
        marker = definition(span)
        if marker is None:
            continue
        if content(span[marker.end() :]):
            witnesses.append(Witness("substance", (i,), (i,), "definition_clause"))
        if not (LIST_INTRO.search(span) and SUBJECT.search(span)) or EXCLUSION.search(span):
            continue
        for j in range(i + 1, min(len(clauses), i + 18)):
            member = clauses[j]
            if not member:
                continue
            if OTHER_SECTION.search(member) or not ENUM.match(member) or definition(member):
                break
            if content(member):
                witnesses.append(Witness("substance", (i, j), (j,), "defined_enumeration"))
            if EXCLUSION.search(member):
                break
    for i, span in enumerate(clauses[:-2]):
        if (
            INTRO.search(span)
            and content(span)
            and CATEGORIES.search(clauses[i + 1])
            and DEEMED.search(clauses[i + 2])
        ):
            witnesses.append(Witness("substance", (i, i + 1, i + 2), (i,), "category_reference"))
    return witnesses


def find_witnesses(views):
    spans = spans_for(views["substance"])
    clauses = [" ".join(s.split()) for s in spans]
    initial_member = {
        "defined_information_and_duty",
        "same_provider_information_and_duty",
        "expressly_backed_recital",
    }
    modes = [
        Witness("carrier", ids, (ids[0 if rule in initial_member else -1],), rule)
        for rule, ids in oral_proof(views["carrier"])
    ]
    found = [*types_in_scope(clauses), *modes]
    return {
        kind: sorted(
            {w for w in found if w.kind == kind}, key=lambda w: (len(w.spans), w.spans, w.rule)
        )
        for kind in TASKS
    }


def source_projection(kind):
    """The derived inclusion fact agrees under both measured interfaces."""
    module, assets = layouts()
    state = dict.fromkeys(module.fields)
    fields = tuple(module.fields)
    offset = 0 if kind == "substance" else 3
    state[fields[offset]] = True
    state[fields[offset + 1]] = True
    decoded = {
        arm: residual.decode(
            asset, residual.encode(asset["features"], state), {}, module_binding=module.binding
        )
        for arm, asset in assets.items()
    }
    expected = NO if kind == "substance" else YES
    assert all(
        result["valid"] and result["outputs"][kind] == expected for result in decoded.values()
    )
    return expected


def apply_witness(kind, current, evidence, paths, mode):
    """Filter the common paths by what the original read actually cited."""
    if mode == "original":
        return current
    ids = set(evidence)
    for w in paths:
        needed = () if mode == "whole_source" else w.members if mode == "cited_member" else w.spans
        if set(needed) <= ids:
            expected = source_projection(kind)
            if current["answer"] == expected and set(w.spans) <= set(current["evidence"]):
                return current
            return {"answer": expected, "evidence": list(w.spans)}
    return current


def replay(views, originals, cites):
    signatures = {key: find_witnesses(native) for key, native in views.items()}
    modes = ("original", "cited_complete", "cited_member", "whole_source")
    measured = {}
    relevant = Counter()
    for arm, bank in originals.items():
        measured[arm] = {}
        for key, rows in bank.items():
            measured[arm][key] = {}
            for kind, before in rows.items():
                paths = signatures[key][kind]
                raw = cites[arm][key][kind] if cites is not None else before["evidence"]
                relevant[(arm, kind, "whole")] += bool(paths)
                relevant[(arm, kind, "complete")] += any(set(w.spans) <= set(raw) for w in paths)
                relevant[(arm, kind, "member")] += any(set(w.members) <= set(raw) for w in paths)
                measured[arm][key][kind] = {
                    mode: apply_witness(kind, before, raw, paths, mode) for mode in modes
                }
    return measured, {
        arm: {
            k: {level: relevant[arm, k, level] for level in ("whole", "complete", "member")}
            for k in TASKS
        }
        for arm in originals
    }


def verify_request(payload, views):
    (message,) = (x["content"] for x in payload["messages"] if x["role"] == "user")
    envelope = json.loads(message)
    public = envelope.get("public", envelope)
    by_id = {v["id"]: v["public"] for v in public["native_views"]}
    for native in views.values():
        expected = native["public"]
        entry = by_id[native["id"]]
        doc = public["shared_documents"][entry["document_ref"]]
        assert (
            entry["question"] == expected["question"]
            and doc["source_text"] == expected["source_text"]
        )
        assert doc["sentence_spans"] == expected["sentence_spans"]


def views_for(source):
    return {k: next(v for v in source["views"] if v["id"] == task) for k, task in TASKS.items()}


def settled_probe(cases, binding):
    receipt = read(MEMBERSHIP)
    stage = ROOT / receipt["artifact_root"]
    old = read(stage / "binding.json")
    assert old == binding and stage.name == digest(old)
    terminal = read(stage / "terminal.json")
    assert sha(stage / "terminal.json") == receipt["terminal_sha256"]
    assert sha(stage / "predictions.json") == terminal["predictions_sha256"]
    assert all(sha(stage / "source_snapshot" / name) == h for name, h in old["sources"].items())
    predictions = read(stage / "predictions.json")
    native = {arm: {} for arm in ROLES}
    citations = {arm: {} for arm in ROLES}
    verified = set()
    with sqlite3.connect(LEDGER.as_uri() + "?mode=ro", uri=True) as db:
        for case, rows in zip(cases, predictions, strict=True):
            for arm, row in rows.items():
                identity = row["physical_call_id"]
                source, status, obj = db.execute(
                    "select source,status,result from calls where id=?", (identity,)
                ).fetchone()
                assert (
                    source == case["source"] and status == "completed" and identity not in verified
                )
                verified.add(identity)
                raw = json.loads(obj)
                assert raw["finish_reason"] == "stop"
                citations[arm][source] = json.loads(raw["content"])["evidence"]
                native[arm][source] = row["predictions"]
    assert len(verified) == terminal["new_executor_requests"] == 18
    return native, citations, receipt["terminal_sha256"]


def load_train():
    binding, cases, native = archive()
    first = ROOT / read(BOOTSTRAP)["artifact_root"]
    roster = load_roster(read(first / "binding.json"))
    views = {
        row["key"]: views_for(row)
        for cohort in roster
        for row in cohort
        if row["dataset"] == DATASET and row["project_split"] == "train"
    }
    assert native.keys() == views.keys() and len(views) == 24
    originals = {arm: {key: row[arm] for key, row in native.items()} for arm in ARMS}
    return views, originals, ROOT / binding["grade_path"], binding["grade_sha256"], binding, cases


def load_dev():
    _, branch, end = bound_stage(dev_pointer(8))
    checkpoint = ROOT / branch["checkpoint_root"]
    study = read(checkpoint / "binding.json")
    assert digest(study) == checkpoint.name == branch["checkpoint_binding_sha256"]
    b0 = ROOT / branch["b0_dev_data_root"]
    roster = read(b0 / "public_DEV_sources.json")
    assert digest(roster) == read(b0 / "binding.json")["DEV_public_sha256"] and len(roster) == 80
    cohort = [s for s in roster if s["dataset"] == DATASET and s["project_split"] == "dev"]
    assert len(cohort) == 16
    views = {s["key"]: views_for(s) for s in cohort}
    grade = study["grading_paths"][DATASET]
    native = {}
    verified = set()
    with sqlite3.connect(LEDGER.as_uri() + "?mode=ro", uri=True) as db:
        for arm in ARMS:
            directory = checkpoint / "dev" / "B8" / arm
            seal = verify(read(directory / "prediction_seal.json"), "prediction_seal_sha256")
            cell = verify(read(directory / "scores.json"), "cell_sha256")
            assert cell["partition"] == "dev" and cell["cell_sha256"] == end["cell_sha256"][arm]
            assert cell["prediction_seal_sha256"] == seal["prediction_seal_sha256"]
            assert seal["task_sha256"] == digest(read(directory / "task.json"))
            native[arm] = {}
            for key, by_kind in views.items():
                saved = read(directory / "predictions" / (digest(key) + ".json"))
                assert (
                    seal["predictions_sha256"][key] == digest(saved)
                    and saved["source"] == key
                    and saved["library_sha256"] == cell["libraries"][DATASET]
                )
                before = verified.copy()
                answer = verify_wire(db, key, saved["result"], verified)
                for identity in verified - before:
                    (stored,) = db.execute(
                        "select result from calls where id=?", (identity,)
                    ).fetchone()
                    folder = Path(json.loads(stored)["artifact_directory"])
                    verify_request(read(folder / "request.json")["payload"], by_kind)
                native[arm][key] = {
                    k: {
                        "answer": answer[task]["answer"],
                        "evidence": answer[task]["evidence_sentence_ids"],
                    }
                    for k, task in TASKS.items()
                }
    return views, native, ROOT / grade, study["grading_file_sha256"][grade], len(verified)


def score(views, bank, labels):
    results = {}
    for arm, rows in bank.items():
        measurements = {}
        for key, found in rows.items():
            for kind, by_mode in found.items():
                task = TASKS[kind]
                for mode, pred in by_mode.items():
                    grade = grade_view(
                        DATASET,
                        views[key][kind],
                        labels[key][task],
                        pred["answer"],
                        pred["evidence"],
                    )
                    measurements.setdefault((kind, mode), []).append(
                        {
                            "source": key,
                            "view": task,
                            "grade": grade["grade"],
                            "evidence": grade["evidence_f1"],
                        }
                    )
        results[arm] = {}
        for (kind, mode), entries in measurements.items():
            base = measurements[kind, "original"]
            results[arm].setdefault(kind, {})[mode] = {
                "correct": int(sum(r["grade"] for r in entries)),
                "evidence_F1": mean(r["evidence"] for r in entries),
                "evidence_when_correct": mean(r["evidence"] * r["grade"] for r in entries),
                "vs_original": paired_source_effect(base, entries) if mode != "original" else None,
            }
    return results


def run(partition):
    train_checksum = parent = None
    if partition == "train":
        views, original, grade, grade_hash, baseline, cases = load_train()
        matched, raw, parent = settled_probe(cases, baseline)
        physical = baseline["original_responses_verified"]
        probe_views = {row["source"]: row["views"] for row in cases}
        probe, probe_cov = replay(probe_views, matched, raw)
    else:
        views, original, grade, grade_hash, physical = load_dev()
        pointer = read(TRAIN)
        stage = ROOT / pointer["artifact_root"]
        train_checksum = sha(stage / "terminal.json")
        assert train_checksum == pointer["terminal_sha256"]
        assert read(stage / "binding.json")["runner_sha256"] == sha(Path(__file__))
    assert partition in grade.parts and sha(grade) == grade_hash
    measured, coverage = replay(views, original, None)
    binding = {
        "partition": partition,
        "runner_sha256": sha(Path(__file__)),
        "cohort_sha256": digest(views),
        "train_terminal_sha256": train_checksum,
        "parent_model_probe_sha256": parent,
        "native_annotation_sha256": grade_hash,
        "upstream_oral_proof_sha256": sha(
            Path(__file__).with_name("convergence_revision5_cni_oral_scope.py")
        ),
        "finite_consumer_sha256": sha(
            Path(__file__).with_name("convergence_revision5_cni_definition_membership.py")
        ),
        "modes": [
            "complete prior citation",
            "prior member plus bound defining scope",
            "complete-text direct lookup",
        ],
    }
    out = HOME / partition / digest(binding)
    immutable_json(out / "binding.json", binding)
    immutable_json(out / "predictions.json", measured)
    if partition == "train":
        immutable_json(out / "paired_archive_predictions.json", probe)
    labels = read(grade)
    with sqlite3.connect(LEDGER.as_uri() + "?mode=ro", uri=True) as db:
        ledger = dict(db.execute("select status,count(*) from calls group by status"))
    assert not ledger.get("reserved")
    summary = {
        "partition": partition,
        "mothers": len(views),
        "original_responses_verified": physical,
        "new_requests": 0,
        "ledger": ledger,
        "coverage": coverage,
        "native": score(views, measured, labels),
        "predictions_sha256": sha(out / "predictions.json"),
    }
    if partition == "train":
        summary["matched_six"] = {
            "native": score(probe_views, probe, labels),
            "coverage": probe_cov,
            "responses_reused": 18,
            "predictions_sha256": sha(out / "paired_archive_predictions.json"),
        }
    immutable_json(out / "terminal.json", summary)
    if partition == "train":
        write_status(
            out, {"status": "TRAIN_settled", "terminal_sha256": sha(out / "terminal.json")}, TRAIN
        )
    print(
        json.dumps({"artifact_root": str(out.relative_to(ROOT)), **summary}, sort_keys=True),
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("partition", choices=("train", "dev"))
    run(parser.parse_args().partition)
