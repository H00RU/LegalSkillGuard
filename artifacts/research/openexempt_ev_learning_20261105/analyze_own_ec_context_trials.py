"""Read-only paired error attribution for the completed TRAIN32 diagnostics."""
from __future__ import annotations

import argparse
import collections
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from experiments.openexempt_online import native_claim_feedback
from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.learning.experiment import read, sha
from legal_skill_guard.learning.legal_namespace import (
    decode_asset_references, decode_reference, public_asset_catalog, public_catalog,
)
from legal_skill_guard.openexempt import evaluate, metrics, upstream

BASE = Path(__file__).resolve().parent
CFG = ROOT / "configs/openexempt_complete_output_utility_public_assets128_20261030_run01.json"
PARENTS = ROOT / "artifacts/research/openexempt_ev_learning_20261104/bounded_train_pilot_run01/parent_records.json"
DECODED = BASE / "own_EC_context_TRAIN32_run01"
NATIVE = BASE / "own_EC_native_context_TRAIN32_run01"


def main(include_native):
    cfg, protocol = read(CFG), read(DECODED / "protocol.json")
    rows = {(r["case_id"], r["family"]): r for r in read(ROOT / cfg["input_packet"])["rows"]}
    arms = {"original_parent": read(PARENTS), "decoded_context": read(DECODED / "scored_records.json")}
    if include_native:
        assert read(NATIVE / "terminal.json")["state"] == "completed"
        arms["native_context"] = read(NATIVE / "scored_records.json")
    ids, current = set(protocol["source_ids"]), set(protocol["current_source_ids"])
    assert len(ids) == 32 and len(current) == 16
    provenance = {str(CFG): sha(CFG), str(PARENTS): sha(PARENTS), str(__file__): sha(Path(__file__))}
    targets = {}
    for cid in ids:
        p = ROOT / cfg["grading_directory"] / f"{cid}.json"
        targets[cid] = read(p)["targets"]
        provenance[str(p)] = sha(p)
    Claim = upstream("source.pydantic_response").Claim
    matcher = upstream("evaluator").Evaluator([])
    norm = lambda a, c: (a.strip().lower(), Claim(citation=c, claim_value=0).normalized_citation)
    ec_exact, ec_predicted = {}, {}
    for cid in ids:
        ec = protocol["EC_forecasts_allowlisted_no_scores_or_targets"][str(cid)]["answer"]
        fake = {"family": "EC", "parse_error": None, "parsed": {"answer": ec},
                "score": {"invalid_format": False}}
        fb = native_claim_feedback(fake, targets[cid]["EC"])
        ec_exact[cid] = not fb["errors"]
        answer = {a.strip().lower(): cs for a, cs in ec.items()}
        pairs, used = set(), set()
        for asset in targets[cid]["EV"]:
            match = matcher._find_matching_asset_description(asset.strip().lower(), list(answer))
            if match is not None and match not in used:
                pairs.update(norm(asset, c) for c in answer[match]); used.add(match)
        pairs.update(norm(a, c) for a, cs in answer.items() if a not in used for c in cs)
        ec_predicted[cid] = pairs

    feedback, records = {}, {}
    for arm, rs in arms.items():
        assert len(rs) == 32 and {r["case_id"] for r in rs} == ids
        records[arm] = {r["case_id"]: r for r in rs}
        feedback[arm] = {}
        for r in rs:
            cid, row = r["case_id"], rows[r["case_id"], "EV"]
            raw_path = ROOT / r["raw_call_path"]
            raw = read(raw_path)
            provenance[str(raw_path)] = sha(raw_path)
            if r["parse_error"] is None:
                submission = json.loads(raw["response"]["content"])
                assert submission == r["public_label_submission"]
                values = decode_asset_references(copy.deepcopy(submission), public_asset_catalog(row))
                decoded = {a: [{"citation": decode_reference(c["citation_ref"], public_catalog(row)),
                               "claim_value": c["claim_value"]} for c in claims]
                           for a, claims in values.items()}
                assert decoded == r["parsed"]["answer"]
            answer = r["parsed"]["answer"] if r["parse_error"] is None else None
            score = evaluate(row, answer, targets[cid]["EV"])
            assert score == r["score"], (arm, cid, "original scorer mismatch")
            feedback[arm][cid] = native_claim_feedback(r, targets[cid]["EV"])

    def states(cid, fb):
        result = {norm(a, c["citation"]): "correct" for a, cs in targets[cid]["EV"].items() for c in cs}
        if fb["invalid_response"]:
            return {k: "invalid" for k in result}
        for e in fb["errors"]:
            if e["kind"] in {"missing", "incorrect_value"}:
                key = norm(e["asset"], e["citation"])
                assert key in result
                result[key] = e["kind"]
        return result

    result = {"TRAIN_only_no_new_calls": True, "scorer_and_raw_decoding_independently_rechecked": True,
              "source_count": 32, "same_model_EC_exact_sources": sum(ec_exact.values()),
              "target_claim_transitions_are_not_native_macro_F1": True,
              "EC_exact_subgroup_is_posthoc_diagnostic_not_deployable_gate": True,
              "arms": {}, "paired": {}, "provenance_sha256": provenance}
    for arm, rs in arms.items():
        by = records[arm]
        cohorts = {"all32": ids, "current16": current, "prior16": ids - current,
                   "EC_exact": {c for c in ids if ec_exact[c]}, "EC_not_exact": {c for c in ids if not ec_exact[c]}}
        result["arms"][arm] = {key: metrics([by[c] for c in sorted(cs)])["EV"] for key, cs in cohorts.items()}
        result["arms"][arm]["errors"] = dict(sum((collections.Counter({k: int(f.get(k, 0)) for k in
            ["invalid_response", "correct", "missing", "incorrect_value", "extra_or_duplicate"]})
            for f in feedback[arm].values()), collections.Counter()))
    pairs = [("original_parent", a) for a in arms if a != "original_parent"]
    if include_native: pairs.append(("decoded_context", "native_context"))
    for before, after in pairs:
        transition, case_rows = collections.Counter(), []
        wrong_from_correct = []; extras_in_EC = 0
        for cid in sorted(ids):
            a, b = states(cid, feedback[before][cid]), states(cid, feedback[after][cid])
            assert a.keys() == b.keys()
            transition.update(x + "->" + b[k] for k, x in a.items())
            for e in feedback[after][cid]["errors"]:
                if e["kind"] == "incorrect_value" and a[norm(e["asset"], e["citation"])] == "correct":
                    wrong_from_correct.append({"case_id": cid, **e})
                if e["kind"] in {"extra_or_duplicate", "extra_asset_claim"}:
                    extras_in_EC += norm(e["asset"], e["citation"]) in ec_predicted[cid]
            case_rows.append({"case_id": cid, "current": cid in current, "EC_exact": ec_exact[cid],
                "native_gain_pp": 100 * (records[after][cid]["score"]["f1"] - records[before][cid]["score"]["f1"]),
                "full_gain_pp": 100 * (records[after][cid]["score"]["full_output_f1"] - records[before][cid]["score"]["full_output_f1"]),
                "before_errors": feedback[before][cid], "after_errors": feedback[after][cid]})
        result["paired"][before + "__to__" + after] = {
            "target_claim_transition_counts": dict(sorted(transition.items())),
            "new_wrong_amounts_from_parent_correct": wrong_from_correct,
            "after_extra_claims_also_in_EC_forecast": extras_in_EC,
            "native_sources_improved": sum(r["native_gain_pp"] > 1e-10 for r in case_rows),
            "native_sources_harmed": sum(r["native_gain_pp"] < -1e-10 for r in case_rows),
            "cases": case_rows}
    out = BASE / ("own_EC_context_paired_analysis_with_native_v1.json" if include_native else "own_EC_decoded_context_paired_analysis_v1.json")
    RunStore.immutable_json(out, result)
    print(json.dumps({"path": str(out), "arms": result["arms"],
        "transitions": {k: {f: v[f] for f in ["target_claim_transition_counts", "after_extra_claims_also_in_EC_forecast",
                                             "native_sources_improved", "native_sources_harmed"]}
                        for k, v in result["paired"].items()}}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--include-native", action="store_true")
    main(parser.parse_args().include_native)
