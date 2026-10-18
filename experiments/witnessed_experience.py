"""Finite case-backed skill evolution with exact historical evidence memory.

Reuses the original native model, ordinary tool, publication and scorer. This is
an experimental entrypoint, not a second runtime service or an answer adapter.
"""
from __future__ import annotations

import copy
import fcntl
import json
import sys
import traceback
from pathlib import Path

from experiments.decision_evidence_transfer import RankedOnline, EDIT_FEEDBACK_METHOD, evidence_proposals
from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.learning.catalog import encode_teacher_body
from legal_skill_guard.learning.decision_evidence import (
    training_witness_catalog, witnessed_guidance_schema, materialize_witness_skills,
    witness_knowledge_view, witnessed_skill_payload)
from legal_skill_guard.learning.experiment import ROOT, read, sha, now, points
from legal_skill_guard.learning.member_contract import annotated_sources
from legal_skill_guard.learning.member_learning import paired_effect
from legal_skill_guard.learning.packing import table, expand
from legal_skill_guard.learning.publication import (
    differential_schema, apply_differential_publication, publication_statistics)
from legal_skill_guard.utils.hashing import canonical_json_sha256 as csha

TEACHER_SYSTEM = (
    "Learn reusable legal inspection skills backed by selected ORIGINAL historical TRAIN evidence "
    "demonstrations. This replaces rules-only memory, not the task or frozen lawyer. Every inference "
    "remains ONE frozen8B native reason/choice/original-integer-SPAN answer on the full current NDA "
    "and same ordinary tool. Use actual supplied sources, Gold, answers and candidate observations, "
    "including successes and harms. Old reference policies are identified historical versions, NOT "
    "invented executions of this new representation. Their prose and labels are fallible experience, "
    "not universal law. Publish explicit CREATE/UPDATE/DELETE/MERGE/NOOP against current_parent_library; "
    "unmentioned records stay verbatim. Each guidance has procedure and witness_refs. A witness_ref "
    "selects an eligible already-seen source/hypothesis pair WITHIN the skill's public scope. The host "
    "materializes ALL original evidence texts and its original E/C label, never invented snippets or "
    "old numeric coordinates. These are different past examples, not current facts or answers. "
    "NM deliberately has no snippet demonstration: a local excerpt cannot prove whole-contract absence. "
    "Use concrete legal contrasts and source functions to teach actor/action/object, modality, "
    "quantifiers, prohibitions, triggers, exceptions and complete responsive evidence. Preserve "
    "opposed boundaries rather than treating every restriction as NM. Lack of a matching example "
    "never implies a legal label. Avoid arbitrary literal shortcuts and generalizing one phrasing. "
    "Choose informative historical evidence with contrasting relations or selection boundaries; "
    "do not force a fixed skill/witness count, growth, one-per-hypothesis or positive-label-only list. "
    "A procedure may have [] witnesses when justified. No case answer tables, IDs, original indices, "
    "parties or dates in procedures. Exact past text is supplied by reference only. Same-source "
    "witnesses are excluded by source identity AND content hash, even for training reanswers. "
    "All original current indices remain selectable; only the lawyer decides final labels/citations. "
    "The same bank has rule-only, witness-only, combined and empty ablations. Use their REAL outcomes "
    "to distinguish reusable procedures from simply adding demonstrations. Original three-way "
    "accuracy, Gold-NN hard original-SPAN F1 and strict joint are unchanged. The COMPLETE MATERIALIZED "
    "knowledge bank, INCLUDING every procedure/scope and FULL historical evidence text/label, must fit4096 "
    "actual target8B tokens; aim2800. Internal audit hashes/IDs are stored/reported separately, not served "
    "knowledge. Each eligible example's exact standalone target8B token cost is supplied. These costs "
    "guide packing, not a promise of additive BPE costs; leave room for rules/structure. Reference IDs "
    "are NOT cheap substitutes for full texts. Do not "
    "blindly attach many long examples. No per-record character clipping or fixed template quota. "
    "All structurally valid edits publish without utility admission, best-bank selection, score-based "
    "retry, fallback or a second curator. Explain the actual source-supported change for each "
    "operation; do not invent successful execution or expose hidden reasoning. No tools/outside data. "
    "Return the exact differential JSON schema."
)


class WitnessedExperience(RankedOnline):
    def observe(self, units):
        values = []
        for u in units:
            delivery = read(self.out / f"deliveries/{u['stage']}/{u['document_id']}/{u['condition']}.json")
            values.append({
                "document_id": u["document_id"], "stage": u["stage"], "bank_sha256": u["bank_sha256"],
                "actual_ordinary_tool_source_ids": u["ordinary_tool_source_ids"],
                "actual_native_answer": u["parsed"], "public_valid": u["public_valid"],
                "invalid_native_content": None if u["public_valid"] else u["response"]["content"],
                "actual_delivery": delivery,
                "original_component_feedback": {q["hypothesis_id"]: {k: q[k] for k in (
                    "label_correct", "evidence_tp", "evidence_fp", "evidence_fn", "joint_exact")}
                    for q in u["queries"]}})
        return table(values)

    def publish(self, body, name):
        parent = copy.deepcopy(self.bank)
        catalog = body["eligible_original_non_neutral_historical_witnesses"]
        window = expand(body["complete_already_revealed_original_source_window_and_Gold"])
        allowed = sorted({r["id"] for r in window} | {x["source_case_id"] for x in catalog.values()})
        guidance = witnessed_guidance_schema(catalog)
        schema = differential_schema(self.labels, parent, allowed, guidance_schema=guidance)
        body["current_parent_library"] = parent
        body["current_materialized_parent_including_all_past_evidence_texts"] = self.materialized
        body["library_budget"] = {"current_materialized_target8B_tokens": self.memory_tokens,
                                  "target_tokens": 2800, "hard_tokens": 4096}
        self.progress("memory_budget", current_arm=name,
                      exact_CPU_tokenizer_cost_requests=len(catalog))
        fields = ("hypothesis_id", "original_training_label", "complete_original_evidence_texts")
        body["exact_standalone_example_target8B_token_costs"] = {
            ref: self.meter.token_count(text=json.dumps({k: w[k] for k in fields},
                ensure_ascii=False, separators=(",", ":"))) for ref, w in catalog.items()}
        body["token_costs_are_existing_CPU_tokenizer_requests_not_native_generations"] = len(catalog)
        self.record(f"learning_inputs/{name}.json", body)
        delta = self.teacher_call(name, TEACHER_SYSTEM, encode_teacher_body(body), schema)
        bank = apply_differential_publication(parent, delta, self.labels, allowed, guidance_schema=guidance)
        materialized = materialize_witness_skills(bank, self.labels, catalog)
        tokens = self.meter.token_count(text=json.dumps(witness_knowledge_view(materialized),
            ensure_ascii=False, separators=(",", ":")))
        audit_storage_tokens = self.meter.token_count(text=json.dumps(materialized,
            ensure_ascii=False, separators=(",", ":")))
        assert tokens <= 4096, "Complete materialized knowledge exceeds capacity; no clipping, gate or old-bank substitute"
        stats = publication_statistics(parent, delta, bank, tokens)
        self.record(f"publications/{name}.json", {
            "at": now(), "parent": parent, "delta": delta, "publication": bank,
            "materialized_runtime_memory": materialized, "statistics": stats,
            "source_ids_actually_available_to_teacher": allowed,
            "all_valid_edits_used_without_utility_gate": True,
            "complete_model_delivered_knowledge_target8B_tokens": tokens,
            "internal_audit_storage_target8B_tokens_reported_separately": audit_storage_tokens,
            "exact_tokenizer_budget_requests_not_native_generations": len(catalog)+2})
        self.bank, self.materialized, self.catalog, self.memory_tokens = bank, materialized, catalog, tokens
        self.publication_history.append(stats)

    def answer_mode(self, row, mode, proposals):
        role = "joint_empty" if mode == "empty" else "skills"
        messages, schema, delivery = witnessed_skill_payload(
            row, self.labels, proposals, self.cfg["bundled_solver_system"], self.materialized, mode=mode)
        native = self.generate(row, role, messages, schema)
        body = json.loads(messages[1]["content"])
        self.record(f"deliveries/{self.phase}/{row['id']}/{role}.json", {
            **delivery, "actual_native_raw_id": native["raw_id"], "materialized_bank_sha256": csha(self.materialized),
            "actual_visible_candidates": {"hypotheses": body["hypotheses"],
                                          "candidate_original_text": body["candidate_original_text"]}})
        self.logical(row, role, native)

    def execute(self):
        assert self.cfg["method"] == EDIT_FEEDBACK_METHOD and len(self.documents) == 16 and len(self.past) == 242
        assert [r["id"] for r in self.documents] == [249,197,150,166,365,386,119,125,300,180,350,347,403,160,599,554]
        assert not self.bank and len(self.prefix_ids) == 242
        terminal = read(ROOT / self.cfg["reference_terminal_preservation"])
        assert terminal["state"] == "terminal_results_preserved" and terminal["all_members_verified"]
        assert sha(terminal["archive"]) == sha(terminal["rootdisk_copy"]) == terminal["archive_sha256"]
        self.materialized, self.catalog, self.memory_tokens, self.publication_history = [], {}, 0, []
        self.fit_records = [read(ROOT / self.cfg["ordinary_manifest"])]
        self.current_batch = 5
        self.record("declaration.json", {
            "at": now(), "config": self.cfg, "frozen_bindings": self.bindings.copy(),
            "planned_new_native_teacher_CPUfits": [72,2,self.cfg["planned_new_CPU_fits"]],
            "inherited_failed_native_teacher_CPUfits": self.cfg.get("inherited_failed_native_teacher_CPUfits", [0,0,0]),
            "initial_common_CPUfit_already_done_and_counted": True,
            "all8_all4_before_each_batch_Gold_grading": True,
            "same_source_witness_exclusion_applies_even_to_training_reanswers": True,
            "not_formal128_independent_repeat_equal_cost_mature_baseline_or_official_TEST": True,
            "prior_failed_group_probe_and_all_adverse_history_preserved": True})
        initial = read(ROOT / self.cfg["initial_teacher_body"])
        self.publish(initial, "initial_known_prefix40")
        modes = ["empty", "procedure_only", "witnesses_only", "combined"]
        summaries, update_effect = [], None
        for offset in (0, 8):
            self.current_batch = 6 + offset // 8
            rows, start = self.documents[offset:offset+8], len(self.answers)
            for index, row in enumerate(rows):
                proposals = evidence_proposals(self.prefix_model, row, self.labels)
                for mode in modes[index%4:] + modes[:index%4]:
                    self.phase = f"b{self.current_batch}_prequential_" + mode
                    self.answer_mode(row, mode, proposals)
            fresh = self.score(self.answers[start:])
            self.units.extend(fresh)
            groups = {m: [u for u in fresh if u["stage"].endswith("_" + m)] for m in modes}
            assert all(len(v) == 8 for v in groups.values())
            summary = {"at": now(), "batch": self.current_batch, "new_source_ids": [r["id"] for r in rows],
                "current_reference_bank": self.bank, "materialized_bank_tokens": self.memory_tokens,
                "common_ordinary_source_count": len(self.prefix_ids), "metrics": {m: points(v) for m,v in groups.items()},
                "same_case_effects_vs_empty": {m: paired_effect(groups["empty"], groups[m],
                    seed=2026101960+self.current_batch+i, replicates=5000)
                    for i,m in enumerate(modes) if m != "empty"}}
            self.record(f"batch_summaries/b{self.current_batch}_before.json", summary)
            summaries.append(summary)
            if offset == 0:
                gold = read(ROOT / self.cfg["grading_only"])["original_TRAIN_annotations"]
                window = self.past[-8:] + rows
                catalog = training_witness_catalog(window, self.labels, gold)
                for skill in self.bank:
                    for ref in skill["guidance"]["witness_refs"]:
                        catalog.setdefault(ref, self.catalog[ref])
                body = {"public_hypotheses": self.labels,
                    "complete_already_revealed_original_source_window_and_Gold": annotated_sources(window,self.labels,gold),
                    "eligible_original_non_neutral_historical_witnesses": catalog,
                    "all_actual_current8_four_arm_answers_and_component_feedback": self.observe(fresh),
                    "actual_current_batch_four_arm_metrics": summary["metrics"],
                    "current_common_ordinary_tool_source_ids": self.prefix_ids,
                    "previous8_reference_observations_not_new_method_own_executions": table([
                        u for u in expand(initial["all_reference_empty_and_prose_observations_in_same_case_tool_pairs"])
                        if u["document_id"] in {r["id"] for r in self.past[-8:]}]),
                    "no_future_source_text_answers_annotations_or_official_DEV_TEST": True,
                    "publication_then_actual_same8_combined_reanswer_under_same_tool_with_same_source_examples_excluded": True}
                self.publish(body, "after_new_batch6")
                start_after, self.phase = len(self.answers), "b6_after_seen_combined"
                for row in rows:
                    self.answer_mode(row, "combined", evidence_proposals(self.prefix_model,row,self.labels))
                after = self.score(self.answers[start_after:])
                self.units.extend(after)
                update_effect = paired_effect(groups["combined"], after, seed=2026101969, replicates=5000)
                self.record("update_effects/b6.json", {"at": now(), "effect": update_effect,
                    "same_common242_tool_and_same_source_witness_exclusion": True,
                    "all8_training_reanswers_not_forward_generalization_or_bank_admission": True})
                self.fit_prefix(self.documents[:8])
        assert len(self.native) == len(self.answers) == 72 and len(self.teachers) == len(self.fit_records) == 2
        groups = {m: [u for u in self.units if "_prequential_" in u["stage"] and u["stage"].endswith("_"+m)]
                  for m in modes}
        assert all(len(v) == 16 for v in groups.values())
        result = {"at": now(), "run_id": self.run_id, "complete16_prequential_metrics": {m:points(v) for m,v in groups.items()},
            "same_case_all16_effects_vs_empty": {m: paired_effect(groups["empty"],groups[m],
                seed=2026101970+i,replicates=5000) for i,m in enumerate(modes) if m != "empty"},
            "batch_summaries": summaries, "actual_first_update_training_effect": update_effect,
            "actual_new_native_teacher_CPUfits": [72,2,self.cfg["planned_new_CPU_fits"]],
            "inherited_failed_native_teacher_CPUfits": self.cfg.get("inherited_failed_native_teacher_CPUfits", [0,0,0]),
            "prior_development_family_native_teacher_CPUfits": self.cfg["prior_development_family_native_teacher_CPUfits"],
            "total_this_development_family_native_teacher_CPUfits": [a+b for a,b in zip(
                [72,2,self.cfg["planned_new_CPU_fits"]],self.cfg["prior_development_family_native_teacher_CPUfits"],strict=True)],
            "actual_ordinary_fits": self.fit_records, "publication_statistics": self.publication_history,
            "final_reference_bank": self.bank, "final_materialized_memory": self.materialized, "units": self.units,
            "all_adverse_arms_cases_invalids_and_original_denominators_preserved": True,
            "not_formal128_independent_repeat_or_official_TEST": True}
        self.record("completion.json", result)
        RunStore.atomic_json(self.out / "progress.json", {
            "at": now(), "state": "completed", "run_id": self.run_id, "completed_native_calls": 72,
            "completed_teacher_calls": 2, "actual_new_CPUfits": self.cfg["planned_new_CPU_fits"],
            "inherited_common_CPUfit": self.cfg.get("inherited_initial_common_fit",False),
            "all16_forward_metrics": result["complete16_prequential_metrics"]})
        print(json.dumps({"completed": self.run_id, "metrics": result["complete16_prequential_metrics"]}), flush=True)


def main():
    with (ROOT / "artifacts/gpu_generation.lock").open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        study = WitnessedExperience(Path(sys.argv[1]))
        try:
            study.execute()
        except BaseException as error:
            failure = {"at": now(), "state": "failed", "error": repr(error), "traceback": traceback.format_exc(),
                "actual_native_teacher_CPUfits": [len(study.native),len(study.teachers),
                    max(0,len(study.fit_records)-int(study.cfg.get("inherited_initial_common_fit",False)))],
                "inherited_failed_native_teacher_CPUfits": study.cfg.get("inherited_failed_native_teacher_CPUfits", [0,0,0]),
                "no_retry_answer_repair_fallback_gate_or_selected_bank": True}
            study.record("failure.json", failure)
            RunStore.atomic_json(study.out / "progress.json", failure)
            raise


if __name__ == "__main__":
    main()
