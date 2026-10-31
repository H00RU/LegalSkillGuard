"""The one v6 explicit-teacher-execution-evidence control.

Reuse Online unchanged. Only the complete outgoing teacher system/body differ;
original labels, selected source IDs, actor interfaces, edits and TRAIN gates do
not. Controller selection and the evolving parent still convey indirect feedback.
This is not label-free or fully feedback-free learning. No run is auto-started.
"""

from __future__ import annotations

import argparse
import copy
import fcntl
from pathlib import Path

from experiments.openexempt_online import ROOT, Online, freeze, read

MAIN_CONFIG = "configs/openexempt_complete_output_utility_public_assets128_20261030_run01.json"
CASE_INPUTS = frozenset({
    "source_case_id", "family", "public_asset_reference_catalog", "facts",
    "public_solved_steps", "public_statutes_ref", "original_training_target",
})
CASE_EXECUTION = frozenset({
    "actual_parent_answer", "actual_same_case_empty_answer",
    "frozen_initial_answer_alias_of", "actual_same_case_frozen_initial_answer",
})
BODY_INPUTS = frozenset({
    "current_source_case_ids", "teacher_evidence_contract", "teaching_task",
    "task_projection_update_contract", "execution_teaching_contract",
    "task_boundary", "current_parent_library", "task_contracts",
    "skill_commit_policy", "adaptive_commit_objective",
    "public_TRAIN_edit_coordinates_before_proposed_shared_edits",
    "full_serialized_library_token_budget", "public_citation_label_catalog",
    "actual_actor_systems", "actual_response_schemas", "actual_actor_skill_messages",
    "actor_visibility_contract", "complete_public_statutes",
    "actual_system_and_response_schema_by_public_context", "already_seen_training",
    "training_evidence_manifest", "future_cases_and_labels_not_supplied",
    "admission_contract", "admission_constraints",
})
BODY_EXECUTION = frozenset({
    "rejected_candidate_feedback", "selected_record_view_preserves_program_answer_score_and_error",
    "native_claim_feedback_contract", "bounded_emitted_evidence_contract",
    "candidate_feedback_contract",
})
MANIFEST_INPUTS = frozenset({
    "current_source_ids_all_included", "selected_historical_source_ids",
    "selected_source_ids", "all_seen_source_ids", "omitted_historical_source_ids",
    "historical_source_limit", "historical_background_source_limit",
    "full_seen_TRAIN_replay_and_acceptance_unchanged", "not_an_independent_validation_set",
    "teaching_task", "selected_task_records", "other_task_predictions_and_targets_not_supplied",
})
MANIFEST_EXECUTION = frozenset({
    "mandatory_feedback_witness_source_ids", "all_bounded_feedback_witnesses_included",
    "public_context_witnesses", "rule",
})


def replace_span(text, start, end, replacement):
    """Exact declared instruction boundaries, not a heuristic text scrubber."""
    if text.count(start) != 1 or text.count(end) != 1:
        raise ValueError("The matched v6 teacher instruction boundary changed")
    left, right = text.index(start), text.index(end)
    if left >= right:
        raise ValueError("Teacher instruction boundaries are out of order")
    return text[:left] + replacement + text[right:]


def teacher_evidence_view(system, body, *, visible=True):
    """True is byte-identical; false removes the teacher's explicit outcome channel."""
    if type(visible) is not bool:
        raise ValueError("Declare teacher execution visibility as a boolean")
    if visible:
        return system, body
    if set(body) - BODY_INPUTS - BODY_EXECUTION:
        raise ValueError("Unclassified teacher field; inspect it before this control runs")
    result = {k: copy.deepcopy(v) for k, v in body.items() if k in BODY_INPUTS}
    cases = []
    for case in body["already_seen_training"]:
        if set(case) - CASE_INPUTS - CASE_EXECUTION or not CASE_INPUTS <= set(case):
            raise ValueError("Unclassified or missing original TRAIN case input")
        cases.append({k: copy.deepcopy(v) for k, v in case.items() if k in CASE_INPUTS})
    result["already_seen_training"] = cases
    manifest = body["training_evidence_manifest"]
    if set(manifest) - MANIFEST_INPUTS - MANIFEST_EXECUTION:
        raise ValueError("Unclassified evidence-selection field")
    result["training_evidence_manifest"] = {
        k: copy.deepcopy(v) for k, v in manifest.items() if k in MANIFEST_INPUTS}
    result["training_evidence_manifest"]["selection_rule"] = (
        "The unchanged controller selected these source IDs. Explicit executor outcomes "
        "and outcome-labelled selection annotations are not supplied to the teacher.")
    for key in ("recurrent_failure_requires_instruction_reconsideration",
                "public_native_final_is_observed_not_automatically_correct"):
        result["execution_teaching_contract"].pop(key, None)
    result["teacher_execution_evidence_visible"] = False

    system = replace_span(system,
        "Improve the supplied frozen Qwen3-8B's reusable legal decision procedures from ",
        "The actor answers EC and EV directly,",
        "Improve the supplied frozen Qwen3-8B's reusable legal decision procedures from "
        "the already-seen TRAIN facts, original targets, public statutes and current skill library. ")
    system = replace_span(system, "Plain-language statutory calculations may be taught ",
        "Use only the benchmark statute version",
        "Plain-language statutory calculations may be taught where the supplied facts, law "
        "and original TRAIN targets warrant them. Prioritize reusable legal-selection and "
        "factual-grounding instructions. ")
    system = replace_span(system,
        "Compare the actual parent prediction, released target, and same-case controls.",
        "Write short decision instructions:",
        "Derive the eligible asset-law alternatives and amounts from the original facts, "
        "law and released target, then compare those requirements with the current guidance. "
        "The original target is authoritative. Missing alternatives, extra alternatives and "
        "incorrect amounts require different instructions. Retain every independently eligible "
        "alternative rather than replacing a specific law with a general-property alternative "
        "or vice versa. For valuation, state the final protected amount for the WHOLE named "
        "asset. Distinguish a per-debtor statutory ceiling from the asset-level output; do not "
        "leave a half-interest as the final answer or double every ceiling merely because "
        "two debtors exist. Attach exclusions to the particular alternative they exclude, "
        "not every other applicable alternative. Derive branches from the supplied statute "
        "and TRAIN targets, not a universal spouse or allocation rule. Verify the task and "
        "statute before treating a cap as an eligibility test. ")
    system = replace_span(system, "Bounded emitted excerpts are unverified executor output,",
        "Return only the exact delta JSON schema.", "")
    system = replace_span(system, "Repeated omissions across supplied sources,",
        "Use actual_actor_skill_messages", "")
    system = replace_span(system, "Reserve EXECUTION_LAPSE for an isolated slip supported ",
        "Quote its current rule anchor.",
        "No actual executor predictions, scores, reasoning or success/failure observations "
        "are supplied. Do not invent them or infer an execution lapse from a target alone. "
        "SKILL_DEFECT remains available for a missing, incorrect, incomplete or inadequate "
        "instruction supported by facts, law, original targets and the current library. ")
    system = replace_span(system, "Public native final submissions show the actor's actual ",
        "Deidentify instances and do not save whole training answers.",
        "Use the supplied actor systems and response schemas for any hypothetical native "
        "output illustration, not an invented successful execution. ")
    system = replace_span(system, "Use this task's actual answers and released targets ",
        "Resolve invariant conditions",
        "Use this task's original facts, released targets, public law and current guidance "
        "to teach its eligibility, co-applicable alternatives and amount computation. ")
    marker = " Candidate feedback retains at most the latest unsuccessful or partially "
    if system.count(marker) != 1:
        raise ValueError("The matched v6 historical-feedback instruction changed")
    system = system[:system.index(marker)] + (
        " Target only IDs in this attempt's actual parent, never IDs created earlier in "
        "the same delta. Keep committed knowledge and propose grounded changes under the "
        "declared full TRAIN admission contract. Actual candidate replays and admission "
        "remain controller-side; their outcomes are not supplied in this condition. "
        "No inference retry or access to future cases is introduced.")
    validate_withheld_request(system, result)
    return system, result


def validate_withheld_request(system, body):
    """The same exact public-context contract for generation and final provenance."""
    forbidden_instructions = (
        "Compare the actual parent prediction", "same-case controls.",
        "Repeated omissions across supplied sources,", "Candidate feedback retains at most",
        "Use this task's actual answers", "Public native final submissions show",
    )
    if (body.get("teacher_execution_evidence_visible") is not False
            or set(body) != BODY_INPUTS | {"teacher_execution_evidence_visible"}
            or set(body["training_evidence_manifest"]) != MANIFEST_INPUTS | {"selection_rule"}
            or any(set(case) != CASE_INPUTS for case in body["already_seen_training"])
            or any(text in system for text in forbidden_instructions)):
        raise ValueError("The actual teacher request violates the declared withheld-evidence contract")


class TeacherExecutionWithheld(Online):
    def teacher_call(self, name, system, body, schema):
        system, body = teacher_evidence_view(system, body, visible=False)
        return Online.teacher_call(self, name, system, body, schema)


def validate_config(path):
    cfg, parent = read(path), read(ROOT / MAIN_CONFIG)
    differences = {k for k in cfg.keys() | parent.keys() if cfg.get(k) != parent.get(k)}
    if (differences != {"run_id", "protocol", "teacher_execution_evidence_visible"}
            or cfg["teacher_execution_evidence_visible"] is not False
            or cfg["run_id"] == parent["run_id"]):
        raise ValueError("Only the same-v6 teacher explicit-execution channel may change")
    return cfg


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "run"))
    parser.add_argument("config", type=Path)
    args = parser.parse_args()
    config = args.config.resolve()
    validate_config(config)
    if args.action == "freeze":
        freeze(config, additional_sources=[Path(__file__).resolve(), ROOT / MAIN_CONFIG,
                                          (ROOT / MAIN_CONFIG).with_suffix(".frozen.json")])
    else:
        with (ROOT / "artifacts/openexempt_training.lock").open("a+") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            TeacherExecutionWithheld(config).run()


if __name__ == "__main__":
    main()
