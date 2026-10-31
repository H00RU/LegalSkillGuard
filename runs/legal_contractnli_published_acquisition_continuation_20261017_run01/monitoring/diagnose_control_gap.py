"""Completed-phase control and failure decomposition; no new model calls.

Historical ordinary answers are references, not independent repeats or new cost.
Original full text was always visible: lead coverage is NOT an oracle bound.
"""

from __future__ import annotations

import argparse
import runpy
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = runpy.run_path(str(HERE / "audit_learning.py"))
Audit, counts, contrast, resample = (BASE[k] for k in ("Audit", "counts", "contrast", "resample"))
ROOT, OUT = BASE["ROOT"], BASE["OUT"]


def decompose(rows):
    result = Counter()
    confusion = Counter()
    for r in rows:
        gold, pred = set(r["Gold_spans"]), set(r["spans"])
        lead = set(r["ordinary"]) | set(r["program"])
        result["questions"] += 1
        confusion[f'{r["Gold_choice"]}->{r["choice"]}'] += 1
        if r["Gold_choice"] == "NotMentioned":
            result["original_NM"] += 1
            result["original_NM_wrong_relation"] += not r["label_correct"]
            continue
        result["original_NN"] += 1
        result["Gold_members"] += len(gold)
        result["Gold_in_explicit_leads"] += len(gold & lead)
        result["Gold_lead_members_cited"] += len(gold & lead & pred)
        result["Gold_lead_members_omitted"] += len(gold & lead - pred)
        result["Gold_outside_leads_cited"] += len(gold & pred - lead)
        result["Gold_outside_leads_omitted"] += len(gold - lead - pred)
        result["nonGold_final_citations_inside_leads"] += len((pred - gold) & lead)
        result["nonGold_final_citations_outside_leads"] += len(pred - gold - lead)
        bucket = "correct_label" if r["label_correct"] else (
            "wrong_NotMentioned" if r["choice"] == "NotMentioned" else "wrong_E_or_C")
        result[f"NN_{bucket}_questions"] += 1
        result[f"FN_with_{bucket}"] += len(gold - pred)
        result[f"FP_with_{bucket}"] += len(pred - gold)
        result[f"TP_with_{bucket}"] += len(gold & pred)
    available = result["Gold_in_explicit_leads"]
    result["fraction_explicit_lead_Gold_cited"] = result["Gold_lead_members_cited"] / available if available else None
    return {"members_and_failure_stage": dict(result), "original_to_predicted_relation": dict(confusion),
        "full_original_source_always_available_leads_are_not_a_hard_recall_bound": True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("prefix", "retention"))
    phase = parser.parse_args().phase
    audit = Audit()
    parent = ROOT / audit.cfg["published_prefix_run"]
    early = ROOT / audit.saved(parent / "declaration.json")["config"]["prefix_feedback_run"]
    ordinary = [u for u in audit.saved(early / "complete32_native_and_original_scores.json")["units"]
        if u["condition"] == "ordinary"]
    ordinary += [u for u in audit.saved(parent / "b3_before_complete.json")["units"] if u["condition"] == "ordinary"]
    phases = {"R1_same_scored_encoding": audit.saved(OUT / "published_prefix_actual_retention.json")["matched_R1_same_encoding_reference_units"],
        "R2": audit.saved(OUT / "published_prefix_actual_retention.json")["new_units"]}
    if phase == "retention":
        last = audit.saved(OUT / "b4_before_complete.json")["units"]
        ordinary += [u for u in last if u["condition"] == "ordinary"]
        phases.pop("R1_same_scored_encoding")
        phases["R2"] += [u for u in last if u["condition"] == "skills"]
        phases["R3"] = audit.saved(OUT / "b4_all_seen_retention.json")["units"]
    n = 24 if phase == "prefix" else 32
    ids = audit.cfg["training_ids"][:n]
    assert [u["document_id"] for u in ordinary] == ids
    baseline, baseline_ids, baseline_usage = audit.units(ordinary)
    rows, raw_ids, usage = {}, set(baseline_ids), {"ordinary_historical_not_new": baseline_usage}
    for name, units in phases.items():
        assert [u["document_id"] for u in units] == ids
        current, response_ids, current_usage = audit.units(units)
        assert raw_ids.isdisjoint(response_ids)
        raw_ids |= response_ids
        rows[name], usage[name] = current, current_usage
    all_rows = {"ordinary": baseline, **rows}
    report = {"at": BASE["now"](), "phase": phase, "original_contract_count": n,
        "actual_unique_wire_ids_including_historical_references": len(raw_ids),
        "metrics": {k: counts(v) for k, v in all_rows.items()},
        "paired_vs_ordinary": {k: contrast(baseline, v) for k, v in rows.items()},
        "conditional_source_intervals_vs_ordinary": {k: resample(baseline, v, ids) for k, v in rows.items()},
        "failure_decomposition": {k: decompose(v) for k, v in all_rows.items()},
        "by_original_hypothesis": {h: {k: {"metrics": counts([r for r in v if r["hypothesis_id"] == h]),
            "failures": decompose([r for r in v if r["hypothesis_id"] == h])} for k, v in all_rows.items()}
            for h in audit.labels},
        "by_original_eight_source_group": {str(b+1): {k: counts([r for r in v if r["document_id"] in ids[8*b:8*(b+1)]])
            for k, v in all_rows.items()} for b in range(n // 8)},
        "usage_references_not_all_new_spend": usage,
        "completed_development_sources_not_independent_learning_or_official_TEST": True,
        "retention_phase_mixes_24_old_and8_new_first_encounter_controls": phase == "retention",
        "bindings": {**audit.bindings, str(Path(__file__).resolve()): BASE["sha"](Path(__file__))}}
    target = HERE / f"{phase}_matched_ordinary_gap_and_original_member_failure_decomposition.json"
    BASE["RunStore"].immutable_json(target, report)
    print({"saved": str(target), "actual_wires": len(raw_ids), "metrics": report["metrics"]})


if __name__ == "__main__":
    main()
