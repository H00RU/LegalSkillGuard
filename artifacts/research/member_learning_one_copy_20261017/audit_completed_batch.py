"""Read-only original-author/wire audit of a CLOSED batch, without generation.

This is the analysis record for this development run, not another training path.
Use --with-after only after the whole after phase has been scored by the runner.
"""

import argparse
import hashlib
import json
import math
import shutil
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import validate

ROOT = Path(__file__).resolve().parents[3]
RUN_ID = "legal_contractnli_member_learning_one_copy_20261017_run03"
CONFIG = ROOT / "configs/contractnli_member_learning_one_copy_20261017.json"
OUT = ROOT / "runs" / RUN_ID


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def canonical(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
        separators=(",", ":")).encode()).hexdigest()


def marked(source):
    result, end = [], 0
    for i, (start, stop) in enumerate(source["spans"]):
        result.extend((source["text"][end:start], f"<SPAN {i}>",
            source["text"][start:stop], f"</SPAN {i}>"))
        end = stop
    return "".join(result) + source["text"][end:]


def metrics(questions):
    assert questions
    nn = [q for q in questions if q["gold"]["choice"] != "NotMentioned"]
    tp, fp, fn = (sum(q[k] for q in nn) for k in ("tp", "fp", "fn"))
    return {"questions": len(questions), "accuracy": sum(q["correct"] for q in questions) / len(questions),
        "Gold_NN_micro_F1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0,
        "Gold_NN_query_mean_F1": sum(q["f1"] for q in nn) / len(nn) if nn else None,
        "joint_accuracy": sum(q["joint"] for q in questions) / len(questions),
        "gold_non_neutral_questions": len(nn), "tp": tp, "fp": fp, "fn": fn,
        "fully_correct_non_NM": sum(q["joint"] for q in nn),
        "class_accuracy": {label: {"n": sum(q["gold"]["choice"] == label for q in questions),
            "correct": sum(q["correct"] and q["gold"]["choice"] == label for q in questions)}
            for label in ("Entailment", "Contradiction", "NotMentioned")}}


def audit_units(units, author, labels, cfg):
    questions, receipts, raw_ids = [], [], []
    for unit in units:
        d = unit["document_id"]
        source = author[d]
        payload, raw = read(unit["payload"]), read(unit["raw_artifact"])
        assert len(raw["calls"]) == 1 and raw["transport_error"] is None
        assert raw["response"] == unit["response"]
        request = raw["calls"][0]["request"]
        assert request["messages"] == payload["messages"]
        assert request["response_format"]["json_schema"]["schema"] == payload["schema"]
        assert all(request[k] == cfg["generation"][k] for k in
            ("model", "seed", "temperature", "top_p", "top_k", "max_tokens"))
        assert canonical(payload["bank"]) == payload["bank_sha256"] == unit["bank_sha256"]
        body = json.loads(request["messages"][1]["content"])
        assert body["full_contract_with_original_span_markers"] == marked(source)
        assert set(body["hypotheses"]) == set(labels)
        expected = [{"hypothesis_ids": s["hypothesis_ids"], "criterion": s["guidance"]["evidence_criterion"]}
            for s in payload["bank"] if s["guidance"].get("evidence_criterion") is not None]
        assert body.get("evidence_selection_criteria", []) == expected
        assert unit["response"]["finish_reason"] == "stop" and unit["native_schema_valid"]
        answer = json.loads(raw["response"]["content"])
        validate(answer, payload["schema"])
        assert set(answer) == set(labels)
        gold = source["annotation_sets"][0]["annotations"]
        scored = {q["hypothesis_id"]: q for q in unit["queries"]}
        for h in labels:
            g, p = gold[h], answer[h]
            gs, ps = set(g["spans"]), set(p["spans"])
            assert all(type(i) is int and 0 <= i < len(source["spans"]) for i in ps | gs)
            assert bool(gs) == (g["choice"] != "NotMentioned")
            tp, fp, fn = len(gs & ps), len(ps - gs), len(gs - ps)
            q = {"source_id": d, "hypothesis_id": h, "gold": g, "answer": p,
                "correct": p["choice"] == g["choice"],
                "joint": p["choice"] == g["choice"] and ps == gs,
                "tp": tp, "fp": fp, "fn": fn,
                "f1": 2 * tp / (2 * tp + fp + fn) if gs else None}
            original = scored[h]
            assert original["gold"] == g and original["prediction"] == p
            assert all(original[k] == q[v] for k, v in
                (("label_correct", "correct"), ("joint_exact", "joint"),
                 ("evidence_tp", "tp"), ("evidence_fp", "fp"), ("evidence_fn", "fn")))
            questions.append(q)
        raw_ids.append(raw["response"]["raw_id"])
        receipts.append({"source_id": d, "arm": unit["condition"], "raw_id": raw_ids[-1],
            "raw_sha256": sha(unit["raw_artifact"]), "payload_sha256": sha(unit["payload"]),
            "bank_sha256": unit["bank_sha256"], "criteria": len(expected),
            "scoped_hypotheses": sorted({h for s in payload["bank"] for h in s["hypothesis_ids"]}),
            "prompt_tokens": raw["response"]["prompt_tokens"],
            "completion_tokens": raw["response"]["completion_tokens"]})
    assert len(raw_ids) == len(set(raw_ids))
    return questions, receipts


def compare(before, after):
    a, b = ({(q["source_id"], q["hypothesis_id"]): q for q in group} for group in (before, after))
    assert a.keys() == b.keys() and a
    changes = [{"source_id": k[0], "hypothesis_id": k[1], "gold": a[k]["gold"],
        "before": a[k]["answer"], "after": b[k]["answer"],
        "label_fixed": not a[k]["correct"] and b[k]["correct"],
        "label_broken": a[k]["correct"] and not b[k]["correct"],
        "joint_fixed": not a[k]["joint"] and b[k]["joint"],
        "joint_broken": a[k]["joint"] and not b[k]["joint"]}
        for k in a if a[k]["answer"] != b[k]["answer"]]
    return {"before": metrics(before), "after": metrics(after),
        "label_fixes": sum(c["label_fixed"] for c in changes),
        "label_damages": sum(c["label_broken"] for c in changes),
        "joint_fixes": sum(c["joint_fixed"] for c in changes),
        "joint_damages": sum(c["joint_broken"] for c in changes),
        "by_hypothesis": {h: {"before": metrics([q for q in before if q["hypothesis_id"] == h]),
            "after": metrics([q for q in after if q["hypothesis_id"] == h])}
            for h in dict.fromkeys(q["hypothesis_id"] for q in before)},
        "changed_public_answers": changes}


def audit_teacher_packet(batch, author, publication):
    from legal_skill_guard.learning.member_contract import WRITER, decode_teacher_source
    from legal_skill_guard.learning.packing import expand

    packet = read(OUT / f"learning_inputs/update_b{batch}.json")
    wire = read(OUT / f"teacher/update_b{batch}/wire_request.json")
    response = read(OUT / f"teacher/update_b{batch}/response.json")
    assert json.loads(wire["user_prompt"]) == packet and wire["system_prompt"] == WRITER
    assert not response["cache_hit"] and not response["invocation"]["tool_events_detected"]
    assert response["value"] == publication["delta"]
    validate(response["value"], wire["output_schema"])
    body = expand(packet["body"])
    assert body["current_parent_library"] == publication["parent"]
    source_ids = []
    for encoded in body["complete_cumulative_original_TRAIN_sources_and_Gold"]:
        d = encoded["id"]
        source_ids.append(d)
        assert decode_teacher_source(encoded) == {k: author[d][k] for k in ("id", "text", "spans")}
        assert encoded["original_annotations"] == author[d]["annotation_sets"][0]["annotations"]
    history = []
    for b in range(1, batch + 1):
        history.extend(u for u in read(OUT / f"b{b}_before_complete.json")["units"] if u["condition"] == "skills")
        if b < batch:
            history.extend(read(OUT / f"scored_phases/b{b}_after_all_seen.json")["units"])
    parent_sha = canonical(publication["parent"])
    latest = {u["document_id"]: u for u in history if u["bank_sha256"] == parent_sha}
    actual = body["actual_own_public_observations"]
    assert len(actual) == len(source_ids) == len(latest)
    supplied_ids = set()
    for observation in actual:
        original = latest[observation["document_id"]]
        supplied_ids.add(observation["actual_native_raw_id"])
        assert observation["actual_native_raw_id"] == original["response"]["raw_id"]
        assert observation["actual_public_answer"] == json.loads(original["response"]["content"])
        assert observation["actual_native_artifact_sha256"] == sha(original["raw_artifact"])
        assert observation["actual_input_payload_sha256"] == sha(original["payload"])
    excluded = [u for u in history if u["response"]["raw_id"] not in supplied_ids]
    assert len(history) == body["learning_response_window"]["archived_own_answers"]
    assert all(u["response"]["raw_id"] not in wire["user_prompt"] for u in excluded)
    return {"wire_sha256": sha(OUT / f"teacher/update_b{batch}/wire_request.json"),
        "actual_invocation": response["invocation"]["budget_reservation"]["sequence"],
        "original_sources_Gold_latest_own_answers_and_actual_teacher_wire_equal": True,
        "source_ids": source_ids, "available_own_history_answers": len(history),
        "actually_supplied_current_parent_answers": len(actual),
        "older_archived_own_answers_not_in_teacher_input": [{"source_id": u["document_id"],
            "stage": u["stage"], "raw_id": u["response"]["raw_id"], "bank_sha256": u["bank_sha256"]}
            for u in excluded],
        "missing_temporal_comparison_is_not_proven_unique_cause_of_bad_performance": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", type=int, choices=range(1, 5), required=True)
    parser.add_argument("--with-after", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    cfg, frozen = read(CONFIG), read(CONFIG.with_suffix(".frozen.json"))
    assert frozen["config_sha256"] == sha(CONFIG)
    assert all(sha(p) == h for p, h in frozen["files"].items())
    with zipfile.ZipFile(ROOT / cfg["source_archive"]) as archive:
        data = json.loads(archive.read("contract-nli/train.json"))
    author, labels = {d["id"]: d for d in data["documents"]}, data["labels"]
    ids = cfg["training_ids"][8 * (args.batch - 1):8 * args.batch]
    phase = read(OUT / f"b{args.batch}_before_complete.json")
    groups, wires = {}, []
    for arm in ("strong_empty", "ordinary", "skills"):
        units = [u for u in phase["units"] if u["condition"] == arm]
        assert len(units) == 8 and {u["document_id"] for u in units} == set(ids)
        groups[arm], receipt = audit_units(units, author, labels, cfg)
        wires.extend(receipt)
        independent, stored = metrics(groups[arm]), phase["metrics"][arm]
        for key, stored_key in (("accuracy", "label_accuracy"),
                ("Gold_NN_micro_F1", "evidence_micro_f1_gold_non_neutral"),
                ("joint_accuracy", "joint_exact_accuracy")):
            assert math.isclose(independent[key], stored[stored_key], abs_tol=1e-12)
    assert len({w["raw_id"] for w in wires}) == 24
    parent = read(OUT / f"publications/b{args.batch}.json")["parent"]
    scope = {h for s in parent for h in s["hypothesis_ids"]}
    prequential = compare(groups["strong_empty"], groups["skills"])
    report = {"at": datetime.now(timezone.utc).isoformat(), "run_id": RUN_ID, "batch": args.batch,
        "source_ids": ids, "all_frozen_bindings_unchanged": len(frozen["files"]),
        "all24_closed_before_wires_source_schema_original_Gold_and_scores_verified": True,
        "before_metrics": {arm: metrics(q) for arm, q in groups.items()},
        "prequential_skill_vs_empty": prequential,
        "prequential_skill_vs_ordinary": compare(groups["ordinary"], groups["skills"]),
        "parent_skill_scope": sorted(scope), "wire_receipts": wires,
        "no_new_native_teacher_calls": True,
        "same_development_episode_not_independent_learning_or_official_TEST": True}
    if scope:
        for name, include in (("inside_declared_parent_scope", True), ("outside_declared_parent_scope", False)):
            a, b = ([q for q in groups[arm] if (q["hypothesis_id"] in scope) == include]
                for arm in ("strong_empty", "skills"))
            if a:
                report[name] = compare(a, b)
    publication = read(OUT / f"publications/b{args.batch}.json")
    edits = Counter(o["operation"] for o in publication["delta"]["operations"])
    report["actual_publication"] = {"operations": dict(edits),
        "parent_records": len(parent), "published_records": len(publication["publication"]),
        "scope": sorted({h for s in publication["publication"] for h in s["hypothesis_ids"]}),
        "capacity": publication["capacity"], "all_valid_edits_published_no_efficacy_admission": True}
    report["actual_teacher_packet_audit"] = audit_teacher_packet(args.batch, author, publication)
    if args.with_after:
        after_units = read(OUT / f"scored_phases/b{args.batch}_after_all_seen.json")["units"]
        seen = cfg["training_ids"][:8 * args.batch]
        assert len(after_units) == len(seen) and {u["document_id"] for u in after_units} == set(seen)
        after, after_receipts = audit_units(after_units, author, labels, cfg)
        report["after_wire_receipts"] = after_receipts
        report["current_batch_fit_parent_to_publication"] = compare(groups["skills"],
            [q for q in after if q["source_id"] in ids])
        report["all_seen_after_metrics"] = metrics(after)
        if args.batch > 1:
            previous = read(OUT / f"scored_phases/b{args.batch - 1}_after_all_seen.json")["units"]
            previous_q, _ = audit_units(previous, author, labels, cfg)
            report["old_sources_parent_to_publication"] = compare(previous_q,
                [q for q in after if q["source_id"] not in ids])
        report["after_is_fit_and_retention_not_new_source_transfer"] = True
    from legal_skill_guard.experiment.storage import RunStore
    assert args.output.parent.resolve() == Path(__file__).parent.resolve()
    RunStore.immutable_json(args.output, report)
    name = RUN_ID + "-" + args.output.name
    copies = [Path("/media/sangfor/vdb/legal-skill-backups") / name,
        Path("/home/yndx/hhy/legal-skill-rootdisk-backups") / name]
    assert copies[0].parent.stat().st_dev != copies[1].parent.stat().st_dev
    for destination in copies:
        assert not destination.exists()
        shutil.copy2(args.output, destination)
        assert sha(destination) == sha(args.output)
    print(json.dumps({"report": str(args.output), "sha256": sha(args.output),
        "before_metrics": report["before_metrics"], "actual_publication": report["actual_publication"],
        "after_complete": args.with_after, "verified_two_filesystem_copies": [str(p) for p in copies],
        "no_new_native_teacher_calls": True}, ensure_ascii=False))


if __name__ == "__main__":
    main()
