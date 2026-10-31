"""One phase-only TRAIN diagnosis: legal clauses, then execution representation.

Not a formal learning stream, validation split, frozen TEST, or new executor.
Uses Online's original HTTP, decoding, grading, dispatch and teacher transports.
Three immutable runs share one <=292-generation revised window; the preceding
failed12/one-teacher interface remains separately counted and preserved. Proposals stop
for the main agent's semantic audit before any candidate outcome is generated.
"""

from __future__ import annotations

import argparse
import copy
import fcntl
import json
import threading
import traceback
from pathlib import Path

from experiments.openexempt_online import (
    ROOT, Online, actor_payload, csha, freeze, metrics, now, paired_effect,
    preserve, read, sha, task_view, validate_scoped_bank, validate_scopes,
    validate_task_projection_edit,
)
from legal_skill_guard.experiment.storage import RunStore

GROUP = "legal_openexempt_v6_EV_phase_contract_TRAIN12_20261031_run01"
PREVIOUS = "legal_openexempt_v6_EV_content_execution_TRAIN12_20261030_run01"
PHASE_INTERFACE = "EV_clauses_then_procedure_fields_v2"
MAIN = "legal_openexempt_complete_output_utility_public_assets128_20261030_run01"
STRICT = "legal_openexempt_v6_strict_policy_control_public_assets128_20261030_run01"
MAIN_CONFIG = "configs/openexempt_complete_output_utility_public_assets128_20261030_run01.json"
MAIN_BANK = "48746352543b1a75627eb3cc9480a2257f42107fde544080aefbadc9cd2fca5d"
PLAN = ("artifacts/research/openexempt_legal_scope_20261020/"
        "Utility_v6_EV_phase_only_contract_TRAIN12_decision_20261031.json")
PLAN_SHA = "eabf96dbd913f4ce01cf86fe5886cc84e0a793fc68bef367540d2c8e8d9b5d5a"
FIELDS = ("when", "procedure", "avoid_when")
LIMITS = {"propose": (12, 2), "screen": (24, 0), "confirm": (256, 0)}


class StrictStillLive(RuntimeError):
    pass


def ref(path):
    return {"path": str(path.relative_to(ROOT)), "sha256": sha(path)}


def strict_finished():
    """A live PID or an unpreserved terminal must never release the GPU queue."""
    stat = Path("/proc/425484/stat")
    if stat.exists():
        fields = stat.read_text().rsplit(")", 1)[1].split()
        if fields[19] == "535803398" and fields[0] not in ("Z", "X"):
            raise StrictStillLive("The original strict control is still live; no diagnostic calls")
    source = ROOT / "runs" / STRICT
    if (source / "failure.json").exists():
        raise RuntimeError("Preserve and resolve the failed strict control before diagnosis")
    done = read(source / "completion.json")
    if done["status"] != "completed_bounded_mechanism_study":
        raise ValueError("This protocol requires the complete strict-control stream")
    receipt = read(source / "terminal_preservation.json")
    if len(receipt["paths"]) != 2:
        raise ValueError("The strict terminal has not been preserved on both disks")


def validate_config(path):
    cfg = read(path)
    stage = cfg["diagnostic_stage"]
    if stage not in LIMITS or cfg["run_id"] != GROUP + "_" + stage:
        raise ValueError("Only the declared three stages of this one window are allowed")
    parent = read(ROOT / MAIN_CONFIG)
    for key in ("generation", "teacher", "phase_dispatch", "inference_environment",
                "input_packet", "grading_directory", "execution_contract",
                "execution_contract_version", "actor_skill_order", "library_token_hard_cap"):
        if cfg[key] != parent[key]:
            raise ValueError("The diagnostic changed the original execution profile: " + key)
    if (cfg.get("teacher_stage_interface") != PHASE_INTERFACE
            or cfg.get("diagnostic_not_formal_training") is not True
            or cfg["initial_library_publication"] != f"runs/{MAIN}/publications/b8.json"
            or cfg["planned_new_native_calls_max"] != LIMITS[stage][0]
            or cfg["planned_teacher_responses_max"] != LIMITS[stage][1]
            or cfg["protocol"] != read(ROOT / PLAN)["protocol"]["path"]):
        raise ValueError("Declare the actual diagnostic bank, budget and protocol")
    if sha(ROOT / PLAN) != PLAN_SHA:
        raise ValueError("The fixed TRAIN12 decision plan changed")
    plan = read(ROOT / PLAN)
    if sha(ROOT / cfg["protocol"]) != plan["protocol"]["sha256"]:
        raise ValueError("The decision protocol changed after fixing the cohort")
    if csha(read(ROOT / cfg["initial_library_publication"])["bank"]) != MAIN_BANK:
        raise ValueError("Use the completed actual main8 bank, not a chosen checkpoint")
    for name, digest in read((ROOT / MAIN_CONFIG).with_suffix(".frozen.json"))["files"].items():
        if sha(ROOT / name) != digest:
            raise ValueError("Original source/input profile changed: " + name)
    strict_finished()
    if stage != "propose":
        RepresentationDiagnosis.proposals()  # Bind real reviewed banks before freeze, not placeholders.
    if stage == "confirm":
        screen = ROOT / "runs" / (GROUP + "_screen")
        if ((screen / "failure.json").exists()
                or read(screen / "completion.json")["status"] != "completed_screen_qualified"
                or len(read(screen / "terminal_preservation.json")["paths"]) != 2):
            raise ValueError("Full128 requires the qualified, preserved real screen before freeze")
    return cfg, plan


def changed_block(bank, sid):
    records = [s for s in bank if s["id"] == sid]
    if len(records) != 1:
        raise ValueError("Clause repairs target one existing skill ID")
    blocks = [b for b in records[0]["guidance"]["by_task"] if b["tasks"] == ["EV"]]
    if len(blocks) != 1:
        raise ValueError("This diagnostic requires the existing separate EV projection")
    return blocks[0]


def phase_schema(parent, ids, variant):
    """Expose only the fields that this stage is allowed to change."""
    properties = {
        "skill_id": {"type": "string", "enum": [s["id"] for s in task_view(parent, "EV")]},
        "source_case_ids": {"type": "array", "minItems": 1,
                           "items": {"type": "integer", "enum": sorted(ids)}}}
    if variant == "A":
        properties.update({
            "field": {"type": "string", "enum": list(FIELDS)},
            "old_text": {"type": "string", "minLength": 1},
            "replacement_text": {"type": "string", "minLength": 1}})
        key = "clause_repairs"
    else:
        properties["procedure"] = {"type": "string", "minLength": 1}
        key = "procedure_edits"
    item = {"type": "object", "additionalProperties": False,
            "properties": properties, "required": list(properties)}
    return {"type": "object", "additionalProperties": False,
            "properties": {key: {"type": "array", "items": item}}, "required": [key]}


def apply_phase_edits(parent, edits, ids, variant):
    """Apply text fields, not model-written bank copies or inference programs."""
    candidate, used = copy.deepcopy(parent), set()
    for edit in edits:
        if (not edit["source_case_ids"] or not set(edit["source_case_ids"]) <= ids):
            raise ValueError("Each field edit needs supplied TRAIN support")
        sid = edit["skill_id"]
        original, block = changed_block(parent, sid), changed_block(candidate, sid)
        if variant == "A":
            field, old, new = edit["field"], edit["old_text"], edit["replacement_text"]
            key = sid, field, old
            if (field not in FIELDS or key in used or not old or old == new
                    or original[field].count(old) != 1 or block[field].count(old) != 1):
                raise ValueError("Use disjoint unique original clauses, not a rewrite or cleanup")
            if any(marker in new for marker in ("Execution example:", "citation_ref", "claim_value")):
                raise ValueError("A cannot add an execution or native-output example")
            block[field] = block[field].replace(old, new, 1)
        else:
            key = sid
            if key in used or not edit["procedure"]:
                raise ValueError("Replace each existing EV procedure at most once")
            block["procedure"] = edit["procedure"]
        used.add(key)
    return candidate


PHASE_COMMON = (
    "Edit reusable legal guidance for the SAME frozen Qwen3-8B on the supplied "
    "OpenExempt TRAIN facts, statutes and original targets. All targets are already-seen "
    "TRAIN feedback, never TEST. The only actual predictions are fresh ORIGINAL-parent "
    "diagnostic references, not an executed or successful corrected library. The task "
    "returns all eligible asset-law alternatives independently and their whole-asset "
    "amounts; it does not allocate one portfolio across assets. Preserve the benchmark's "
    "supplied statute version, category conditions and item-level versus debtor-level "
    "limits. Never blanket-double every ceiling for spouses. No case IDs, actual debtor "
    "names, instance asset descriptions or values, answer tables, new legal provisions, "
    "program operators, inference tools or fallback. Public statutory citations and real "
    "caps may appear when grounded in the supplied sources. The complete serialized "
    "library must remain within4096 target-tokenizer tokens; the budget receipt gives "
    "actual headroom. All EC guidance is protected. Return only the requested fields."
)
PHASE_A = (
    " PHASE A IS LEGAL CONTENT ONLY. Correct an actually false or missing legal condition, "
    "citation or real ceiling using a unique literal span in an existing EV block. Quote "
    "the original span and its supported replacement with supplied source IDs. Keep every "
    "unrelated character unchanged. Do not rewrite a correct rule because the executor "
    "failed it; do not reorder execution steps, add reminders, worked examples, JSON "
    "illustrations or execution diagnoses. Those belong to B. Do not return a whole bank "
    "or diagnosis labels. Use disjoint original spans; do not introduce text and then "
    "edit that newly introduced text. An empty clause_repairs array is allowed if no "
    "supported content correction exists. No second quality attempt is scheduled."
)
PHASE_B = (
    " PHASE B IS EXECUTION REPRESENTATION ONLY. A is fixed corrected content, NOT an "
    "executed or proven-successful library. Preserve exactly its applicability conditions, "
    "real caps and citations; when, avoid_when, jurisdiction and every other field are "
    "unchangeable. Return procedure_edits only. Make the EV procedures compact and "
    "operational: bind variables to the supplied whole-asset facts, identify the applicable "
    "legal ceiling, calculate the minimum, and retain independent alternatives. Include "
    "a short hypothetical native JSON worked illustration with citation_ref/claim_value, "
    "clearly identifying illustrative references rather than memorizing a current asset "
    "or answer. Hypothetical values must not be presented as statutory caps. Do not add a "
    "new legal repair or infer an A/B outcome: none is available. Procedures are guidance "
    "for the original actor, not a new solver or execution layer. An empty procedure_edits "
    "array is allowed; no second quality attempt is scheduled."
)


def gains(before, after):
    a, b = metrics(before)["EV"], metrics(after)["EV"]
    return {key: 100 * (b[key] - a[key]) for key in ("f1", "full_output_f1")}


def subset(records, ids):
    return [r for r in records if r["case_id"] in ids]


class RepresentationDiagnosis(Online):
    def __init__(self, config_path):
        self.diagnostic, self.plan = validate_config(config_path)
        self.stage = self.diagnostic["diagnostic_stage"]
        self._reservations, self._reservation_lock = 0, threading.Lock()
        super().__init__(config_path)
        self.parent = copy.deepcopy(self.bank)
        self.ids = {v["source_case_id"] for v in self.plan["fixed_12_TRAIN_sources"]}
        self.controls = {v["source_case_id"] for v in self.plan["fixed_12_TRAIN_sources"]
                         if v["selection_role"] == "context_correct_control"}
        self.ev = [r for r in self.rows if r["family"] == "EV"]
        if (len(self.ev) != 128 or {r["case_id"] for r in self.ev} != set(range(181, 309))
                or len(self.ids) != 12 or len(self.controls) != 5):
            raise ValueError("Only the fixed original128 TRAIN and its fixed12 are permitted")

    def call(self, *args, **kwargs):
        with self._reservation_lock:
            if self._reservations >= LIMITS[self.stage][0]:
                raise RuntimeError("Physical native-call limit reached; no retry or extension")
            self._reservations += 1
        return Online.call(self, *args, **kwargs)

    def record(self, name, value):
        RunStore.immutable_json(self.out / name, value)

    def validate_bank(self, parent, candidate):
        validate_scoped_bank(candidate)
        validate_scopes(candidate, self.rows[0]["components"]["statutes"])
        validate_task_projection_edit(parent, candidate, "EV")
        count = self.meter.token_count(text=json.dumps(candidate, ensure_ascii=False, separators=(",", ":")))
        if count > 4096:
            raise ValueError("Complete bank over4096 tokens; retain failure without teacher reroll")
        for row in self.rows:
            if row["family"] == "EC":
                args = dict(grounded=True, direct_numeric=True, asset_references=True)
                if actor_payload(row, self.parent, **args)[:2] != actor_payload(row, candidate, **args)[:2]:
                    raise ValueError("The diagnostic changed an EC production message or schema")
        return count

    def teacher_packet(self, bank, observations, *, variant):
        focus = [r for r in self.ev if r["case_id"] in self.ids]
        # Only real historical empty records satisfy the original serializer's
        # bookkeeping. They are removed before the diagnostic wire is written.
        empty = []
        for n in range(1, 9):
            data = read(ROOT / "runs" / MAIN / f"batches/b{n}_prequential_records.json")
            empty.extend(r for r in data["empty"] if r["family"] == "EV" and r["case_id"] in self.ids)
        self.bank = copy.deepcopy(bank)
        self.prequential_empty = empty
        self.prequential_frozen = empty
        body = self.teacher_body(focus, focus, observations, [], teaching_task="EV")
        for case in body["already_seen_training"]:
            for key in list(case):
                if key.startswith(("actual_same_case_", "frozen_initial_answer_")):
                    del case[key]
            if variant == "B":
                case["actual_diagnostic_reference_answer"] = case.pop("actual_parent_answer")
        for key in ("skill_commit_policy", "adaptive_commit_objective", "admission_contract",
                    "admission_constraints", "rejected_candidate_feedback",
                    "public_TRAIN_edit_coordinates_before_proposed_shared_edits",
                    "execution_teaching_contract"):
            body.pop(key, None)
        body["teacher_evidence_contract"] = "bounded_seen_TRAIN_content_then_representation_diagnosis"
        body["diagnostic_contract"] = {
            "variant": variant, "phase_only_output_interface": PHASE_INTERFACE,
            "no_generic_execution_diagnosis_contract": True,
            "fresh_reference_bank_sha256": MAIN_BANK,
            "reference_generated_in_this_decision_window": True,
            "current_A_library_has_not_been_executed": variant == "B",
            "no_A_or_B_candidate_outcomes_available": True,
            "UPDATE_existing_EV_blocks_only": True,
            "no_private_limit_metadata_or_TEST": True,
            "not_a_new_formal_learning_recipe": True}
        if variant == "B":
            body["bounded_emitted_evidence_contract"]["roles"] = ["actual_diagnostic_reference_answer"]
            body["prospective_actor_skill_messages"] = body.pop("actual_actor_skill_messages")
        self.bank = copy.deepcopy(self.parent)
        return body

    def propose(self):
        focus = [r for r in self.ev if r["case_id"] in self.ids]
        before = self._dispatch.native(
            lambda r: self.answer(r, self.parent, "fresh_parent12", "parent"), focus)
        self.grade(before)
        self.record("fresh_parent12.json", {"records": before, "metrics": metrics(before)})
        observations = {(r["case_id"], r["family"]): r for r in before}
        banks, contents = {}, []
        for variant in ("A", "B"):
            parent = self.parent if variant == "A" else banks["A"]
            body = self.teacher_packet(parent, observations, variant=variant)
            if variant == "B":
                body["fixed_content_repairs_from_A"] = contents
            value = self.teacher_call(
                "variant_" + variant, PHASE_COMMON + (PHASE_A if variant == "A" else PHASE_B),
                body, phase_schema(parent, self.ids, variant))
            key = "clause_repairs" if variant == "A" else "procedure_edits"
            edits = value[key]
            candidate = apply_phase_edits(parent, edits, self.ids, variant)
            if variant == "A":
                contents = edits
            tokens = self.validate_bank(parent, candidate)
            banks[variant] = candidate
            self.record("candidate_" + variant + ".json", {
                "bank": candidate, "bank_sha256": csha(candidate), "tokens": tokens,
                "phase_only_edit_contract": PHASE_INTERFACE, "field_edits": edits,
                "all128_EC_production_payloads_byte_identical": True})
        return {"status": "completed_proposals_awaiting_main_agent_semantic_review",
                "candidate_bank_sha256": {k: csha(v) for k, v in banks.items()},
                "candidate_outcomes_not_generated": True,
                "fresh_parent12": ref(self.out / "fresh_parent12.json")}

    @staticmethod
    def proposals():
        source = ROOT / "runs" / (GROUP + "_propose")
        if (source / "failure.json").exists():
            raise ValueError("The original proposals failed; no replacement candidates")
        done = read(source / "completion.json")
        if done["status"] != "completed_proposals_awaiting_main_agent_semantic_review":
            raise ValueError("The original two proposals did not complete; no replacement candidates")
        if len(read(source / "terminal_preservation.json")["paths"]) != 2:
            raise ValueError("Preserve paid proposals before candidate replay")
        review = read(source / "proposal_review.json")
        expected = ("A_only_supported_literal_content_repairs", "B_same_corrected_conditions_caps_citations",
                    "both_no_instance_answers", "B_native_illustration_is_hypothetical")
        banks = {v: read(source / ("candidate_" + v + ".json"))["bank"] for v in ("A", "B")}
        if (review["proposal_completion_sha256"] != sha(source / "completion.json")
                or review["candidate_bank_sha256"] != {k: csha(v) for k, v in banks.items()}
                or any(review["checks"].get(k) is not True for k in expected)
                or not review.get("rationale")):
            raise ValueError("Exact proposals require the main agent's substantive audit before replay")
        return source, banks

    def screen(self):
        source, banks = self.proposals()
        before = read(source / "fresh_parent12.json")["records"]
        if len(before) != 12 or {r["case_id"] for r in before} != self.ids:
            raise ValueError("Incomplete fresh parent12")
        # These are this window's new references, not main8's old cached answers.
        for record in before:
            raw = read(ROOT / record["raw_call_path"])
            row = next(r for r in self.ev if r["case_id"] == record["case_id"])
            messages, schema, _ = actor_payload(row, self.parent, grounded=True, direct_numeric=True, asset_references=True)
            q = raw["calls"][0]["request"]
            if (record["bank_sha256"] != MAIN_BANK or record["family"] != "EV"
                    or raw["transport_error"] is not None or len(raw["calls"]) != 1
                    or any(q[k] != self.cfg["generation"][k] for k in ("model", "temperature", "top_p", "top_k", "max_tokens", "seed"))
                    or q.get("chat_template_kwargs", {}).get("enable_thinking", True) is not True
                    or q["messages"] != messages or q["response_format"]["json_schema"]["schema"] != schema
                    or not str(ROOT / record["raw_call_path"]).startswith(str(source / "native/fresh_parent12/"))):
                raise ValueError("Fresh parent reference provenance changed")
            fingerprint = csha({"messages": messages, "schema": schema, "generation": self.cfg["generation"]})
            self.request_cache[fingerprint] = {"response": raw["response"], "raw_call_path": record["raw_call_path"]}
        rows = [r for r in self.ev if r["case_id"] in self.ids]
        def answer_row(row):
            order = ("A", "B") if row["case_id"] % 2 else ("B", "A")
            return {v: self.answer(row, banks[v], "candidate_screen12", v) for v in order}
        answers = self._dispatch.native(answer_row, rows)
        conditions = {v: self.grade([a[v] for a in answers]) for v in ("A", "B")}
        results = {}
        for variant, after in conditions.items():
            delta = gains(before, after)
            control = gains(subset(before, self.controls), subset(after, self.controls))
            results[variant] = {"gain_pp": delta, "correct_control_gain_pp": control,
                "eligible": min(delta.values()) >= 2 - 1e-10 and min(control.values()) >= -1 - 1e-10,
                "metrics": metrics(after), "paired": paired_effect(before, after), "records": after}
        eligible = [v for v in ("A", "B") if results[v]["eligible"]]
        winner = max(eligible, key=lambda v: (min(results[v]["gain_pp"].values()),
                     sum(results[v]["gain_pp"].values()), v == "A")) if eligible else None
        return {"status": "completed_screen_qualified" if winner else "closed_no_qualified_representation",
                "winner": winner, "fresh_parent12_source": ref(source / "fresh_parent12.json"),
                "results": results, "A_to_B_gain_pp": gains(conditions["A"], conditions["B"])}

    def confirm(self):
        _, banks = self.proposals()
        screen_path = ROOT / "runs" / (GROUP + "_screen") / "completion.json"
        screen = read(screen_path)
        if screen["status"] != "completed_screen_qualified" or screen["winner"] not in banks:
            raise ValueError("No qualified fixed12 candidate; close this branch without full replay")
        if len(read(screen_path.with_name("terminal_preservation.json"))["paths"]) != 2:
            raise ValueError("Preserve the completed screen before fresh full128 replay")
        winner = screen["winner"]
        if self.request_cache:
            raise ValueError("Full128 starts fresh, without screen/main8 response imports")
        def answer_row(row):
            order = ("parent", "candidate") if row["case_id"] % 2 else ("candidate", "parent")
            return {v: self.answer(row, self.parent if v == "parent" else banks[winner],
                                  "fresh_paired128", v) for v in order}
        answers = self._dispatch.native(answer_row, self.ev)
        before, after = [self.grade([a[v] for a in answers]) for v in ("parent", "candidate")]
        delta = gains(before, after)
        old = gains(subset(before, set(range(181, 197))), subset(after, set(range(181, 197))))
        later = gains(subset(before, set(range(197, 309))), subset(after, set(range(197, 309))))
        qualified = min(delta.values()) >= 2 - 1e-10 and min(old.values()) >= -1 - 1e-10 and min(later.values()) >= -1e-10
        self.validate_bank(self.parent, banks[winner])
        return {"status": "completed_eligible_for_new_formal_recipe" if qualified else "closed_full128_not_qualified",
            "winner": winner, "screen_completion": ref(screen_path), "gain_pp": delta,
            "old_B1_16_gain_pp": old, "subsequent112_gain_pp": later,
            "five_original_correct_controls_gain_pp": gains(subset(before, self.controls), subset(after, self.controls)),
            "parent_metrics": metrics(before), "candidate_metrics": metrics(after),
            "paired": paired_effect(before, after), "parent_records": before, "candidate_records": after,
            "per_original_batch_gain_pp": {str(n+1): gains(subset(before, set(range(181 + 16*n, 197 + 16*n))),
                subset(after, set(range(181 + 16*n, 197 + 16*n)))) for n in range(8)},
            "bank_not_an_equal_budget_formal_main_table_condition": True}

    def run(self):
        status = "failed"
        try:
            result = getattr(self, self.stage)()
            earlier = [read(ROOT / "runs" / (GROUP + "_" + s) / "completion.json")
                       for s in ("propose", "screen")[:("propose", "screen", "confirm").index(self.stage)]]
            linked_native = len(self.native) + sum(v["actual_native_calls"] for v in earlier)
            linked_teacher = len(self.teachers) + sum(v["actual_teacher_responses"] for v in earlier)
            if linked_native > 300 or linked_teacher > 2:
                raise ValueError("The combined diagnostic window exceeded its hard budget")
            previous = read(ROOT / "runs" / (PREVIOUS + "_propose") / "failure.json")
            development_native = previous["actual_native_calls"] + linked_native
            development_teacher = previous["actual_teacher_responses"] + linked_teacher
            if development_native > 312 or development_teacher > 3:
                raise ValueError("Combined development including the failed first interface exceeded its budget")
            result.update({"at": now(), "run_id": self.run_id, "diagnostic_stage": self.stage,
                "prior_failed_window": PREVIOUS + "_propose",
                "cumulative_development_native_calls": development_native,
                "cumulative_development_teacher_responses": development_teacher,
                "actual_native_calls": len(self.native), "actual_teacher_responses": len(self.teachers),
                "actual_teacher_attempts": self.teacher_attempts, "linked_native_calls": linked_native,
                "linked_teacher_responses": linked_teacher,
                "linked_teacher_attempts": self.teacher_attempts + sum(v["actual_teacher_attempts"] for v in earlier),
                "native_prompt_tokens": sum(v["response"]["prompt_tokens"] for v in self.native if v["response"]),
                "native_completion_tokens": sum(v["response"]["completion_tokens"] for v in self.native if v["response"]),
                "teacher_reported_usage": {k: sum(t["invocation"]["usage"].get(k, 0) for t in self.teachers)
                    for k in ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens")},
                "no_TEST_or_formal_learning_success_claim": True})
            self.check()
            self.record("completion.json", result)
            status = result["status"]
            print(json.dumps({k: result[k] for k in ("status", "run_id", "actual_native_calls", "actual_teacher_responses")}), flush=True)
        except BaseException as exc:
            self.record("failure.json", {"at": now(), "error": repr(exc), "traceback": traceback.format_exc(),
                "actual_native_calls": len(self.native), "actual_teacher_responses": len(self.teachers),
                "actual_teacher_attempts": self.teacher_attempts, "no_quality_retry_or_fallback": True})
            raise
        finally:
            self.progress("terminal", state=status)
            files = [str(p.relative_to(ROOT)) for p in self.out.rglob("*") if p.is_file() and "/cache/" not in str(p)]
            self.record("terminal_preservation.json", preserve(self.run_id, "actual-terminal", files))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "run"))
    parser.add_argument("config", type=Path)
    args = parser.parse_args()
    config = args.config.resolve()
    cfg, _ = validate_config(config)
    if args.action == "freeze":
        extra = [Path(__file__).resolve(), ROOT / PLAN, ROOT / MAIN_CONFIG,
                 (ROOT / MAIN_CONFIG).with_suffix(".frozen.json"), ROOT / "runs" / MAIN / "completion.json",
                 ROOT / "runs" / STRICT / "completion.json", ROOT / "runs" / STRICT / "terminal_preservation.json"]
        extra += list((ROOT / "runs" / MAIN / "batches").glob("*_prequential_records.json"))
        failed = ROOT / "runs" / (PREVIOUS + "_propose")
        extra += [failed / n for n in ("failure.json", "terminal_preservation.json", "teacher/variant_A/response.json")]
        extra += [ROOT / "artifacts/research/openexempt_legal_scope_20261020/Utility_v6_TRAIN12_failed_A_phase_contract_mixed_example_full_source397_paid_before_interface_fix_dual_20261031.json"]
        for phase in ("propose", "screen")[:("propose", "screen", "confirm").index(cfg["diagnostic_stage"])]:
            extra += [p for p in (ROOT / "runs" / (GROUP + "_" + phase)).rglob("*")
                      if p.is_file() and "/cache/" not in str(p) and p.name != "progress.json"]
        freeze(config, additional_sources=extra)
    else:
        with (ROOT / "artifacts/openexempt_training.lock").open("a+") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            RepresentationDiagnosis(config).run()


if __name__ == "__main__":
    main()
