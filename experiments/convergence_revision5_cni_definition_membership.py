"""Compare typed definition membership with a direct reader on original ContractNLI TRAIN."""

import argparse
import fcntl
import inspect
import json
import sqlite3
from collections import Counter
from functools import lru_cache
from pathlib import Path
from statistics import mean

import jsonschema

from experiments.convergence_formal_b1_observe import POINTER as FIRST
from experiments.convergence_formal_b1_observe import load_roster
from experiments.convergence_formal_bootstrap import POINTER as BOOTSTRAP
from experiments.convergence_formal_train_fit import EXTERNAL_ARM, ORDINARY
from experiments.convergence_formal_train_observe import pointer as observe_pointer
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from experiments.convergence_revision5_cni_disposition_scope import spans_for
from experiments.convergence_revision5_cni_nonsolicitation import bound_stage
from experiments.convergence_revision5_maud_sibling_cue import response, verify_prediction
from legal_skill_guard.paired_interfaces import residual
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.paired_interfaces.convergence_journal import TrainingJournal
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import grade_view, record_schema
from legal_skill_guard.skill_evolution.objects import digest

HOME = BASE / "revision5_CNI_definition_membership_20261119"
POINTER = HANDOFF / "revision5_CNI_definition_membership_current.json"
DATASET = "ContractNLI"
TASKS = {"substance": "nda-2", "carrier": "nda-3"}
ROLES = ("fixed", "synthesized", "direct_reader")
YES, NO, ABSENT = "Entailment", "Contradiction", "NotMentioned"
# Selection is fixed before any new read. Clause witnesses are source reviews
# held out of all request messages and supplied only to the offline control.
REVIEW = {
    (1, 1): ((NO, (9, 11, 14, 17, 19, 20)), (YES, (7,))),
    (3, 2): ((NO, (10, 11, 12)), (YES, (10,))),
    (5, 0): ((ABSENT, ()), (YES, (13,))),
    (6, 0): ((ABSENT, ()), (YES, (14,))),
    (6, 1): ((NO, (18, 21)), (YES, (18,))),
    (6, 2): ((NO, (5, 6, 7)), (YES, (5, 7))),
}
MEANINGS = {
    "listed_type_in_protected_definition": "the cited substantive category is included under the operative protected-information definition",
    "listed_type_is_nontechnical": "the cited substantive category is nontechnical (e.g., recruitment policies or financial information), regardless of disclosure medium",
    "closed_technical_limit": "an operative scope rule limits protected information to technical content only",
    "stated_medium_in_protected_definition": "the cited transmission-medium wording is part of the operative protected-information definition",
    "stated_medium_permits_oral": "the cited transmission-medium wording includes oral disclosures, explicitly or through an applicable all-forms rule",
    "closed_nonoral_limit": "an operative scope rule expressly excludes orally transmitted information",
}
COMMON = (
    "Read the entire agreement and both original questions. Confidential Information can include types of substance "
    "(for example, technical specifications or financial plans) and modes of disclosure (for example, writing or speech). "
    "A mode of transmission gives no evidence about the substance. A broad general definition or non-exhaustive "
    "list of unspecified data and documents gives no named nontechnical category. Resolve listed examples, "
    "anaphora, and separately numbered continuations before deciding whether an operative definition includes "
    "a type of substance or a mode of transmission. Keep background statements and expressly excluded information "
    "outside the operative definition unless the document links them. Check whether a narrower limit is expressly "
    "stated. For a signed answer, cite all original evidence spans required to bind that judgment, including a "
    "definition lead-in or referring span where needed. Use zero-based IDs. "
    "For a verified absence, give no evidence. Do not invent a scope limit or infer actual contents from the medium."
)


def consume(values, _context):
    substance = None
    # Literal equality is part of the relation compiler's Python syntax.
    if (
        values["listed_type_in_protected_definition"] == True  # noqa: E712
        and values["listed_type_is_nontechnical"] == True  # noqa: E712
    ):
        substance = NO
    elif (
        values["listed_type_in_protected_definition"] == False  # noqa: E712
        or values["listed_type_is_nontechnical"] == False  # noqa: E712
    ):
        if values["closed_technical_limit"] is not None:
            substance = YES if values["closed_technical_limit"] else ABSENT
    carrier = None
    if (
        values["stated_medium_in_protected_definition"] == True  # noqa: E712
        and values["stated_medium_permits_oral"] == True  # noqa: E712
    ):
        carrier = YES
    elif (
        values["stated_medium_in_protected_definition"] == False  # noqa: E712
        or values["stated_medium_permits_oral"] == False  # noqa: E712
    ):
        if values["closed_nonoral_limit"] is not None:
            carrier = NO if values["closed_nonoral_limit"] else ABSENT
    return {"substance": substance, "carrier": carrier}


@lru_cache(maxsize=1)
def layouts():
    procedure = inspect.getsource(consume)
    fields = tuple(MEANINGS)
    module = residual.FiniteModule.build(
        "definition_type_and_medium_membership",
        {name: [True, False, None] for name in fields},
        [{}],
        consume,
        consumer_sha256=digest(procedure),
        program_source=procedure,
        protected_status_fields=(fields[2], fields[5]),
        source_scope={
            "source_fields": ["source_text"],
            "local_unit": "textually witnessed candidate member of the definition",
            "field_meanings": MEANINGS,
        },
    )
    fixed = [{"name": n, "operation": "field", "field": n} for n in fields]
    synthesized = []
    for start, name in ((0, "substantive_member_attached"), (3, "oral_medium_attached")):
        deps = set(fields[start : start + 2])
        (link,) = (
            item
            for item in residual.consumer_relations(module)
            if item["expression"]["op"] == "and" and set(item["consumer_dependencies"]) == deps
        )
        synthesized.extend(({**link, "name": name}, fixed[start + 2]))
    assets = {
        "fixed": residual.compile_pair(
            module, fixed, operation="fixed_coordinates", layout="anchored"
        ),
        "synthesized": residual.compile_pair(
            module, synthesized, operation="consumer_relational_projection", layout="anchored"
        ),
    }
    for state in module.states:
        for asset in assets.values():
            encoded = residual.encode(asset["features"], state)
            decoded = residual.decode(asset, encoded, {}, module_binding=module.binding)
            assert decoded["valid"] and decoded["outputs"] == consume(state, {})
    return module, assets


def query(case, role):
    evidence = {
        "type": "array",
        "maxItems": 12,
        "items": {"type": "integer", "minimum": 0, "maximum": len(case["spans"]) - 1},
    }
    fields = {"evidence": record_schema(dict.fromkeys(TASKS, evidence))}
    if role == "direct_reader":
        fields["answers"] = record_schema(dict.fromkeys(TASKS, {"enum": [YES, NO, ABSENT, None]}))
        details = "Give answers to both questions in the answer record. Use null if the source is unresolved."
    else:
        asset = layouts()[1][role]
        fields["relations"] = record_schema(
            {f["name"]: {"enum": asset["domains"][f["name"]]} for f in asset["features"]}
        )
        details = (
            "Read the local source observations listed below. Use false for a checked negative or absence "
            "and null for unresolved attachment or meaning.\n"
            + "\n".join(residual.reader_prompt(asset, verbalize_relations=True).splitlines()[4:])
        )
    system = {"role": "system", "content": COMMON + "\n" + details}
    user = {"role": "user", "content": case["user"]}
    return [system, user], record_schema(fields)


def decode(case, role, result):
    try:
        if result["finish_reason"] != "stop":
            raise ValueError("The read did not complete")
        value = json.loads(result["content"])
        jsonschema.validate(value, query(case, role)[1])
        if role == "direct_reader":
            reads = value["answers"]
        else:
            module, assets = layouts()
            decoded = residual.decode(
                assets[role], value["relations"], {}, module_binding=module.binding
            )
            if not decoded["valid"]:
                raise ValueError("The observed tuple conflicts with the declared domain")
            reads = decoded["outputs"]
        output = {}
        for kind, label in reads.items():
            ids = value["evidence"][kind]
            if len(set(ids)) != len(ids) or any(not case["spans"][i].strip() for i in ids):
                raise ValueError("The reader cited a duplicate or empty original span")
            if label in (YES, NO) and not ids:
                label = None
            output[kind] = {"answer": label, "evidence": sorted(ids) if label in (YES, NO) else []}
        return output, None
    except (ValueError, jsonschema.ValidationError) as exc:
        return {kind: {"answer": None, "evidence": []} for kind in TASKS}, type(exc).__name__


def archive():
    checkpoint = ROOT / read(BOOTSTRAP)["artifact_root"]
    study = read(checkpoint / "binding.json")
    assert digest(study) == checkpoint.name
    roster = load_roster(study)
    journal = TrainingJournal(checkpoint, study, roster)
    cases, previous, proof, physical = [], {}, {}, set()
    grades = set()
    with sqlite3.connect(LEDGER.as_uri() + "?mode=ro", uri=True) as db:
        assert not db.execute("select 1 from calls where status='reserved'").fetchone()
        for i, cohort in enumerate(roster, 1):
            stage, stage_binding, end = bound_stage(FIRST if i == 1 else observe_pointer(i))
            proof[str(i)] = sha(stage / "terminal.json")
            grade = stage_binding["native_grade_paths"][DATASET]
            grades.add((grade, stage_binding["native_grade_sha256"][grade]))
            registered = {arm: journal._observations(arm, i) for arm in (ORDINARY, EXTERNAL_ARM)}
            assert all(
                registered[arm]["train_observation_sha256"] == end["observation_receipts"][arm]
                for arm in registered
            )
            for j, source in enumerate(row for row in cohort if row["dataset"] == DATASET):
                key = source["key"]
                assert source["project_split"] == "train"
                views = {
                    kind: next(v for v in source["views"] if v["id"] == task)
                    for kind, task in TASKS.items()
                }
                a, b = views.values()
                assert a["public"]["source_text"] == b["public"]["source_text"]
                assert spans_for(a) == spans_for(b)
                bank = {}
                for arm, receipt in registered.items():
                    stored = read(
                        journal.directory(arm, i) / "predictions" / (digest(key) + ".json")
                    )
                    assert digest(stored) == receipt["predictions"][key]
                    result = stored["result"]
                    ident = verify_prediction(db, key, result)
                    if ident not in physical:
                        _, payload = response(db, key, ident)
                        (message,) = (
                            x["content"] for x in payload["messages"] if x["role"] == "user"
                        )
                        envelope = json.loads(message)
                        public = envelope.get("public", envelope)
                        public_views = {v["id"]: v["public"] for v in public["native_views"]}
                        for expected in views.values():
                            actual = public_views[expected["id"]]
                            document = public["shared_documents"][actual["document_ref"]]
                            reference_view = expected["public"]
                            assert actual["question"] == reference_view["question"]
                            assert document["source_text"] == reference_view["source_text"]
                            assert document["sentence_spans"] == reference_view["sentence_spans"]
                        physical.add(ident)
                    bank[arm] = {
                        kind: {
                            "answer": result["native"][task]["answer"],
                            "evidence": result["native"][task]["evidence_sentence_ids"],
                        }
                        for kind, task in TASKS.items()
                    }
                previous[key] = bank
                if (i, j) not in REVIEW:
                    continue
                reference = {
                    kind: {"answer": label, "evidence": list(ids)}
                    for kind, (label, ids) in zip(TASKS, REVIEW[i, j], strict=True)
                }
                spans = spans_for(a)
                assert all(
                    spans[n].strip()
                    for expected in reference.values()
                    for n in expected["evidence"]
                )
                user = json.dumps(
                    {
                        "document": a["public"]["source_text"],
                        "questions": {k: v["public"]["question"] for k, v in views.items()},
                        "indexed_original_spans": [
                            {"id": n, "text": span} for n, span in enumerate(spans)
                        ],
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
                cases.append(
                    {
                        "source": key,
                        "position": [i, j],
                        "views": views,
                        "spans": spans,
                        "user": user,
                        "source_review": reference,
                    }
                )
    ((grade, checksum),) = grades
    assert "train" in Path(grade).parts and sha(ROOT / grade) == checksum
    assert len(previous) == 24 and len(cases) == len(REVIEW)
    slots = sorted((i, role) for i in range(len(cases)) for role in ROLES)
    binding = {
        "study": "consumer_bound_information_substance_and_medium",
        "partition": "train",
        "grade_path": grade,
        "grade_sha256": checksum,
        "original_stage_terminal_sha256": proof,
        "original_responses_verified": len(physical),
        "original_baseline_archive_sha256": digest(previous),
        "ordered_cohort_sha256": digest(cases),
        "state_count": len(layouts()[0].states),
        "candidate_versions": {k: a["version"] for k, a in layouts()[1].items()},
        "executor": study["executor"],
        "wires_sha256": digest([query(cases[i], role) for i, role in slots]),
        "new_executor_cells": len(slots),
        "new_teacher_cells": 0,
        "guard": "TRAIN only, same full text/span index/frozen reader for every condition",
        "sources": {
            str(path.relative_to(ROOT)): sha(path)
            for path in (
                Path(__file__),
                Path(residual.__file__),
                ROOT / "legal_skill_guard/skill_evolution/clients.py",
                ROOT / "legal_skill_guard/rr/client.py",
            )
        },
    }
    return binding, cases, previous


def check_wire(db, case, role, identity, result):
    row = db.execute(
        "select source,status,purpose,request_hash,result from calls where id=?", (identity,)
    ).fetchone()
    assert row[:3] == (case["source"], "completed", "skill_actor")
    actual = json.loads(row[4])
    directory = Path(actual["artifact_directory"])
    req = read(directory / "request.json")
    payload = req["payload"]
    assert req["request_hash"] == row[3] == actual["request_hash"]
    assert req["id"] == identity and read(directory / "result.json") == actual
    messages, schema = query(case, role)
    assert (
        payload["messages"] == messages
        and payload["response_format"]["json_schema"]["schema"] == schema
    )
    assert (
        payload["model"] == "Qwen/Qwen3-8B"
        and payload["chat_template_kwargs"]["enable_thinking"] is False
    )
    assert decode(case, role, actual) == result
    raw = read(directory / "wire_request.json")
    import base64
    import hashlib

    body = base64.b64decode(raw["body_b64"], validate=True)
    assert json.loads(body) == payload and hashlib.sha256(body).hexdigest() == raw["body_sha256"]
    return actual["usage"]["total_tokens"]


def measure(cases, observations, archived, labels):
    output = {}
    scores = {
        arm: {kind: [] for kind in TASKS}
        for arm in (*ROLES, ORDINARY, EXTERNAL_ARM, "reviewed_direct")
    }
    supports = Counter()
    for case, pair in zip(cases, observations, strict=True):
        key = case["source"]
        variants = {
            **archived[key],
            **{role: row["predictions"] for role, row in pair.items()},
            "reviewed_direct": case["source_review"],
        }
        for arm, found in variants.items():
            for kind, task in TASKS.items():
                expected = case["source_review"][kind]
                item = found[kind]
                score = grade_view(
                    DATASET,
                    case["views"][kind],
                    labels[key][task],
                    item["answer"],
                    item["evidence"],
                )
                scores[arm][kind].append(
                    {
                        "source": key,
                        "view": task,
                        "grade": score["grade"],
                        "official_evidence_f1": score["evidence_f1"],
                        "evidence_after_correct_label": score["grade"] * score["evidence_f1"],
                    }
                )
                supports[(arm, kind)] += item["answer"] == expected["answer"] and set(
                    expected["evidence"]
                ) <= set(item["evidence"])
    for arm, tasks in scores.items():
        output[arm] = {
            k: {
                "correct": int(sum(r["grade"] for r in rows)),
                "evidence_f1": mean(r["official_evidence_f1"] for r in rows),
                "evidence_after_correct_label": mean(
                    r["evidence_after_correct_label"] for r in rows
                ),
                "reviewed_witness_matches": supports[arm, k],
            }
            for k, rows in tasks.items()
        }

    def rows(arm):
        return [row for kind in TASKS for row in scores[arm][kind]]

    return output, {
        control: paired_source_effect(rows(control), rows("synthesized"))
        for control in ("fixed", "direct_reader")
    }


def run(dispatch):
    binding, cases, prior = archive()
    out = HOME / digest(binding)
    immutable_json(out / "binding.json", binding)
    immutable_json(out / "case_material.json", cases)
    if (out / "terminal.json").exists():
        print(json.dumps(read(out / "terminal.json"), sort_keys=True), flush=True)
        return
    if not dispatch:
        assert not POINTER.exists() or read(POINTER)["status"] != "running"
        write_status(out, {"status": "prepared", "planned": binding["new_executor_cells"]}, POINTER)
        print(
            json.dumps(
                {
                    "artifact_root": str(out.relative_to(ROOT)),
                    "planned": binding["new_executor_cells"],
                    "states": binding["state_count"],
                }
            )
        )
        return
    assert ROOT / read(POINTER)["artifact_root"] == out
    for name, expected in binding["sources"].items():
        dest = out / "source_snapshot" / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists():
            with dest.open("xb") as stream:
                stream.write((ROOT / name).read_bytes())
        assert sha(dest) == expected
    with (out / "dispatch.lock").open("a") as gate:
        fcntl.flock(gate, fcntl.LOCK_EX | fcntl.LOCK_NB)
        run_id = "convergence-r5-CNI-definition-membership-" + out.name[:16]
        ledger = EvolutionLedger(
            LEDGER,
            run_id=run_id,
            sources={"train": [c["source"] for c in cases], "dev": [], "test": []},
            binding=binding,
        )
        reader = FrozenExecutor(ledger, out, binding["executor"])
        reader.readiness()
        results = []
        try:
            write_status(out, {"status": "running", "settled_pairs": 0}, POINTER)
            for case in cases:
                local = {}
                for role in ROLES:
                    identity = f"{run_id}:{digest(case['source'])}:{role}"
                    messages, schema = query(case, role)
                    raw = reader.generate(
                        identity,
                        source=case["source"],
                        purpose="skill_actor",
                        messages=messages,
                        schema=schema,
                        thinking=False,
                    )
                    preds, error = decode(case, role, raw)
                    local[role] = {
                        "physical_call_id": identity,
                        "predictions": preds,
                        "error": error,
                    }
                results.append(local)
                immutable_json(out / "paired_reads" / (digest(case["source"]) + ".json"), local)
                write_status(out, {"status": "running", "settled_pairs": len(results)}, POINTER)
                print(json.dumps({"settled_mothers": len(results)}), flush=True)
            immutable_json(out / "predictions.json", results)
            tokens = Counter()
            with sqlite3.connect(LEDGER.as_uri() + "?mode=ro", uri=True) as db:
                for case, pair in zip(cases, results, strict=True):
                    for role, row in pair.items():
                        tokens[role] += check_wire(
                            db,
                            case,
                            role,
                            row["physical_call_id"],
                            (row["predictions"], row["error"]),
                        )
                counts = dict(db.execute("select status,count(*) from calls group by status"))
                assert not counts.get("reserved")
            grade = ROOT / binding["grade_path"]
            assert sha(grade) == binding["grade_sha256"]
            labels = read(grade)
            summary, effects = measure(cases, results, prior, labels)
            whole = {
                arm: {
                    kind: sum(
                        all_rows[arm][kind]["answer"] == labels[key][task]["answer"]
                        for key, all_rows in prior.items()
                    )
                    for kind, task in TASKS.items()
                }
                for arm in (ORDINARY, EXTERNAL_ARM)
            }
            terminal = {
                "status": "settled_ContractNLI_membership_TRAIN",
                "native": summary,
                "paired": effects,
                "original_TRAIN_correct": whole,
                "new_executor_requests": binding["new_executor_cells"],
                "new_teacher_requests": 0,
                "tokens_by_role": dict(tokens),
                "mothers": len(cases),
                "states": binding["state_count"],
                "original_responses_verified": binding["original_responses_verified"],
                "decode_errors": dict(
                    Counter(role for pair in results for role, row in pair.items() if row["error"])
                ),
                "ledger": counts,
                "predictions_sha256": sha(out / "predictions.json"),
            }
            immutable_json(out / "terminal.json", terminal)
            write_status(
                out,
                {"status": terminal["status"], "terminal_sha256": sha(out / "terminal.json")},
                POINTER,
            )
            print(json.dumps(terminal, sort_keys=True), flush=True)
        except Exception:
            write_status(
                out, {"status": "failed_or_interrupted", "settled_pairs": len(results)}, POINTER
            )
            raise


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("phase", choices=("prepare", "run"))
    run(cli.parse_args().phase == "run")
