"""Original-author/wire audit of the COMPLETE held-K2 interface comparison.

Never read partial outcomes. No generation, semantic judge or answer repair.
This file is run-local analysis, not an inference dependency or production layer.
"""

# ruff: noqa: E402 -- Exact project and run identities are intentional.
from __future__ import annotations

import json
import runpy
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parents[1]
PARENT = ROOT / "runs/legal_contractnli_executable_acquisition_online_20261017_run01"
sys.path.insert(0, str(ROOT))

import numpy as np
from jsonschema import validate

from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.learning.acquisition import source_messages
from legal_skill_guard.learning.experiment import now, read, sha
from legal_skill_guard.task import marked_text
from legal_skill_guard.utils.hashing import canonical_json_sha256 as csha

# Only pure original-member arithmetic is reused. The old payload/wire auditor,
# phase loader and compiler are NOT run against the changed production source.
UTIL_PATH = PARENT / "monitoring/audit_batch.py"
UTIL = runpy.run_path(str(UTIL_PATH))
counts, contrast = UTIL["counts"], UTIL["contrast"]
METRICS = ("label_accuracy", "evidence_micro_f1_gold_non_neutral", "joint_exact_accuracy")


def source_resampling(before, after, ids):
    """Paired SOURCE clusters, not 272 independent questions or learned banks."""
    def table(rows):
        return np.array([[sum(r[k] for r in rows if r["document_id"] == d)
            for k in ("label_correct", "tp", "fp", "fn", "joint_exact")] for d in ids])

    def scores(values):
        label, tp, fp, fn, joint = values.T
        return np.column_stack((label / (17 * len(ids)), 2 * tp / (2 * tp + fp + fn),
            joint / (17 * len(ids))))

    index = np.random.default_rng(2026101716).integers(0, len(ids), (10000, len(ids)))
    delta = 100 * (scores(table(after)[index].sum(1)) - scores(table(before)[index].sum(1)))
    return {k: {"percentile95_pp": np.percentile(delta[:, i], [2.5, 97.5]).tolist(),
        "not_independent_learning_repeats_or_confirmatory_TEST": True}
        for i, k in enumerate(METRICS)}


def main():
    final_path = OUT / "completion.json"
    assert final_path.is_file(), "Wait for all32 native calls; no partial quality scoring"
    destination = OUT / "monitoring/complete32_original_author_same_facts_wire_and_paired_effects_audit.json"
    assert not destination.exists(), "Already audited; read the immutable saved report"
    complete = read(final_path)
    cfg_path = ROOT / "configs/contractnli_acquisition_fact_boundary.json"
    cfg, frozen = read(cfg_path), read(cfg_path.with_suffix(".frozen.json"))
    assert all(sha(p) == digest for p, digest in frozen["files"].items())
    assert complete["completed_native_calls"] == 32 and complete["completed_teacher_calls"] == 0
    assert cfg["diagnostic_source_ids"] == cfg["training_ids"][:16]
    assert sha(ROOT / cfg["source_archive"]) == cfg["source_archive_sha256"]
    with zipfile.ZipFile(ROOT / cfg["source_archive"]) as archive:
        author = json.loads(archive.read("contract-nli/train.json"))
    sources = {r["id"]: r for r in author["documents"]}
    labels = author["labels"]
    publication_path = ROOT / cfg["fixed_bank_publication"]
    assert sha(publication_path) == cfg["fixed_bank_publication_sha256"]
    bank = read(publication_path)["publication"]
    bank_hash = csha(bank)
    assert complete["fixed_bank_sha256"] == bank_hash
    units_path = OUT / "complete32_native_and_original_scores.json"
    units = read(units_path)["units"]
    assert len(units) == 32
    assert {(u["condition"], u["document_id"]) for u in units} == {
        (a, d) for a in ("ordinary", "skills") for d in cfg["diagnostic_source_ids"]}
    ordinary_manifest = read(ROOT / cfg["ordinary_manifest"])
    bindings = frozen["files"].copy()
    ids, rows = set(), []
    usage = {k: 0 for k in ("prompt_tokens", "completion_tokens")}
    for u in units:
        payload, raw = read(u["payload"]), read(u["raw_artifact"])
        assert raw["transport_error"] is None and len(raw["calls"]) == 1
        request, server = (raw["calls"][0][k] for k in ("request", "response"))
        assert request["messages"] == payload["messages"]
        assert request["response_format"]["json_schema"]["schema"] == payload["schema"]
        assert all(request[k] == cfg["generation"][k] for k in (
            "model", "seed", "temperature", "top_p", "top_k", "max_tokens"))
        response = raw["response"]
        assert u["response"] == response
        assert response["content"] == server["choices"][0]["message"]["content"]
        assert response["raw_id"] == server["id"] and server["id"] not in ids
        assert server["model"] == cfg["generation"]["model"]
        assert response["finish_reason"] == server["choices"][0]["finish_reason"] == "stop"
        assert server["choices"][0]["message"]["reasoning_content"]
        ids.add(server["id"])
        for k in usage:
            assert response[k] == server["usage"][k]
            usage[k] += server["usage"][k]
        values = json.loads(response["content"])
        validate(values, payload["schema"])
        original = sources[u["document_id"]]
        source = {k: original[k] for k in ("id", "text", "spans")}
        expected_bank = bank if u["condition"] == "skills" else []
        assert payload["bank"] == expected_bank
        assert payload["bank_sha256"] == u["bank_sha256"] == csha(expected_bank)
        assert payload["fixed_ordinary_model_state"] == ordinary_manifest["state_sha256"]
        old_batch = 1 + cfg["diagnostic_source_ids"].index(source["id"]) // 8
        old_payload_path = PARENT / f"prospective/b{old_batch}_before/ordinary/{source['id']}.json"
        old_payload = read(old_payload_path)
        old_body = json.loads(old_payload["messages"][1]["content"])
        proposals = {"by_hypothesis": {h: {"candidates":
            old_body["hypotheses"][h]["fallible_evidence_candidates"]} for h in labels}}
        # Replay declared factual serving, not the worker's legal scoring.
        messages, schema, trace = source_messages(source, labels,
            cfg["bundled_solver_system"], expected_bank, proposals)
        assert (messages, schema, trace) == (
            payload["messages"], payload["schema"], payload["actual_factual_trace"])
        body = json.loads(messages[1]["content"])
        assert body["full_contract_with_original_span_markers"] == marked_text(source)
        assert "SOURCE_LEADS" not in messages[1]["content"]
        assert all(s["id"] not in json.dumps([messages, schema]) for s in bank)
        assert set(values) == set(labels)
        for h, g in original["annotation_sets"][0]["annotations"].items():
            value, question = values[h], body["hypotheses"][h]
            assert set(value) == {"choice", "spans", "reason"}
            assert question["original_hypothesis"] == labels[h]["hypothesis"]
            assert question["original_public_short_description"] == labels[h]["short_description"]
            for branch in schema["properties"][h]["anyOf"]:
                assert branch["properties"]["spans"]["items"]["enum"] == list(range(len(source["spans"])))
            assert {v for branch in schema["properties"][h]["anyOf"]
                for v in branch["properties"]["choice"]["enum"]} == {"Entailment", "Contradiction", "NotMentioned"}
            ordinary = [v["original_span_index"] for v in question["fallible_evidence_candidates"]]
            returned = trace["per_hypothesis_returned_original_indices"][h]
            assert question["additional_source_read_indices"] == sorted(set(returned) - set(ordinary))
            for i in set(ordinary) | set(returned):
                assert body["candidate_original_text"][str(i)] == source["text"][slice(*source["spans"][i])]
            gold, prediction = set(g["spans"]), set(value["spans"])
            nn = g["choice"] != "NotMentioned"
            rows.append({"document_id": source["id"], "hypothesis_id": h,
                "condition": u["condition"], "Gold_choice": g["choice"], "Gold_spans": g["spans"],
                **value, "ordinary": ordinary, "program": returned,
                "label_correct": value["choice"] == g["choice"],
                "joint_exact": value["choice"] == g["choice"] and gold == prediction,
                "tp": len(gold & prediction) if nn else 0,
                "fp": len(prediction - gold) if nn else 0,
                "fn": len(gold - prediction) if nn else 0})
        for p in (Path(u["payload"]), Path(u["raw_artifact"]), old_payload_path):
            bindings[str(p)] = sha(p)
    arms = {a: [r for r in rows if r["condition"] == a] for a in ("ordinary", "skills")}
    metrics = {a: counts(r) for a, r in arms.items()}
    for a, m in metrics.items():
        for k in m.keys() & complete["fixed_seen_interface_results"][a].keys():
            assert abs(m[k] - complete["fixed_seen_interface_results"][a][k]) < 1e-12
    assert usage == complete["actual_native_usage"]
    old_files = [PARENT / f"monitoring/b{b}_before_original_author_sets_actual_wires_and_acquisition_audit.json" for b in (1, 2)]
    old_files.append(PARENT / "monitoring/b2_retention_original_author_sets_actual_wires_and_acquisition_audit.json")
    historical = {"ordinary": [r for f in old_files[:2] for r in read(f)["all_query_records"] if r["condition"] == "ordinary"],
        "skills": read(old_files[2])["all_query_records"]}
    history_metrics = {a: counts(r) for a, r in historical.items()}
    source_ids = cfg["diagnostic_source_ids"]
    report = {"at": now(), "run_id": OUT.name,
        "all32_actual_wires_original_author_sets_and_exact_factual_delivery_checked": True,
        "fixed_K2_not_K1_or_unexecuted_K3": bank_hash,
        "new_actual_native_responses": len(ids), "unique_sources": len(source_ids), "new_teachers": 0,
        "new_interface_metrics": metrics, "old_interface_existing_outputs_not_new_calls": history_metrics,
        "by_original_training_batch": {str(b): {a: counts([r for r in rr if r["document_id"] in source_ids[(b - 1) * 8:b * 8]]) for a, rr in arms.items()} for b in (1, 2)},
        "new_same_interface_skill_effect": contrast(arms["ordinary"], arms["skills"]),
        "old_same_interface_skill_effect": contrast(historical["ordinary"], historical["skills"]),
        "ordinary_layout_effect": contrast(historical["ordinary"], arms["ordinary"]),
        "skilled_layout_effect": contrast(historical["skills"], arms["skills"]),
        "new_skill_effect_source_cluster_resampling": source_resampling(arms["ordinary"], arms["skills"], source_ids),
        "difference_in_skill_effect_pp": {k: 100 * ((metrics["skills"][k] - metrics["ordinary"][k]) - (history_metrics["skills"][k] - history_metrics["ordinary"][k])) for k in METRICS},
        "actual_new_native_usage": usage, "all_new_query_records": rows,
        "combined_actor_boundary_change_not_unique_isolation_of_each_removed_component": True,
        "not_unseen_transfer_online_evolution_mature_method_victory_independent_repeat_or_TEST": True}
    for p in [final_path, units_path, cfg_path.with_suffix(".frozen.json"), UTIL_PATH, Path(__file__).resolve(), *old_files]:
        bindings[str(p)] = sha(p)
    report["bindings"] = bindings
    RunStore.immutable_json(destination, report)
    print(json.dumps({k: report[k] for k in ("new_interface_metrics", "old_interface_existing_outputs_not_new_calls",
        "new_same_interface_skill_effect", "difference_in_skill_effect_pp", "actual_new_native_usage")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
