"""Finite same-bank source-binding intervention, not another training path.

Compare unchanged memory, order-only prefix, explicit public-task prefix and
strong empty on complete original contracts. No teacher, fit, new judge,
bank selection, output repair or external dependency. Preserve this finite
driver in Git/archive and remove it from active code after the diagnosis.
"""
from __future__ import annotations

import copy
import fcntl
import json
import sys
import traceback
from pathlib import Path

from experiments.witnessed_experience import WitnessedExperience
from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.learning.decision_evidence import witnessed_skill_payload, witness_knowledge_view
from legal_skill_guard.learning.evidence_programs import evidence_proposals
from legal_skill_guard.learning.experiment import ROOT, now, points, read, sha
from legal_skill_guard.learning.member_learning import paired_effect
from legal_skill_guard.utils.hashing import canonical_json_sha256 as csha

STYLES = ("empty", "original", "prefix", "prefix_explicit")


def binding_payload(row, labels, proposals, system, materialized, style):
    if style not in STYLES:
        raise ValueError("Undeclared binding intervention")
    messages, schema, delivery = witnessed_skill_payload(row, labels, proposals, system,
        materialized, mode="empty" if style == "empty" else "combined")
    original = json.loads(messages[1]["content"])
    body = copy.deepcopy(original)
    if style == "prefix_explicit":
        body["historical_evidence_demonstrations"] = [
            {"original_public_hypothesis": labels[e["hypothesis_id"]]["hypothesis"], **e}
            for e in body["historical_evidence_demonstrations"]]
    if style in ("prefix", "prefix_explicit"):
        memory_keys = ("learned_legal_procedures", "historical_evidence_demonstrations")
        body = {**{k: body[k] for k in memory_keys if k in body},
                **{k:v for k,v in body.items() if k not in memory_keys}}
        reconstructed = copy.deepcopy(body)
        if style == "prefix_explicit":
            for e in reconstructed["historical_evidence_demonstrations"]:
                assert e.pop("original_public_hypothesis") == labels[e["hypothesis_id"]]["hypothesis"]
        assert reconstructed == original  # Order-only, or duplicated PUBLIC question only.
        messages[1]["content"] = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
    return messages, schema, delivery


class SourceBindingDiagnosis(WitnessedExperience):
    def teacher_call(self, *args, **kwargs):
        raise AssertionError("This fixed-bank diagnosis cannot invoke a teacher")

    def fit_prefix(self, *args, **kwargs):
        raise AssertionError("This fixed-tool diagnosis cannot fit a model")

    def payload(self, row, style, proposals):
        return binding_payload(row, self.labels, proposals, self.cfg["bundled_solver_system"],
                               self.materialized, style)

    def answer_style(self, row, style, proposals, *, inherited=False):
        role = "joint_empty" if style == "empty" else "skills"
        messages, schema, delivery = self.payload(row, style, proposals)
        assert not delivery["excluded_same_source_witness_refs"]
        if inherited:
            assert style in ("empty", "original")
            old = ROOT / "runs" / self.cfg["inherited_source_run"]
            stage = "b3_prequential_empty" if style == "empty" else "b3_prequential_combined"
            source_input = old / f"inputs/{stage}/{row['id']}/{role}.json"
            source_native = old / f"native/{stage}/{row['id']}/{role}.json"
            source_logical = old / f"logical_answers/{stage}/{row['id']}/{role}.json"
            assert read(source_input) == {"messages": messages, "schema": schema}
            record = read(source_native)
            native = record["response"]
            logical = read(source_logical)
            assert logical["response"] == native and logical["ordinary_tool_source_ids"] == self.prefix_ids
            assert logical["bank_sha256"] == csha([] if style == "empty" else self.bank)
            self.record(f"inputs/{self.phase}/{row['id']}/{role}.json", read(source_input))
            self.record(f"inherited_actual_calls/{row['id']}/{role}.json", {
                "source_input": str(source_input), "source_input_sha256": sha(source_input),
                "source_native": str(source_native), "source_native_sha256": sha(source_native),
                "source_logical": str(source_logical), "source_logical_sha256": sha(source_logical),
                "actual_original_response": native, "new_native_calls": 0,
                "exact_original_input_schema_and_generation_settings_verified": True,
                "physical_call_already_counted_in_prior_episode_not_independent_exploration": True})
        else:
            native = self.generate(row, role, messages, schema)
        body = json.loads(messages[1]["content"])
        self.record(f"deliveries/{self.phase}/{row['id']}/{role}.json", {
            **delivery, "binding_intervention": style, "actual_native_raw_id": native["raw_id"],
            "inherited_actual_call_not_a_new_generation": inherited,
            "actual_source_read_selection": proposals["selection"],
            "actual_model_delivered_bank_knowledge_tokens": self.knowledge_tokens[style],
            "actual_user_JSON_field_order": list(body),
            "actual_visible_candidates": {"hypotheses": body["hypotheses"],
                                          "candidate_original_text": body["candidate_original_text"]}})
        self.logical(row, role, native)

    def execute(self):
        assert self.cfg["study_kind"] == "fixed_actual_bank_source_binding_16"
        assert len(self.documents) == 16 and len(self.prefix_ids) == 218
        assert [r["id"] for r in self.documents] == self.cfg["episode_ids"]
        parent_path = ROOT / self.cfg["terminal_parent_publication"]
        latest = max(parent_path.parent.glob("online_b*.json"),
                     key=lambda p: int(p.stem.split("_b")[1]))
        assert latest.resolve() == parent_path.resolve()
        parent = read(parent_path)
        assert parent["publication"] == self.bank
        terminal = read(ROOT / self.cfg["terminal_parent_receipt"])
        assert terminal["state"] == "terminal_results_preserved"
        self.materialized = parent["materialized_runtime_memory"]
        policy = read(ROOT / self.cfg["reading_calibration_completion"])["reading_policy"]
        generation = read(ROOT / self.cfg["inherited_source_config"])["generation"]
        assert self.cfg["generation"] == generation
        self.knowledge_tokens = {"empty": 0}
        for style in STYLES[1:]:
            knowledge = witness_knowledge_view(self.materialized)
            if style == "prefix_explicit":
                knowledge["historical_evidence_demonstrations"] = [
                    {"original_public_hypothesis": self.labels[e["hypothesis_id"]]["hypothesis"], **e}
                    for e in knowledge["historical_evidence_demonstrations"]]
            tokens = self.meter.token_count(text=json.dumps(knowledge, ensure_ascii=False, separators=(",", ":")))
            assert tokens <= 4096  # No deletion, clipping, short-ref budget or bank substitute.
            self.knowledge_tokens[style] = tokens
        assert self.knowledge_tokens["original"] == parent["complete_model_delivered_knowledge_target8B_tokens"]
        self.record("declaration.json", {"at": now(), "config": self.cfg,
            "frozen_bindings": self.bindings.copy(), "actual_fixed_terminal_bank": self.bank,
            "actual_fixed_materialized_memory": self.materialized, "knowledge_tokens": self.knowledge_tokens,
            "shared_ordinary_source_ids": self.prefix_ids, "shared_reading_policy": policy,
            "planned_new_native_teacher_CPUfits": [48,0,0], "planned_logical_answers": 64,
            "inherited_actual_prior_physical_calls": 16,
            "all_predictions_before_diagnostic_grading": True,
            "not_a_new_learning_episode_or_independent_confirmation": True})
        for block in range(2):
            self.current_batch = block + 3
            for index, row in enumerate(self.documents[block*8:(block+1)*8]):
                proposals = evidence_proposals(self.prefix_model, row, self.labels,
                                               reading_threshold=policy["threshold"])
                if block == 0:
                    for style in ("empty", "original"):
                        self.phase = f"inherited_b3_{style}"
                        self.answer_style(row, style, proposals, inherited=True)
                    styles = ("prefix", "prefix_explicit")
                    if index % 2:
                        styles = styles[::-1]
                else:
                    offset = index % len(STYLES)
                    styles = STYLES[offset:] + STYLES[:offset]
                for style in styles:
                    self.phase = f"binding_b{block+3}_{style}"
                    self.answer_style(row, style, proposals)
        assert len(self.native) == 48 and len(self.answers) == 64
        assert not self.teachers and not self.teacher_attempts and not self.fit_records
        units = self.score(self.answers)  # First diagnostic Gold read; no policy-selection loop.
        self.units.extend(units)
        groups = {s:[u for u in units if u["stage"].endswith("_"+s)] for s in STYLES}
        assert all(len(v) == 16 for v in groups.values())
        result = {"at": now(), "run_id": self.run_id,
            "metrics": {s:points(v) for s,v in groups.items()},
            "fixed_first8_metrics": {s:points([u for u in v if u["document_id"] in self.cfg["episode_ids"][:8]])
                                     for s,v in groups.items()},
            "fixed_next8_metrics": {s:points([u for u in v if u["document_id"] in self.cfg["episode_ids"][8:]])
                                    for s,v in groups.items()},
            "paired_effects": {f"{a}_to_{b}": paired_effect(groups[a], groups[b],
                seed=2026101910+i, replicates=5000) for i,(a,b) in enumerate([
                    ("original","prefix"),("prefix","prefix_explicit"),("empty","prefix_explicit")])},
            "actual_new_native_teacher_CPUfits": [48,0,0], "inherited_actual_physical_calls": 16,
            "logical_answers": 64, "knowledge_tokens": self.knowledge_tokens,
            "not_token_matched_or_independent_learning_repeats_or_formal_TEST": True,
            "no_teacher_bank_admission_repair_fit_or_future_source_selection": True,
            "all_adverse_cases_invalids_and_units": units,
            "prior_development_family_native_teacher_CPUfits": self.cfg["prior_development_family_native_teacher_CPUfits"],
            "total_development_family_native_teacher_CPUfits": [
                a+b for a,b in zip([48,0,0],self.cfg["prior_development_family_native_teacher_CPUfits"],strict=True)]}
        self.record("completion.json", result)
        RunStore.atomic_json(self.out/"progress.json", {"at":now(), "state":"completed",
            "run_id":self.run_id, "completed_native_calls":48, "completed_teacher_calls":0,
            "actual_new_CPUfits":0, "metrics":result["metrics"]})
        print(json.dumps({"complete":self.run_id,"metrics":result["metrics"]}),flush=True)


def main():
    with (ROOT/"artifacts/gpu_generation.lock").open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX|fcntl.LOCK_NB)
        study = SourceBindingDiagnosis(Path(sys.argv[1]))
        try:
            study.execute()
        except BaseException as error:
            failure = {"at":now(), "state":"failed", "error":repr(error),
                "traceback":traceback.format_exc(), "actual_new_native_teacher_CPUfits":[
                    len(study.native),len(study.teachers),len(study.fit_records)],
                "no_retry_fallback_answer_repair_or_selected_bank":True}
            study.record("failure.json", failure)
            RunStore.atomic_json(study.out/"progress.json", failure)
            raise


if __name__ == "__main__":
    main()
