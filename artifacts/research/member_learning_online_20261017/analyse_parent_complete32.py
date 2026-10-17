"""Recount complete old32 member selection and preserve every paired harm.

No generation, fitting, future-source labels, output edits or semantic judge.
This is descriptive diagnosis of the fixed taught bank, never an admission set.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.learning.experiment import ROOT, now, read, sha

RUN = ROOT / "runs/legal_contractnli_discriminative_evidence_full32_retention_20261017_run01"
PARENT = ROOT / "runs/legal_contractnli_discriminative_evidence_skill_20261017_run03"
OUTPUT = Path(__file__).with_name("parent32_membership_and_all_damage_audit.json")


def summarize(rows):
    nn = [r for r in rows if r["gold"]["choice"] != "NotMentioned"]
    tp = sum(len(set(r["gold"]["spans"]) & set(r["prediction"]["spans"])) for r in nn)
    fp = sum(len(set(r["prediction"]["spans"]) - set(r["gold"]["spans"])) for r in nn)
    fn = sum(len(set(r["gold"]["spans"]) - set(r["prediction"]["spans"])) for r in nn)
    return {"questions": len(rows), "NN": len(nn), "label_correct": sum(r["label_correct"] for r in rows),
        "joint_exact": sum(r["joint_exact"] for r in rows), "tp": tp, "fp": fp, "fn": fn,
        "Gold_NN_F1": 2 * tp / (2 * tp + fp + fn) if nn else None,
        "label_correct_but_inexact_members": sum(r["label_correct"] and not r["joint_exact"] for r in nn)}


def main():
    complete = read(RUN / "completion.json")
    assert complete["actual_new_native_teacher_calls"] == [48, 0]
    assert complete["all64_wires_and_original_author_sets_independently_recounted"]
    units = read(RUN / "complete64_actual_paired_native_and_original_scores.json")["units"]
    packet = Path(read(PARENT / "declaration.json")["config"]["input_packet"])
    source_packet = read(ROOT / packet)
    sources = {r["id"]: r for r in source_packet["documents"]}
    publication = PARENT / "publications/b5.json"
    bank = read(publication)["publication"]
    scoped = {h for s in bank if s["guidance"].get("evidence_criterion") is not None for h in s["hypothesis_ids"]}
    records, roles, score_groups = {}, defaultdict(lambda: defaultdict(int)), defaultdict(list)
    bins, hypotheses, choices, scopes = (defaultdict(lambda: defaultdict(list)) for _ in range(4))
    for u in units:
        d, arm = u["document_id"], u["condition"]
        p = read(u["payload"])
        body = json.loads(p["messages"][1]["content"])
        for q in u["queries"]:
            h, g, pred = q["hypothesis_id"], q["gold"], q["prediction"]
            assert pred is not None and u["native_schema_valid"]
            hint = body["hypotheses"][h]
            candidates = {v["original_span_index"]: v for v in hint["fallible_evidence_candidates"]}
            additional = {v["original_span_index"]: v for v in hint["additional_source_read_indices"]}
            gold, cited = set(g["spans"]), set(pred["spans"])
            bins[arm][str(len(gold)) if len(gold) < 3 else "3+"].append(q)
            hypotheses[arm][h].append(q)
            choices[arm][g["choice"]].append(q)
            scopes[arm]["criterion_scoped" if h in scoped else "not_criterion_scoped"].append(q)
            members = []
            for i in range(len(sources[d]["spans"])):
                item = candidates.get(i) or additional.get(i)
                role = "ordinary" if i in candidates else "extra_direct" if i in additional and additional[i]["literal_match"] else "extra_context" if i in additional else "outside_leads"
                if g["choice"] != "NotMentioned":
                    truth = "Gold" if i in gold else "nonGold"
                    selected = "cited" if i in cited else "omitted"
                    roles[arm][role + ":" + truth + ":" + selected] += 1
                    if item is not None:
                        score_groups[(arm, role, truth, selected)].append(item["membership_score"])
                if i in gold | cited:
                    members.append({"index": i, "original_text": sources[d]["text"][slice(*sources[d]["spans"][i])],
                        "original_member": i in gold if g["choice"] != "NotMentioned" else None,
                        "cited": i in cited, "role": role, "delivered_membership_score": item["membership_score"] if item else None})
            records[(arm, d, h)] = {"original_hypothesis": source_packet["public_hypotheses"][h],
                "gold": g, "prediction": pred, "label_correct": q["label_correct"], "joint_exact": q["joint_exact"],
                "has_published_criterion": h in scoped, "members": members,
                "payload": u["payload"], "raw_artifact": u["raw_artifact"]}
    arms = ["ordinary", "skills"]
    harm, changes = [], defaultdict(int)
    for arm, d, h in records:
        if arm != "skills":
            continue
        a, b = records[("ordinary", d, h)], records[(arm, d, h)]
        if (a["label_correct"] and not b["label_correct"]) or (a["joint_exact"] and not b["joint_exact"]):
            harm.append({"document_id": d, "hypothesis_id": h,
                "label_damage": a["label_correct"] and not b["label_correct"],
                "joint_damage": a["joint_exact"] and not b["joint_exact"], "ordinary": a, "skills": b})
        if b["gold"]["choice"] != "NotMentioned":
            ga, ca, cb = set(a["gold"]["spans"]), set(a["prediction"]["spans"]), set(b["prediction"]["spans"])
            lookup = {m["index"]: m["role"] for m in b["members"]}
            for i in ga & (cb - ca):
                changes["Gold_gained:" + lookup[i]] += 1
            for i in ga & (ca - cb):
                changes["Gold_lost:" + lookup[i]] += 1
    def grouped(value):
        return {arm: {key: summarize(v) for key, v in value[arm].items()} for arm in arms}

    result = {"at": now(), "actual_new_native_teacher_calls_for_this_analysis": [0, 0],
        "old32_fixed_taught_bank_not_current_new32_online_results": True,
        "by_original_Gold_cardinality": grouped(bins), "by_original_hypothesis": grouped(hypotheses),
        "by_original_relation": grouped(choices), "by_criterion_scope_not_semantic_isolation": grouped(scopes),
        "original_NN_member_roles": dict(roles), "paired_true_member_changes_by_skill_access_role": dict(changes),
        "actual_delivered_score_quantiles_p0_p25_p50_p75_p100_not_causal_anchor_proof": {
            ":".join(key): {"n": len(values), "quantiles": np.quantile(values, [0, .25, .5, .75, 1]).tolist()}
            for key, values in score_groups.items()},
        "all_paired_label_or_joint_damage_original_text_and_public_reasons": harm,
        "complete_source_packet": str(ROOT / packet), "full_NM_source_needed_not_all_uncited_spans_are_negatives": True,
        "no_manual_Gold_correction_case_exclusion_answer_edit_or_main_run_change": True,
        "bindings": {str(p): sha(p) for p in [Path(__file__), RUN / "completion.json", RUN / "complete64_actual_paired_native_and_original_scores.json", publication, ROOT / packet]}}
    assert sum(r["label_damage"] for r in harm) == 23 and sum(r["joint_damage"] for r in harm) == 29
    assert sum(v for k, v in changes.items() if k.startswith("Gold_gained:")) == 58
    assert sum(v for k, v in changes.items() if k.startswith("Gold_lost:")) == 33
    RunStore.immutable_json(OUTPUT, result)
    print({"complete_old_sources": 32, "all_harm_questions": len(harm), "new_generation": 0, "output": str(OUTPUT)})


if __name__ == "__main__":
    main()
