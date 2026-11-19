"""Counterfactual recovery of complete CNI records from archived length cutoffs."""

import json
import re
import sqlite3
from collections import Counter
from pathlib import Path

from experiments.convergence_formal_curves import pointer as dev_pointer
from experiments.convergence_formal_train_fit import pointer as fit_pointer
from experiments.convergence_pilot_b0 import HANDOFF, LEDGER, ROOT, read, sha
from experiments.convergence_revision5_cni_survival_scope import (
    ARMS,
    BOOTSTRAP,
    DATASET,
    FIRST,
    TrainingJournal,
    bound_stage,
    load_roster,
    response,
    verify,
    verify_prediction,
    verify_request,
    verify_wire,
)
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import decode_answer, grade_view, restore_enum_transport
from legal_skill_guard.skill_evolution.objects import digest


SPACE = re.compile(r"[ \t\r\n]*")
VALUE_START = re.compile(r'[ \t\r\n]*\{[ \t\r\n]*"value"[ \t\r\n]*:[ \t\r\n]*\{[ \t\r\n]*')
RUNTIME = "legal_skill_guard/paired_interfaces/control_programs.py"
TABLE = (
    ROOT / "reports/legal_skill_convergence_20261117/paper/tables/"
    "REVISION5_CNI_PARTIAL_WIRE_20261119.json"
)


def unique_pairs(pairs):
    result = dict(pairs)
    if len(result) != len(pairs):
        raise ValueError("Duplicate JSON member")
    return result


def reject_constant(value):
    raise ValueError(f"Invalid JSON constant {value}")


def completed_members(content, names):
    """Read existing object boundaries and retain no data from the cutoff member."""
    if not (start := VALUE_START.match(content)):
        return {}
    decoder = json.JSONDecoder(object_pairs_hook=unique_pairs, parse_constant=reject_constant)
    records = {}
    cursor = start.end()
    while cursor < len(content):
        if content[cursor] == "}":
            # A length stop can arrive after the inner closing brace.
            if re.fullmatch(r"\}\s*\}?\s*", content[cursor:]):
                return records
            raise ValueError("Unexpected data after the native object")
        try:
            task, cursor = decoder.raw_decode(content, cursor)
        except json.JSONDecodeError:
            break
        if not isinstance(task, str) or task not in names or task in records:
            raise ValueError("Unknown or duplicate native hypothesis")
        cursor = SPACE.match(content, cursor).end()
        if cursor == len(content):
            break
        if content[cursor] != ":":
            raise ValueError("Expected ':' after the native hypothesis")
        cursor = SPACE.match(content, cursor + 1).end()
        if cursor < len(content) and content[cursor] != "{":
            raise ValueError("Expected a native answer object")
        try:
            record, cursor = decoder.raw_decode(content, cursor)
        except json.JSONDecodeError:
            break
        records[task] = record
        cursor = SPACE.match(content, cursor).end()
        if cursor < len(content) and content[cursor] == ",":
            cursor = SPACE.match(content, cursor + 1).end()
            if cursor < len(content) and content[cursor] != '"':
                raise ValueError("Expected a hypothesis after ','")
        elif cursor < len(content) and content[cursor] != "}":
            raise ValueError("Expected the next member or the end of the native object")
    return records


def recover(raw, payload, views, native):
    if raw["finish_reason"] != "length":
        return native
    assert not any(row["handled"] for row in native.values())
    schema = payload["response_format"]["json_schema"]["schema"]
    fields = schema["properties"]["value"]["properties"]
    assert set(fields) == set(views) == set(native)
    updates = {}
    for task, row in completed_members(raw["content"], fields).items():
        restored, _ = restore_enum_transport(row, fields[task])
        answer, evidence = decode_answer(DATASET, views[task], restored)
        updates[task] = {
            **native[task],
            "handled": True,
            "answer": answer,
            "evidence_sentence_ids": evidence,
            "reason": None,
        }
    return native | updates


def checked_result(db, source, result, raw_and_wire, *, dev=False):
    key = source["key"]
    if dev:
        ids = set()
        verify_wire(db, key, result, ids)
        (identity,) = ids
        if identity not in raw_and_wire:
            raw = json.loads(db.execute("select result from calls where id=?", (identity,)).fetchone()[0])
            payload = read(Path(raw["artifact_directory"]) / "request.json")["payload"]
    else:
        identity = verify_prediction(db, key, result)
        if identity not in raw_and_wire:
            raw, payload = response(db, key, identity)
    views = {v["id"]: v for v in source["views"]}
    if identity not in raw_and_wire:
        verify_request(payload, views)
        raw_and_wire[identity] = (raw, payload)
    raw, payload = raw_and_wire[identity]
    return identity, recover(raw, payload, views, result["native"])


def score(source, annotations, native):
    totals = Counter(tasks=len(source["views"]))
    for view in source["views"]:
        task = view["id"]
        entry = native[task]
        if not entry["handled"]:
            continue
        grade = grade_view(
            DATASET, view, annotations[task], entry["answer"], entry["evidence_sentence_ids"]
        )
        totals["handled"] += 1
        totals["correct"] += grade["correct"]
        totals["evidence_f1_sum"] += grade["evidence_f1"]
    return totals


def changed_case(source, before, after, grade):
    counts = score(source, grade, after)
    assert not any(row["handled"] for row in before.values())
    return {
        "native_tasks_in_cutoff_response": counts["tasks"],
        "recovered_task_records": counts["handled"],
        "correct_recovered_labels": counts["correct"],
        "recovered_records_with_100_or_more_citations": sum(
            len(row["evidence_sentence_ids"]) >= 100 for row in after.values() if row["handled"]
        ),
        "recoveries_by_hypothesis": {
            task: {"correct": row["answer"] == grade[task]["answer"],
                   "citation_count": len(row["evidence_sentence_ids"])}
            for task, row in after.items()
            if row["handled"]
        },
    }


def train(db, known, study, roster):
    inventory = {
        s["key"]: s for batch in roster for s in batch if s["dataset"] == DATASET
    }
    assert len(inventory) == 24 and all(s["project_split"] == "train" for s in inventory.values())
    _, binding, _ = bound_stage(FIRST)
    grade = ROOT / binding["native_grade_paths"][DATASET]
    assert sha(grade) == binding["native_grade_sha256"][str(grade.relative_to(ROOT))]
    annotations = read(grade)
    journal = TrainingJournal(ROOT / read(BOOTSTRAP)["artifact_root"], study, roster)
    proposals, terminals = [], {}
    for batch in (3, 4, 5):
        stage, _, terminal = bound_stage(fit_pointer(batch))
        terminals[str(batch)] = sha(stage / "terminal.json")
        matched = read(stage / "matched_decisions.json")
        assert digest(matched) == terminal["matched_decisions_sha256"]
        for arm in ARMS:
            decision = matched["teacher"][arm][DATASET]
            if decision["native_utility_delta"] <= 0:
                continue
            path = stage / "candidates" / arm / DATASET
            assert read(path / "decision.json") == decision
            current = read(path / "measurements.json")["predictions"]
            prior = read(path / "prior_TRAIN_regression.json")
            assert digest(current) == decision["predictions_sha256"]
            assert digest(prior) == decision["earlier_TRAIN_regression"]["evidence_sha256"]
            totals = {scope: {p: Counter() for p in ("before", "candidate", "before_replay", "candidate_replay")}
                      for scope in ("current", "earlier")}
            affected = []
            observed = journal._observations(arm, batch)
            for key, candidate in (prior["candidate"] | current).items():
                scope = "current" if key in current else "earlier"
                incumbent = prior["before"].get(key)
                if key in current:
                    saved = read(journal.directory(arm, batch) / "predictions" / (digest(key) + ".json"))
                    assert digest(saved) == observed["predictions"][key]
                    incumbent = saved["result"]
                source = inventory[key]
                for side, row in (("before", incumbent), ("candidate", candidate)):
                    identity, replay = checked_result(db, source, row, known)
                    totals[scope][side].update(score(source, annotations[key], row["native"]))
                    totals[scope][side + "_replay"].update(score(source, annotations[key], replay))
                    if replay != row["native"]:
                        affected.append({"scope": scope, "side": side, "physical_response_sha256": digest(identity),
                                         **changed_case(source, row["native"], replay, annotations[key])})
            earlier = totals["earlier"]
            perfect_cutoff_credit = sum(
                row["native_tasks_in_cutoff_response"] for row in affected
                if row["scope"] == "earlier" and row["side"] == "candidate"
            )
            entry = {
                "batch": batch,
                "arm": arm,
                "archived_selection": decision["selected"],
                "affected_responses": affected,
                "metrics": {k: {p: brief(v) for p, v in c.items()} for k, c in totals.items()},
            }
            if perfect_cutoff_credit:
                entry["upper_bound_if_all_cutoff_tasks_correct"] = (
                    earlier["candidate"]["correct"] + perfect_cutoff_credit
                )
            for suffix, label in (("", "archived_selection"), ("_replay", "replayed_selection")):
                current_gain = delta(totals["current"], suffix)
                retention_gain = delta(totals["earlier"], suffix)
                selection = "candidate" if current_gain > 0 and retention_gain >= 0 else "incumbent"
                if not suffix:
                    assert selection == decision["selected"]
                    assert abs(current_gain - decision["native_utility_delta"]) < 1e-12
                    assert abs(retention_gain - prior["native_utility_delta"]) < 1e-12
                entry[label] = selection
            proposals.append(entry)
    return proposals, terminals


def brief(totals):
    return {
        "tasks": totals["tasks"],
        "handled": totals["handled"],
        "correct": totals["correct"],
        "accuracy": totals["correct"] / totals["tasks"],
        "evidence_f1_over_all_tasks": totals["evidence_f1_sum"] / totals["tasks"],
    }


def delta(totals, suffix):
    a, b = (totals[p + suffix] for p in ("before", "candidate"))
    assert a["tasks"] == b["tasks"]
    return (b["correct"] - a["correct"]) / a["tasks"]


def dev(db, known, study, checkpoint):
    stage8, binding8, terminal8 = bound_stage(dev_pointer(8))
    stage1 = ROOT / read(HANDOFF / "run_state.json")["B1_fixed_DEV"]["artifact_root"]
    binding1, terminal1 = (read(stage1 / name) for name in ("binding.json", "terminal.json"))
    assert stage1.name == digest(binding1) and not terminal1["TEST_opened"]
    assert all(sha(stage1 / "source_snapshot" / p) == h for p, h in binding1["source_sha256"].items())
    data = ROOT / binding8["b0_dev_data_root"]
    roster = read(data / "public_DEV_sources.json")
    assert digest(roster) == read(data / "binding.json")["DEV_public_sha256"] == study["DEV_public_sha256"]
    sources = [s for s in roster if s["dataset"] == DATASET]
    assert len(sources) == 16 and all(s["project_split"] == "dev" for s in sources)
    grade = study["grading_paths"][DATASET]
    assert "dev" in Path(grade).parts and sha(ROOT / grade) == study["grading_file_sha256"][grade]
    annotations = read(ROOT / grade)
    receipt = ROOT / read(HANDOFF / "B1_CNI_DEV_excess_evidence_20261118.json")["receipt"]
    records, stages = [], {}
    for batch, stage, binding, terminal in ((1, stage1, binding1, terminal1), (8, stage8, binding8, terminal8)):
        stages[str(batch)] = sha(stage / "terminal.json")
        assert binding["checkpoint_binding_sha256"] == digest(study)
        runtime = stage / "source_snapshot" / RUNTIME
        assert sha(runtime) == binding["source_sha256"][RUNTIME]
        assert "Predicate response is incomplete; do not repair a partial result" in runtime.read_text()
        for arm in ARMS:
            folder = checkpoint / "dev" / f"B{batch}" / arm
            seal = verify(read(folder / "prediction_seal.json"), "prediction_seal_sha256")
            cell = verify(read(folder / "scores.json"), "cell_sha256")
            assert seal["task_sha256"] == digest(read(folder / "task.json"))
            assert cell["partition"] == "dev" and cell["cell_sha256"] == terminal["cell_sha256"][arm]
            assert seal["prediction_seal_sha256"] == cell["prediction_seal_sha256"]
            before, after, cases = Counter(), Counter(), []
            for source in sources:
                key = source["key"]
                saved = read(folder / "predictions" / (digest(key) + ".json"))
                assert seal["predictions_sha256"][key] == digest(saved) and saved["source"] == key
                assert saved["library_sha256"] == cell["libraries"][DATASET]
                actual = saved["result"]["native"]
                identity, replay = checked_result(db, source, saved["result"], known, dev=True)
                before.update(score(source, annotations[key], actual))
                after.update(score(source, annotations[key], replay))
                if actual != replay:
                    cases.append({
                        "previously_reported_length_cutoff": identity == read(receipt)["physical_call_id"],
                        "physical_response_sha256": digest(identity),
                        **changed_case(source, actual, replay, annotations[key]),
                    })
            records.append({"batch": batch, "arm": arm, "archived": brief(before),
                            "prefix_replay": brief(after), "affected_responses": cases})
    return records, stages, sha(receipt)


def result():
    checkpoint = ROOT / read(BOOTSTRAP)["artifact_root"]
    study = read(checkpoint / "binding.json")
    assert checkpoint.name == digest(study)
    known = {}
    with sqlite3.connect(LEDGER.as_uri() + "?mode=ro", uri=True) as db:
        ledger = dict(db.execute("select status,count(*) from calls group by status"))
        assert not ledger.get("reserved")
        train_rows, fit_stages = train(db, known, study, load_roster(study))
        n_train = len(known)
        dev_rows, dev_stages, previous_dev = dev(db, known, study, checkpoint)
    return {
        "status": "settled_archived_CNI_complete_record_replay",
        "read_scope": "B3-B5 native-positive proposals; B1 and B8 DEV for ordinary and PARSE",
        "archived_TRAIN_responses_verified": n_train,
        "archived_DEV_responses_verified": len(known) - n_train,
        "proposals": train_rows,
        "DEV": dev_rows,
        "TRAIN_terminals_sha256": fit_stages,
        "DEV_terminals_sha256": dev_stages,
        "previous_B1_length_audit_sha256": previous_dev,
        "runner_sha256": sha(Path(__file__)),
        "scoring": "missing tasks score zero in this replay; recovered evidence uses original native scorer",
        "same_partial_wire_rule_for_all_reviewed_conditions": True,
        "new_requests": 0,
        "continuous_ledger": ledger,
        "TEST_opened": False,
    }


if __name__ == "__main__":
    immutable_json(TABLE, result())
