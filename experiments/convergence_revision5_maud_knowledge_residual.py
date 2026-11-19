"""Specialize the MAUD knowledge consumer using facts visible in the exact source."""

import argparse
import json
import re
import sqlite3
from dataclasses import replace
from hashlib import sha256
from itertools import combinations
from pathlib import Path
from zipfile import ZipFile

from experiments.convergence_formal_b1_observe import POINTER as FIRST
from experiments.convergence_formal_b1_observe import load_roster
from experiments.convergence_formal_bootstrap import POINTER as BOOTSTRAP
from experiments.convergence_formal_curves import pointer as dev_pointer
from experiments.convergence_formal_train_fit import EXTERNAL_ARM, ORDINARY
from experiments.convergence_formal_train_observe import pointer as observe_pointer
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from experiments.convergence_revision5_cni_nonsolicitation import bound_stage
from experiments.convergence_revision5_cni_oral_dev import verify_wire
from experiments.convergence_revision5_maud_parent_definition_coverage import ARCHIVE, unpage
from experiments.convergence_revision5_maud_sibling_cue import response, verify_prediction
from experiments.convergence_revision5_maud_ternary_relation import equivalent_asset
from legal_skill_guard.paired_interfaces import maud_knowledge_relational as knowledge
from legal_skill_guard.paired_interfaces import residual
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.paired_interfaces.convergence_journal import TrainingJournal
from legal_skill_guard.paired_interfaces.formal_evaluation import verify
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest

HOME = BASE / "revision5_MAUD_knowledge_residual_20261119"
TRAIN_PTR = HANDOFF / "revision5_MAUD_knowledge_residual_TRAIN_current.json"
ARMS = (ORDINARY, EXTERNAL_ARM)
DATASET, TASK = "MAUD", knowledge.TASK
TARGET, EFFECT, ACTUAL = ("qualification_target", "inquiry_effect", "explicit_actual_restriction")
TERM = r'[“"](?:knowledge(?: of [^”"]{1,60})?|to (?:the )?[^”"]{1,50}knowledge(?: of [^”"]{1,60})?)[”"]'
DEFINITION = re.compile(
    rf'{TERM}(?:\s+or\s+{TERM})?[^.!?”“"]{{0,240}}?\b(?:shall\s+mean|means?)\b', re.I
)
END = re.compile(r"[.!?](?=\s|$)")
INITIAL_OR_ABBREVIATION = re.compile(r"\b(?:[A-Z]|Mr|Ms|Dr|Jr|Sr|Inc|Corp|Co|Ltd|No|U\.S|e\.g)\Z")
ACTUAL_WORDING = re.compile(r"\bactual knowledge\b", re.I)
INQUIRY = re.compile(r"\b(?:inquir\w*|investigat\w*)\b", re.I)
REQUIRED = re.compile(
    r"\b(?:after|following|assuming|upon)\s+(?:reasonable|due|reasonable due)\s+inquiry\b", re.I
)
NEGATED = re.compile(r"\b(?:without|no|not|except)\b[^,.;]{0,55}$", re.I)
OMISSION = "<omitted>"


def normalize(text):
    return unpage(text.replace("\u200b", ""))


def definitions(text):
    """Anchor a definition and keep initials, numbered sections and role lists intact."""
    anchors = []
    end = 0
    for term in DEFINITION.finditer(text):
        if term.start() < end:
            continue
        boundary = next(
            (
                p
                for p in END.finditer(text, term.end())
                if p[0] != "."
                or not INITIAL_OR_ABBREVIATION.search(
                    text[max(term.end(), p.start() - 12) : p.start()]
                )
            ),
            None,
        )
        end = boundary.end() if boundary else len(text)
        anchors.append({"text": text[term.start() : end], "closed": boundary is not None})
    return anchors


def facts(anchor):
    text = anchor["text"]
    known = {}
    if ACTUAL_WORDING.search(text):
        known[ACTUAL] = True
    for marker in REQUIRED.finditer(text):
        if not NEGATED.search(text[max(0, marker.start() - 65) : marker.start()]):
            return {**known, TARGET: "target_definition", EFFECT: "required"}
    if anchor["closed"] and OMISSION not in text and not INQUIRY.search(text):
        known.update({TARGET: "absent", EFFECT: "absent"})
    return known


def specialized(known):
    """Fix only independently anchored fields, and prove every remaining finite state."""
    original = knowledge.module()
    allowed = [
        (state, outcomes)
        for state, outcomes in zip(original.states, original.outcomes, strict=True)
        if all(state[k] == value for k, value in known.items())
    ]
    model = replace(
        original, states=tuple(s for s, _ in allowed), outcomes=tuple(o for _, o in allowed)
    )
    if not allowed:
        raise ValueError("The source facts fall outside the MAUD consumer domain")
    candidates = {entry[0]["outputs"]["classification"] for _, entry in allowed}
    # A zero-field certificate directly resolves a constant output on the restricted domain.
    if len(candidates) == 1:
        (answer,) = candidates
        return {
            "states": len(allowed),
            "direct_answer": answer,
            "fixed_fields": 0,
            "synthesized_fields": 0,
            "fully_determined": True,
        }
    widths = {}
    for name, features in (
        ("fixed", knowledge.assets()[0]["features"]),
        ("synthesized", equivalent_asset()["features"]),
    ):
        remainder = [
            f
            for f in features
            if len({residual.canonical(residual.feature_value(f, s)) for s, _ in allowed}) > 1
        ]
        for width in range(1, len(remainder) + 1):
            feasible = next(
                (
                    fs
                    for fs in combinations(remainder, width)
                    if residual.witness(model, fs) is None
                ),
                None,
            )
            if feasible is not None:
                candidate = residual.compile_pair(
                    model, feasible, operation="source_conditioned_knowledge", layout="anchored"
                )
                for state, outputs in allowed:
                    actual = residual.decode(
                        candidate,
                        residual.encode(feasible, state),
                        {},
                        module_binding=model.binding,
                    )
                    assert actual == outputs[0]
                widths[name + "_fields"] = width
                break
        assert name + "_fields" in widths
    return {"states": len(allowed), "direct_answer": None, "fully_determined": False, **widths}


def parent_anchor(visible, parent):
    """Extend a uniquely aligned definition and keep its corpus scope distinct."""
    parts = [piece.strip() for piece in visible["text"].split(OMISSION)]
    if not all(parts):
        return None
    hits = []
    for match in re.finditer(re.escape(parts[0]), parent, re.I):
        # The definition must begin exactly at the quoted term in both sources.
        parent_matches = definitions(parent[match.start() : match.start() + 3500])
        if not parent_matches:
            continue
        candidate = parent_matches[0]
        sentence = candidate["text"]
        if (
            not candidate["closed"]
            or not sentence.casefold().startswith(parts[0].casefold())
            or len(parts) > 1
            and not all(sentence.casefold().count(p.casefold()) == 1 for p in parts[1:])
        ):
            continue
        cursor = len(parts[0])
        for piece in parts[1:]:
            start = sentence.casefold().find(piece.casefold(), cursor)
            if start < 0:
                break
            cursor = start + len(piece)
        else:
            hits.append(
                {
                    **candidate,
                    "parent_offset": match.start(),
                    "visible_characters_bound": sum(map(len, parts)),
                }
            )
    return hits[0] if len(hits) == 1 else None


def independent_direct(known):
    if known.get(TARGET) == "target_definition" and known.get(EFFECT) == "required":
        return "Constructive knowledge"
    if known.get(EFFECT) == "absent" and known.get(ACTUAL) is True:
        return "Actual knowledge"
    return None


def view_for(source):
    return next(v for v in source["views"] if v["id"] == TASK)


def verify_request_view(payload, source):
    (message,) = (m["content"] for m in payload["messages"] if m["role"] == "user")
    request = json.loads(message)
    views = request.get("public", request)["native_views"]
    expected = view_for(source)["public"]
    assert sum(view["public"] == expected for view in views) == 1


def proof(source, corpus):
    public = normalize(view_for(source)["public"]["source_text"])
    anchored = definitions(public)
    if len(anchored) != 1:
        return {
            "matched_definition": False,
            "excerpt": specialized({}),
            "parent": None,
            "visible_fact_count": 0,
        }
    visible = anchored[0]
    known = facts(visible)
    original = specialized(known)
    assert original["direct_answer"] == independent_direct(known)
    parent = None
    if corpus is not None:
        raw = corpus.read("data/contracts/" + source["parent_id"] + ".txt")
        assert sha256(raw).hexdigest() == source["fulltext_raw_sha256"]
        parent = parent_anchor(visible, normalize(raw.decode("utf-8-sig")))
    checked = None
    if parent is not None:
        restored = facts(parent)
        checked = specialized(restored)
        assert checked["direct_answer"] == independent_direct(restored)
        checked.update(
            more_definition_text=parent["text"] != visible["text"],
            parent_definition_sha256=digest(parent["text"]),
            parent_offset=parent["parent_offset"],
        )
    return {
        "matched_definition": True,
        "visible_fact_count": len(known),
        "excerpt": original,
        "parent": checked,
        "visible_definition_sha256": digest(visible["text"]),
        "excerpt_has_omission_or_open_tail": not visible["closed"] or OMISSION in visible["text"],
    }


def archive_inputs(part, cases, checkpoint, study, roster, archives):
    bank = {arm: {} for arm in ARMS}
    verified = set()
    with sqlite3.connect(LEDGER.as_uri() + "?mode=ro", uri=True) as db:
        ledger = dict(db.execute("select status,count(*) from calls group by status"))
        assert not ledger.get("reserved")
        if part == "TRAIN":
            journal = TrainingJournal(checkpoint, study, roster)
            for batch, sources in enumerate(roster, 1):
                stage, info, end = bound_stage(FIRST if batch == 1 else observe_pointer(batch))
                archives[str(batch)] = sha(stage / "terminal.json")
                grade = info["native_grade_paths"][DATASET]
                grade_sha = info["native_grade_sha256"][grade]
                for arm in ARMS:
                    receipt = journal._observations(arm, batch)
                    assert receipt["train_observation_sha256"] == end["observation_receipts"][arm]
                    for s in (row for row in sources if row["key"] in cases):
                        key = s["key"]
                        saved = read(
                            journal.directory(arm, batch) / "predictions" / (digest(key) + ".json")
                        )
                        assert digest(saved) == receipt["predictions"][key]
                        pair = saved["result"]
                        wire = verify_prediction(db, key, pair)
                        if wire not in verified:
                            _, payload = response(db, key, wire)
                            verify_request_view(payload, s)
                            verified.add(wire)
                        bank[arm][key] = pair["native"][TASK]["answer"]
        else:
            stage, _, end = bound_stage(dev_pointer(8))
            archives["B8_DEV"] = sha(stage / "terminal.json")
            grade = study["grading_paths"][DATASET]
            grade_sha = study["grading_file_sha256"][grade]
            for arm in ARMS:
                root = checkpoint / "dev" / "B8" / arm
                task = read(root / "task.json")
                seal = verify(read(root / "prediction_seal.json"), "prediction_seal_sha256")
                cell = verify(read(root / "scores.json"), "cell_sha256")
                assert (
                    cell["partition"] == "dev"
                    and cell["cell_sha256"] == end["cell_sha256"][arm]
                    and seal["task_sha256"] == digest(task)
                    and cell["prediction_seal_sha256"] == seal["prediction_seal_sha256"]
                )
                for key, source in cases.items():
                    pred = read(root / "predictions" / (digest(key) + ".json"))
                    assert (
                        digest(pred) == seal["predictions_sha256"][key]
                        and pred["library_sha256"] == cell["libraries"][DATASET]
                    )
                    before = verified.copy()
                    bank[arm][key] = verify_wire(db, key, pred["result"], verified)[TASK]["answer"]
                    for identity in verified - before:
                        (stored,) = db.execute(
                            "select result from calls where id=?", (identity,)
                        ).fetchone()
                        request = read(
                            Path(json.loads(stored)["artifact_directory"]) / "request.json"
                        )
                        assert (
                            request["payload"]["chat_template_kwargs"]["enable_thinking"] is False
                        )
                        verify_request_view(request["payload"], source)
    assert all(rows.keys() == cases.keys() for rows in bank.values())
    assert part.lower() in Path(grade).parts and sha(ROOT / grade) == grade_sha
    return bank, len(verified), ledger, ROOT / grade


def run(part):
    if part == "TRAIN":
        archive_sha = read(BASE / "postfreeze_M2_MAUD_source_scope_20261119" / "terminal.json")[
            "parent_reference_audit"
        ]["official_archive_sha256"]
        assert sha(ARCHIVE) == archive_sha
        checkpoint = ROOT / read(BOOTSTRAP)["artifact_root"]
        study = read(checkpoint / "binding.json")
        assert digest(study) == checkpoint.name
        roster = load_roster(study)
        sources = [s for batch in roster for s in batch]
        parent_train = None
    else:
        archive_sha = None
        training = read(TRAIN_PTR)
        parent_train = training["terminal_sha256"]
        assert sha(ROOT / training["artifact_root"] / "terminal.json") == parent_train
        assert read(ROOT / training["artifact_root"] / "binding.json")["runner_sha256"] == sha(
            Path(__file__)
        )
        _, setup, _ = bound_stage(dev_pointer(8))
        checkpoint = ROOT / setup["checkpoint_root"]
        study = read(checkpoint / "binding.json")
        assert digest(study) == setup["checkpoint_binding_sha256"]
        shared = ROOT / setup["b0_dev_data_root"]
        sources = read(shared / "public_DEV_sources.json")
        assert (
            len(sources) == 80
            and digest(sources) == read(shared / "binding.json")["DEV_public_sha256"]
        )
        roster = None
    cases = {
        s["key"]: s
        for s in sources
        if s["dataset"] == DATASET and s["project_split"] == part.lower()
    }
    assert len(cases) == (24 if part == "TRAIN" else 16)
    if part == "TRAIN":
        with ZipFile(ARCHIVE) as corpus:
            proofs = {key: proof(s, corpus) for key, s in cases.items()}
    else:
        proofs = {key: proof(s, None) for key, s in cases.items()}
    archives = {}
    bank, native_reads, ledger, grade = archive_inputs(
        part, cases, checkpoint, study, roster, archives
    )
    preds = {}
    for arm, rows in bank.items():
        preds[arm] = {}
        for key, old in rows.items():
            p = proofs[key]
            explicit = p["excerpt"]["direct_answer"]
            parent_value = p["parent"]["direct_answer"] if p["parent"] else None
            preds[arm][key] = {"original": old, "scoped_excerpt": explicit or old}
            if part == "TRAIN":
                preds[arm][key]["parent_context_sensitivity"] = parent_value or explicit or old
    bind = {
        "partition": part,
        "runner_sha256": sha(Path(__file__)),
        "source_sha256": digest(cases),
        "consumer_sha256": sha(Path(knowledge.__file__)),
        "compiler_sha256": sha(Path(residual.__file__)),
        "proofs_sha256": digest(proofs),
        "official_parent_archive_sha256": archive_sha,
        "native_grade_sha256": sha(grade),
        "original_native_terminals": archives,
        "TRAIN_terminal_sha256": parent_train,
    }
    out = HOME / part / digest(bind)
    immutable_json(out / "binding.json", bind)
    immutable_json(out / "predictions.json", preds)
    immutable_json(out / "proofs.json", proofs)
    annotation = read(grade)
    native = {}
    for arm, rows in preds.items():
        measurements = {mode: [] for mode in next(iter(rows.values()))}
        for key, answers in rows.items():
            for mode, value in answers.items():
                actual = grade_view(DATASET, view_for(cases[key]), annotation[key][TASK], value)[
                    "grade"
                ]
                measurements[mode].append({"source": key, "view": TASK, "grade": actual})
        native[arm] = {
            "correct": {
                mode: int(sum(v["grade"] for v in values)) for mode, values in measurements.items()
            },
            "by_mode_vs_original": {
                mode: paired_source_effect(measurements["original"], values)
                for mode, values in measurements.items()
                if mode != "original"
            },
        }
    differences = []
    for i, (key, p) in enumerate(proofs.items()):
        a = annotation[key][TASK]["answer"]
        parent = p["parent"]
        if parent and parent["direct_answer"] and parent["direct_answer"] != a:
            differences.append(
                {
                    "position": i,
                    "official_excerpt_label": a,
                    "parent_interpretation": parent["direct_answer"],
                    "parent_adds_definition_text": parent["more_definition_text"],
                    "excerpt_proof_label": p["excerpt"]["direct_answer"],
                }
            )
    report = {
        "status": "settled_MAUD_original_and_parent_knowledge_scope",
        "partition": part,
        "mothers": len(cases),
        "excerpt_targets_bound": sum(p["matched_definition"] for p in proofs.values()),
        "excerpt_proof_decides": sum(
            p["excerpt"]["direct_answer"] is not None for p in proofs.values()
        ),
        "parents_uniquely_bound": sum(p["parent"] is not None for p in proofs.values()),
        "parents_extend_visible_text": sum(
            bool(p["parent"] and p["parent"]["more_definition_text"]) for p in proofs.values()
        ),
        "parent_scope_changes_relative_to_native_reference": differences,
        "residual_read_fields": {
            role: sum(p["excerpt"][role + "_fields"] for p in proofs.values())
            for role in ("fixed", "synthesized")
        },
        "by_arm": native,
        "archived_physical_responses": native_reads,
        "new_requests": 0,
        "ledger": ledger,
        "predictions_sha256": sha(out / "predictions.json"),
    }
    immutable_json(out / "terminal.json", report)
    if part == "TRAIN":
        write_status(
            out,
            {"status": report["status"], "terminal_sha256": sha(out / "terminal.json")},
            TRAIN_PTR,
        )
    print(
        json.dumps({"artifact_root": str(out.relative_to(ROOT)), **report}, sort_keys=True),
        flush=True,
    )


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("partition", choices=("TRAIN", "DEV"))
    run(cli.parse_args().partition)
