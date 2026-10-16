"""Independent original-author membership accounting after the complete26 study.

No generation, teacher, answer rewriting, selection, or production dependency.
The mechanism strata were fixed before new-outcome scoring, not chosen here.
"""

from __future__ import annotations

import json
import zipfile
from collections import Counter
from pathlib import Path

from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.learning.experiment import now, read, sha

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
TREATMENT = "complete_master_semantic_delivery"
ARMS = ("trace_procedures", "ordinary_memory", "unconditional_layout", "strong_empty", TREATMENT)


def aggregate(rows):
    tp, fp, fn = (sum(r[k] for r in rows) for k in ("tp", "fp", "fn"))
    return {
        "documents": len({r["d"] for r in rows}), "hypotheses": len(rows),
        "label_correct": sum(r["label_correct"] for r in rows),
        "label_accuracy": sum(r["label_correct"] for r in rows) / len(rows),
        "evidence_tp": tp, "evidence_fp": fp, "evidence_fn": fn,
        "evidence_micro_f1_gold_non_neutral": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0,
        "joint_exact_correct": sum(r["joint_correct"] for r in rows),
        "joint_exact_accuracy": sum(r["joint_correct"] for r in rows) / len(rows),
        "nonneutral_label_and_all_evidence_correct": sum(r["joint_correct"] and r["Gold_choice"] != "NotMentioned" for r in rows),
        "correct_nm_with_empty_evidence": sum(r["joint_correct"] and r["Gold_choice"] == "NotMentioned" for r in rows),
        "false_NotMentioned": sum(r["choice"] == "NotMentioned" and r["Gold_choice"] != "NotMentioned" for r in rows),
    }


def contrast(before, after):
    old, new = {(r["d"], r["h"]): r for r in before}, {(r["d"], r["h"]): r for r in after}
    assert set(old) == set(new)
    pairs = [(old[k], new[k]) for k in old]
    return {
        "queries": len(pairs),
        "label_fixes": sum(not a["label_correct"] and b["label_correct"] for a, b in pairs),
        "label_damage": sum(a["label_correct"] and not b["label_correct"] for a, b in pairs),
        "joint_fixes": sum(not a["joint_correct"] and b["joint_correct"] for a, b in pairs),
        "joint_damage": sum(a["joint_correct"] and not b["joint_correct"] for a, b in pairs),
        "gained_true_original_members": sum(len((set(b["spans"]) & set(b["Gold_spans"])) - (set(a["spans"]) & set(a["Gold_spans"]))) for a, b in pairs if a["Gold_choice"] != "NotMentioned"),
        "lost_true_original_members": sum(len((set(a["spans"]) & set(a["Gold_spans"])) - (set(b["spans"]) & set(b["Gold_spans"]))) for a, b in pairs if a["Gold_choice"] != "NotMentioned"),
        "old_false_NM_queries": sum(a["choice"] == "NotMentioned" and a["Gold_choice"] != "NotMentioned" for a, _ in pairs),
        "old_false_NM_label_fixes": sum(a["choice"] == "NotMentioned" and a["Gold_choice"] != "NotMentioned" and b["label_correct"] for a, b in pairs),
        "old_false_NM_still_false_NM": sum(a["choice"] == b["choice"] == "NotMentioned" and a["Gold_choice"] != "NotMentioned" for a, b in pairs),
        "new_false_NM_from_previously_correct_non_NM": sum(a["label_correct"] and a["Gold_choice"] != "NotMentioned" and b["choice"] == "NotMentioned" for a, b in pairs),
        "before": aggregate(before), "after": aggregate(after),
    }


def analyse():
    assert read(OUT / "progress.json")["state"] == "completed", "Never analyse a partial run"
    done = read(OUT / "completion.json")
    assert (done["new_native_calls"], done["new_teacher_calls"], done["logical_historical_references_not_new_spend"]) == (26, 0, 104)
    assert read(OUT / "audits/all130_actual_wires_before_original_grading.json")["logical_observations"] == 130
    precommit_path = OUT / "monitoring/pre_outcome_complete26_delivery_mechanism_strata_and_analysis_rules.json"
    precommit = read(precommit_path)
    strata = {(r["d"], r["h"]): r for r in precommit["queries"]}
    config = read(ROOT / "configs/contractnli_source_condition_audit_completion.json")
    archive_path = ROOT / config["source_archive"]
    assert sha(archive_path) == config["source_archive_sha256"]
    with zipfile.ZipFile(archive_path) as archive:
        author = json.loads(archive.read("contract-nli/train.json"))
    sources = {r["id"]: r for r in author["documents"]}
    packet = read(ROOT / config["input_packet"])
    assert author["labels"] == packet["public_hypotheses"]
    groups, units, invalid, records = {}, {}, [], []
    for arm in ARMS:
        groups[arm], units[arm] = [], {}
        for case in precommit["cases"]:
            d = case["d"]
            unit = read(OUT / f"scored/{arm}/{d}.json")
            units[arm][d] = unit
            raw_path = Path(unit["raw_artifact"])
            raw = read(raw_path)
            assert len(raw["calls"]) == 1 and raw["response"] == unit["response"]
            wire = raw["calls"][0]["request"]
            body = json.loads(wire["messages"][1]["content"])
            source = sources[d]
            parts, last = [], 0
            for i, (a, b) in enumerate(source["spans"]):
                parts += [source["text"][last:a], f"<SPAN {i}>", source["text"][a:b], f"</SPAN {i}>"]
                last = b
            parts.append(source["text"][last:])
            assert body["full_contract_with_original_span_markers"] == "".join(parts)
            assert list(body["hypotheses"]) == list(author["labels"])
            for h, label in author["labels"].items():
                assert body["hypotheses"][h]["original_hypothesis"] == label["hypothesis"]
            for k in ("model", "temperature", "top_p", "top_k", "max_tokens", "seed"):
                assert wire[k] == config["generation"][k]
            response = unit["response"]
            valid = response["finish_reason"] == "stop"
            try:
                answer = json.loads(response["content"]) if valid else {}
                assert set(answer) == set(author["labels"])
                for a in answer.values():
                    assert a["choice"] in ("Entailment", "Contradiction", "NotMentioned")
                    assert isinstance(a["spans"], list) and all(type(i) is int and 0 <= i < len(source["spans"]) for i in a["spans"])
            except (AssertionError, ValueError, TypeError, KeyError):
                answer, valid = {}, False
            if not valid:
                invalid.append({"arm": arm, "d": d, "raw_id": response["raw_id"]})
            for h, gold in source["annotation_sets"][0]["annotations"].items():
                a = answer[h] if valid else {"choice": None, "spans": []}
                gs, ps = set(gold["spans"]), set(a["spans"])
                nn = gold["choice"] != "NotMentioned"
                groups[arm].append({
                    "d": d, "h": h, "batch": case["batch"],
                    "Gold_choice": gold["choice"], "Gold_spans": sorted(gs),
                    "choice": a["choice"], "spans": sorted(ps),
                    "label_correct": valid and a["choice"] == gold["choice"],
                    "joint_correct": valid and a["choice"] == gold["choice"] and ps == gs,
                    "tp": len(gs & ps) if nn else 0,
                    "fp": len(ps - gs) if nn else 0,
                    "fn": len(gs - ps) if nn else 0,
                })
            records.append({"arm": arm, "d": d, "raw_id": response["raw_id"], "raw_sha256": sha(raw_path)})
    assert len(records) == len({r["raw_id"] for r in records}) == 130
    metrics, mechanisms, harmful_sources = {}, {}, {}
    for cohort in ("B2", "B3", "B4", "online18", "exposed_development8"):
        subset = {a: [r for r in rs if (r["batch"] == int(cohort[1:]) if cohort.startswith("B") else r["batch"] < 5 if cohort == "online18" else r["batch"] == 5)] for a, rs in groups.items()}
        metrics[cohort] = {a: aggregate(rs) for a, rs in subset.items()}
        for arm in ARMS:
            for k, value in metrics[cohort][arm].items():
                if k != "false_NotMentioned":
                    assert abs(value - done["results"][cohort][arm][k]) < 1e-12
        mechanisms[cohort] = {}
        for stratum in sorted({r["old_input_stratum"] for r in strata.values()}):
            selected = {a: [r for r in subset[a] if r["Gold_choice"] != "NotMentioned" and strata[(r["d"], r["h"])]["old_input_stratum"] == stratum] for a in ("trace_procedures", TREATMENT)}
            if selected[TREATMENT]:
                mechanisms[cohort][stratum] = contrast(selected["trace_procedures"], selected[TREATMENT])
        mechanisms[cohort]["all_original_queries"] = contrast(subset["trace_procedures"], subset[TREATMENT])
        harmful_sources[cohort] = []
        for d in sorted({r["d"] for r in subset[TREATMENT]}):
            stats = {a: aggregate([r for r in subset[a] if r["d"] == d]) for a in ARMS}
            harmful_sources[cohort].append({"d": d, "metrics": stats})
    repeats = []
    for d in precommit["identical_entire_request_repeat_source_ids"]:
        a, b = (read(units[arm][d]["raw_artifact"]) for arm in ("trace_procedures", TREATMENT))
        assert a["calls"][0]["request"] == b["calls"][0]["request"]
        assert a["response"]["raw_id"] != b["response"]["raw_id"]
        repeats.append({"d": d, "identical_actual_full_request": True, "fresh_distinct_raw_IDs": True, "identical_public_answer_bytes": a["response"]["content"] == b["response"]["content"], "identical_reasoning_bytes": a["calls"][0]["response"]["choices"][0]["message"].get("reasoning_content") == b["calls"][0]["response"]["choices"][0]["message"].get("reasoning_content")})
    bindings = read(OUT / "terminal_parent_and_references_frozen.json")["bindings"]
    assert len(bindings) == 494 and all(sha(p) == h for p, h in bindings.items())
    value = {
        "at": now(), "analysis_source_sha256": sha(Path(__file__)), "pre_outcome_analysis_rules_sha256": sha(precommit_path),
        "completion_sha256": sha(OUT / "completion.json"), "independent_all130_original_author_source_wire_manual_membership_scores_match": True,
        "metrics": metrics, "mechanisms_Gold_non_NM_strata_and_overall": mechanisms,
        "all_source_results_not_outcome_selected": harmful_sources, "identical_request_repeats": repeats,
        "invalid_native_answers_kept_not_dropped": invalid, "raw_records": records,
        "all2210_query_rows": groups, "all494_frozen_inputs_unchanged": True,
        "not_single_skill_causal_credit_independent_learning_or_formal_test": True,
        "no_new_model_calls_or_bank_selection_or_answer_repair": True,
    }
    RunStore.immutable_json(OUT / "monitoring/complete130_independent_original_author_manual_scores_and_delivery_mechanisms.json", value)
    return {"at": value["at"], "metrics": {k: metrics[k] for k in ("online18", "exposed_development8")}, "repeats": repeats, "invalid_answers": invalid}


if __name__ == "__main__":
    print(json.dumps(analyse(), ensure_ascii=False, indent=2))
