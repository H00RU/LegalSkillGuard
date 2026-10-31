"""Independent original-author accounting, only for fully completed batches.

This run-local analysis does not change the learner, select a bank, call a model,
or inspect endpoint Gold. Error strata are descriptive, not causal skill credit.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import zipfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from jsonschema import validate

from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.learning.experiment import now, read, sha
from legal_skill_guard.learning.publication import apply_differential_publication
from legal_skill_guard.learning.task_local import LOCAL_GUIDANCE_SCHEMA
from legal_skill_guard.utils.hashing import canonical_json_sha256

ARMS = ("strong_empty", "ordinary_memory", "unconditional_layout", "skill_memory")
FIELDS = ("when", "inspection", "relation_if_established", "evidence_requirement")


def aggregate(queries):
    n = len(queries)
    tp, fp, fn = (sum(q[k] for q in queries) for k in ("tp", "fp", "fn"))
    labels = sum(q["label_correct"] for q in queries)
    joint = sum(q["joint_correct"] for q in queries)
    return {
        "documents": len({q["d"] for q in queries}), "hypotheses": n,
        "label_correct": labels, "label_accuracy": labels / n,
        "evidence_tp": tp, "evidence_fp": fp, "evidence_fn": fn,
        "evidence_micro_f1_gold_non_neutral": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0,
        "joint_exact_correct": joint, "joint_exact_accuracy": joint / n,
        "nonneutral_label_and_all_evidence_correct": sum(q["joint_correct"] and q["Gold_choice"] != "NotMentioned" for q in queries),
        "correct_nm_with_empty_evidence": sum(q["joint_correct"] and q["Gold_choice"] == "NotMentioned" for q in queries),
        "false_NotMentioned": sum(q["choice"] == "NotMentioned" and q["Gold_choice"] != "NotMentioned" for q in queries),
    }


def contrast(before, after):
    old, new = ({(q["d"], q["h"]): q for q in qs} for qs in (before, after))
    assert set(old) == set(new)
    pairs = [(old[k], new[k]) for k in old]
    return {
        "before": aggregate(before), "after": aggregate(after),
        "label_fixes": [[a["d"], a["h"]] for a, b in pairs if not a["label_correct"] and b["label_correct"]],
        "label_damage": [[a["d"], a["h"]] for a, b in pairs if a["label_correct"] and not b["label_correct"]],
        "joint_fixes": [[a["d"], a["h"]] for a, b in pairs if not a["joint_correct"] and b["joint_correct"]],
        "joint_damage": [[a["d"], a["h"]] for a, b in pairs if a["joint_correct"] and not b["joint_correct"]],
        "true_original_members_gained": sum(len(set(b["spans"]) & set(b["Gold_spans"]) - set(a["spans"])) for a, b in pairs if a["Gold_choice"] != "NotMentioned"),
        "true_original_members_lost": sum(len(set(a["spans"]) & set(a["Gold_spans"]) - set(b["spans"])) for a, b in pairs if a["Gold_choice"] != "NotMentioned"),
        "new_false_NM_from_correct_non_NM": [[a["d"], a["h"]] for a, b in pairs if a["label_correct"] and a["Gold_choice"] != "NotMentioned" and b["choice"] == "NotMentioned"],
        "ordinary_tool_may_also_change_in_seen_fit_not_pure_skill_effect": True,
    }


def original_markers(row):
    parts, last = [], 0
    for i, (start, end) in enumerate(row["spans"]):
        parts.extend((row["text"][last:start], f"<SPAN {i}>", row["text"][start:end], f"</SPAN {i}>"))
        last = end
    return "".join(parts) + row["text"][last:]


def analyse(batch):
    summary_path = OUT / f"batch{batch}_summary.json"
    assert summary_path.exists(), "Never grade/report an incomplete batch"
    destination = OUT / f"monitoring/complete_B{batch}_independent_original_author_and_matched_error_audit.json"
    if destination.exists():
        old = read(destination)
        assert old["analysis_source_sha256"] == sha(__file__)
        assert all(sha(p) == digest for p, digest in old["audited_file_sha256"].items())
        print(json.dumps({"already_audited_unchanged": str(destination), "metrics": old["metrics"]}, ensure_ascii=False))
        return
    cfg_path = ROOT / "configs/contractnli_literal_fixed_static.json"
    cfg, frozen = read(cfg_path), read(cfg_path.with_suffix(".frozen.json"))
    assert frozen["config_sha256"] == sha(cfg_path)
    assert all(sha(p) == digest for p, digest in frozen["files"].items())
    paths = {str(summary_path), str(cfg_path), str(cfg_path.with_suffix(".frozen.json"))}
    summary = read(summary_path)
    packet = read(ROOT / cfg["input_packet"])
    archive_path = ROOT / cfg["source_archive"]
    assert sha(archive_path) == cfg["source_archive_sha256"]
    with zipfile.ZipFile(archive_path) as archive:
        author = json.loads(archive.read("contract-nli/train.json"))
    ids = [r["id"] for r in packet["training"] if r["batch"] == batch]
    assert ids == summary["source_ids"] and len(ids) == 6
    sources = {r["id"]: r for r in author["documents"] if r["id"] in ids}
    labels = author["labels"]
    assert labels == packet["public_hypotheses"]
    for r in packet["training"]:
        if r["id"] in ids:
            assert {k: v for k, v in r.items() if k != "batch"} == sources[r["id"]]

    tx_path = OUT / f"update_transactions/b{batch}.json"
    tx = read(tx_path)
    parent_path = OUT / f"update_transactions/b{batch - 1}.json"
    parent = read(parent_path)["publication"] if batch > 1 else []
    assert tx["actual_parent"] == parent
    teacher_dir = OUT / f"teacher/task_local_b{batch}"
    response = read(teacher_dir / "response.json")
    wire = read(teacher_dir / "wire_request.json")
    body = json.loads(wire["user_prompt"])
    assert canonical_json_sha256(wire) == response["request_sha256"]
    witnesses = [r["id"] for r in packet["training"] if r["batch"] in (batch - 1, batch)]
    assert tx["source_case_ids"] == body["supplied_original_witness_ids"] == witnesses
    assert response["value"] == tx["actual_teacher_value"]
    assert canonical_json_sha256(response["value"]) == response["response_sha256"]
    invocation = response["invocation"]
    assert response["model"] == cfg["teacher"]["model"] and not response["cache_hit"]
    assert invocation["returncode"] == 0 and invocation["attempt"] == 1 and not invocation["tool_events_detected"]
    events = read(teacher_dir / "event_log.json")
    assert canonical_json_sha256({"event_log": events["event_log"]}) == invocation["event_log_sha256"]
    agent_messages = []
    for line in events["event_log"].splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        item = event.get("item", {})
        if event.get("type") == "item.completed" and item.get("type") == "agent_message":
            agent_messages.append(item["text"])
    assert len(agent_messages) == 1 and json.loads(agent_messages[0]) == response["value"]
    published = apply_differential_publication(parent, response["value"], labels, witnesses, guidance_schema=LOCAL_GUIDANCE_SCHEMA)
    assert published == tx["publication"]
    paths.update(str(p) for p in (tx_path, teacher_dir / "response.json", teacher_dir / "wire_request.json", teacher_dir / "event_log.json"))
    if batch > 1:
        paths.add(str(parent_path))

    units, groups, raw_ids = {}, {}, []
    for stage, arms in (("before", ARMS), ("after", ("skill_memory",))):
        for arm in arms:
            key = f"{stage}/{arm}"
            groups[key], units[key] = [], {}
            for d in ids:
                choices = [OUT / f"batch{batch}_{stage}/{arm}/{d}.{suffix}.json" for suffix in ("public", "reference")]
                candidates = [p for p in choices if p.exists()]
                assert len(candidates) == 1
                path, row = candidates[0], sources[d]
                unit = read(path)
                expected_bank = (parent if stage == "before" else published) if arm == "skill_memory" else []
                assert unit["document_id"] == d and unit["arm"] == arm and unit["stage"] == f"batch{batch}_{stage}"
                assert unit["published_library"] == expected_bank
                assert canonical_json_sha256(expected_bank) == unit["published_library_sha256"]
                version = batch - (stage == "before")
                if arm == "strong_empty" or version == 0:
                    expected_state = None
                else:
                    manifest_path = ROOT / cfg["reference_training_run"] / f"evidence_models/ordinary_M{version}.manifest.json"
                    manifest = read(manifest_path)
                    expected_state = manifest["state_sha256"]
                    assert sha(manifest["path"]) == manifest["pickle_sha256"]
                    paths.add(str(manifest_path))
                trace = unit["actual_factual_trace"]
                assert trace["ordinary_model_state"] == expected_state
                raw_path = Path(unit["raw_artifact"])
                raw = read(raw_path)
                assert len(raw["calls"]) == 1 and raw["response"] == unit["response"]
                request = raw["calls"][0]["request"]
                payload = json.loads(request["messages"][1]["content"])
                assert payload["full_contract_with_original_span_markers"] == original_markers(row)
                assert list(payload["hypotheses"]) == list(labels)
                assert set(payload) == {"full_contract_with_original_span_markers", "hypotheses", "output_contract", "ordinary_source_evidence_tool"}
                for name in ("model", "temperature", "top_p", "top_k", "max_tokens", "seed"):
                    assert request[name] == cfg["generation"][name]
                valid = unit["response"]["finish_reason"] == "stop"
                answer = json.loads(unit["response"]["content"]) if valid else {}
                if valid:
                    validate(answer, request["response_format"]["json_schema"]["schema"])
                    assert answer == unit["parsed"] and set(answer) == set(labels)
                assert valid == unit["public_valid"]
                for h, label in labels.items():
                    question = payload["hypotheses"][h]
                    relevant = [s for s in expected_bank if h in s["hypothesis_ids"]]
                    projection = [{"id": s["id"], "guidance": {k: s["guidance"][k] for k in FIELDS}} for s in relevant]
                    assert question["original_hypothesis"] == label["hypothesis"]
                    assert question["original_public_short_description"] == label["short_description"]
                    assert question["applicable_published_skills"] == projection
                    candidates = None if trace["proposals"] is None else trace["proposals"]["by_hypothesis"][h]["candidates"]
                    assert question["fallible_evidence_candidates"] == candidates
                    gold = row["annotation_sets"][0]["annotations"][h]
                    a = answer[h] if valid else {"choice": None, "spans": [], "used_skill_ids": [], "reason": None}
                    gs, ps = set(gold["spans"]), set(a["spans"])
                    assert all(type(i) is int and 0 <= i < len(row["spans"]) for i in ps | gs)
                    nn = gold["choice"] != "NotMentioned"
                    assert bool(gs) == nn
                    assert set(a["used_skill_ids"]) <= {s["id"] for s in relevant}
                    cs = {c["original_span_index"] for c in candidates or []}
                    record = {
                        "d": d, "h": h, "Gold_choice": gold["choice"], "Gold_spans": sorted(gs),
                        "choice": a["choice"], "spans": sorted(ps), "reason": a["reason"],
                        "label_correct": valid and a["choice"] == gold["choice"],
                        "joint_correct": valid and a["choice"] == gold["choice"] and ps == gs,
                        "tp": len(gs & ps) if nn else 0, "fp": len(ps - gs) if nn else 0, "fn": len(gs - ps) if nn else 0,
                        "candidate_members": sorted(cs), "all_Gold_members_in_candidates": bool(gs) and gs <= cs,
                        "delivered_skill_ids": [s["id"] for s in relevant], "used_skill_ids": a["used_skill_ids"],
                        "skill_use_is_public_report_not_faithful_attention_or_causal_credit": True,
                    }
                    stored = next(q for q in unit["queries"] if q["hypothesis_id"] == h)
                    assert stored["gold"] == gold and stored["prediction"] == (answer[h] if valid else None)
                    assert stored["label_correct"] == record["label_correct"] and stored["joint_exact"] == record["joint_correct"]
                    groups[key].append(record)
                units[key][d] = unit
                paths.update((str(path), str(raw_path)))
                raw_ids.append(unit["response"]["raw_id"])
            manual = aggregate(groups[key])
            recorded = summary[stage][arm]
            for name, value in manual.items():
                if name in recorded:
                    assert math.isclose(recorded[name], value, abs_tol=1e-12), (key, name, recorded[name], value)
    if batch > 1:
        for d in ids:
            proposals = units["before/ordinary_memory"][d]["actual_factual_trace"]["proposals"]
            assert all(units[f"before/{a}"][d]["actual_factual_trace"]["proposals"] == proposals for a in ("skill_memory", "unconditional_layout"))

    metrics = {k: aggregate(qs) for k, qs in groups.items()}
    comparisons = {a: contrast(groups[f"before/{a}"], groups["before/skill_memory"]) for a in ARMS if a != "skill_memory"}
    residuals = [q for q in groups["after/skill_memory"] if not q["joint_correct"]]
    all_paths = {**frozen["files"], **{p: sha(p) for p in paths}}
    result = {
        "at": now(), "run_id": cfg["run_id"], "batch": batch,
        "complete_original_training_source_ids": ids,
        "looked_up_original_Gold_source_ids": ids,
        "logical_units": len(raw_ids), "distinct_native_raw_ids": len(set(raw_ids)),
        "analysis_source_sha256": sha(__file__), "audited_file_sha256": all_paths,
        "independent_original_author_source_manual_sets_and_summary_match": True,
        "all_actual_wire_source_hypotheses_scoped_semantics_decode_and_raw_identity_checked": True,
        "teacher_actual_single_no_tools_return_and_complete_publication_replayed": True,
        "teacher_witness_ids": witnesses, "teacher_usage": invocation["usage"],
        "publication_counts": dict(Counter(op["operation"] for op in tx["actual_teacher_value"]["operations"])),
        "metrics": metrics, "first_encounter_matched_contrasts": comparisons,
        "seen_update_contrast_not_pure_skill_effect": contrast(groups["before/skill_memory"], groups["after/skill_memory"]),
        "after_residuals_not_silently_repaired_or_gated": residuals,
        "all_query_records": groups,
        "no_endpoint_Gold_generation_teacher_or_live_frozen_edits": True,
        "posthoc_error_strata_not_independent_legal_oracle_or_single_skill_causal_effect": True,
    }
    RunStore.immutable_json(destination, result)
    print(json.dumps({"receipt": str(destination), "metrics": metrics, "after_residual_queries": len(residuals), "distinct_native_raw_ids": len(set(raw_ids))}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=int, choices=(1, 2, 3, 4), required=True)
    analyse(parser.parse_args().batch)
