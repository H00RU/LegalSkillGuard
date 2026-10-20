"""ACE's native text-playbook roles adapted to the public EC/EV interface.

Uses the pinned author prompts and ADD/counter helpers, not the NDA learner.
Starts without our blind legal/program bank. The declared profile uses either
the common direct task answer or the historical common inline arithmetic.
This module is a role adapter; it does not establish baseline performance.
"""

from __future__ import annotations

import copy
import json

from jsonschema import validate

from experiments.openexempt_online import actor_payload
from legal_skill_guard.learning.ace_native import (
    apply_curator_operations,
    get_next_global_id,
    get_playbook_stats,
    update_bullet_counts,
)
from legal_skill_guard.learning.claim_execution import execute_claims
from legal_skill_guard.learning.experiment import (
    ACE_SECTIONS,
    CURATOR_PROMPT,
    GENERATOR_PROMPT,
    PUBLIC_ACE_REFLECTOR_PROMPT,
    bullets,
)
from legal_skill_guard.learning.legal_namespace import (
    decode_asset_references,
    decode_claim_plan,
    decode_classification,
    decode_reference,
    public_asset_catalog,
    public_catalog,
)


def public_explanation_prompt(prompt):
    # Retain the author's field names, without requesting a teacher's hidden CoT.
    return prompt.replace(
        "your chain of thought / reasoning / thinking process, detailed analysis and calculations",
        "a concise source-supported public explanation, not hidden reasoning",
    ).replace(
        "Your chain of thought / reasoning / thinking process, detailed analysis and calculations",
        "A concise source-supported public explanation, not hidden reasoning",
    ).replace("Show your reasoning step-by-step", "Provide a concise public explanation")


def generator_payload(row, playbook, *, direct_numeric=False, training_reflection=None,
                      asset_references=False):
    original, native_schema, _ = actor_payload(row, [], direct_numeric=direct_numeric,
                                              asset_references=asset_references)
    known = bullets(playbook)
    ids = {"type": "array", "items": {"type": "string"}}
    if known:
        ids["items"]["enum"] = list(known)
    else:
        ids["maxItems"] = 0
    schema = {"type": "object", "additionalProperties": False,
        "required": ["reasoning", "bullet_ids", "final_answer"], "properties": {
            "reasoning": {"type": "string"}, "bullet_ids": ids,
            "final_answer": native_schema}}
    system = original[0]["content"] + (
        " In this ACE adaptation, all preceding benchmark root/final-output instructions "
        "describe the VALUE of final_answer. The actual outer JSON has exactly reasoning, "
        "bullet_ids and final_answer. reasoning is a concise public explanation, not "
        "private thinking. Cite only actually relevant playbook IDs.")
    if training_reflection is None:
        system += " No current reflection or answer feedback is available at this first encounter."
        reflection = "(empty: no current-case feedback)"
    else:
        system += (" This is a released-TRAIN regeneration with a recorded reflection. "
                   "It never replaces the independently saved first-encounter prediction.")
        reflection = json.dumps(training_reflection, ensure_ascii=False)
    prompt = public_explanation_prompt(GENERATOR_PROMPT).format(
        playbook, reflection, original[-1]["content"],
        "All permitted public context is in the question; no outside law or tools.")
    return [{"role": "system", "content": system}, {"role": "user", "content": prompt}], schema


def decode_generator(row, playbook, submitted, *, direct_numeric=False, asset_references=False):
    """Unpack fields and decode labels; execute math only in the declared program profile."""
    _, schema = generator_payload(row, playbook, direct_numeric=direct_numeric,
                                  asset_references=asset_references)
    validate(submitted, schema)
    cited = submitted["bullet_ids"]
    if len(cited) != len(set(cited)):
        raise ValueError("Repeated native ACE bullet citation, no deduplication")
    native = submitted["final_answer"]
    if asset_references:
        native = decode_asset_references(native, public_asset_catalog(row))
    receipt = program = None
    if row["family"] == "EV" and direct_numeric:
        catalog = public_catalog(row)
        answer = {name: [{"citation": decode_reference(claim["citation_ref"], catalog),
                          "claim_value": claim["claim_value"]} for claim in claims]
                  for name, claims in native.items()}
    elif row["family"] == "EV":
        program = decode_claim_plan(native, public_catalog(row))
        answer, receipt = execute_claims(program["assets"], row["components"]["facts"],
                                         row["components"]["statutes"], [])
    else:
        answer = decode_classification(native, public_catalog(row))
    return {"answer": answer, "native_program": program, "execution_receipt": receipt,
            "used_bullet_ids": copy.deepcopy(cited),
            "public_rationale": submitted["reasoning"]}


def reflector_request(row, observation, target, playbook, environment_feedback, *,
                      direct_numeric=False, asset_references=False):
    """TRAIN-only feedback for this source, never used to repair its first score."""
    if (observation["case_id"], observation["family"]) != (row["case_id"], row["family"]):
        raise ValueError("Reflect only this actual source/task observation")
    known = bullets(playbook)
    # None explicitly means IDs were unavailable after a malformed native output.
    # It does not invent an empty successful answer or retry the legal task.
    cited = observation["used_bullet_ids"]
    if cited is None:
        if not observation.get("parse_error"):
            raise ValueError("Missing bullet provenance without an actual parse error")
        cited = []
    if len(cited) != len(set(cited)) or not set(cited) <= set(known):
        raise ValueError("Reflection must retain valid actual native bullet citations")
    fields = ("reasoning", "error_identification", "root_cause_analysis", "correct_approach", "key_insight")
    tags = {"type": "array", "minItems": len(cited), "maxItems": len(cited), "items": {
        "type": "object", "additionalProperties": False, "required": ["id", "tag"],
        "properties": {"id": {"type": "string"},
                       "tag": {"type": "string", "enum": ["helpful", "harmful", "neutral"]}}}}
    if cited:
        tags["items"]["properties"]["id"]["enum"] = cited
    schema = {"type": "object", "additionalProperties": False,
        "required": [*fields, "bullet_tags"], "properties": {
            **{k: {"type": "string"} for k in fields}, "bullet_tags": tags}}
    original, _, _ = actor_payload(row, [], direct_numeric=direct_numeric,
                                  asset_references=asset_references)
    prompt = PUBLIC_ACE_REFLECTOR_PROMPT.format(original[-1]["content"],
        json.dumps(observation, ensure_ascii=False),
        json.dumps(observation.get("answer"), ensure_ascii=False),
        json.dumps(target, ensure_ascii=False),
        json.dumps(environment_feedback, ensure_ascii=False),
        "\n".join(known[s]["raw_line"] for s in cited))
    return prompt, schema, cited


def validate_reflection(value, schema, cited):
    validate(value, schema)
    ids = [tag["id"] for tag in value["bullet_tags"]]
    if len(ids) != len(set(ids)) or set(ids) != set(cited):
        raise ValueError("Native reflector must tag exactly its cited bullets once")


def curator_request(playbook, reflections, rows, *, current_step, total_samples, token_budget,
                    direct_numeric=False, all_round_bullet_tags=None, asset_references=False):
    """Native batch counter behavior, then the author's incremental ADD curator."""
    tags = ([tag for reflection in reflections for tag in reflection["bullet_tags"]]
            if all_round_bullet_tags is None else all_round_bullet_tags)
    known = bullets(playbook)
    if any(tag["id"] not in known for tag in tags):
        raise ValueError("Unknown bullet tag cannot update native counters")
    # The pinned author's helper uses the final tag for a repeated ID in a batch.
    # Preserve it rather than silently replacing it by per-document summation.
    counted = update_bullet_counts(playbook, tags) if tags else playbook
    context = [actor_payload(row, [], direct_numeric=direct_numeric,
                            asset_references=asset_references)[0][-1]["content"]
               for row in rows]
    prompt = public_explanation_prompt(CURATOR_PROMPT).format(
        token_budget=token_budget, current_step=current_step, total_samples=total_samples,
        playbook_stats=json.dumps(get_playbook_stats(counted)),
        recent_reflection=json.dumps(reflections, ensure_ascii=False),
        current_playbook=counted, question_context=json.dumps(context, ensure_ascii=False))
    sections = [s.lower().replace(" ", "_").replace("&", "and") for s in ACE_SECTIONS]
    schema = {"type": "object", "additionalProperties": False,
        "required": ["reasoning", "operations"], "properties": {
            "reasoning": {"type": "string"}, "operations": {"type": "array", "items": {
                "type": "object", "additionalProperties": False,
                "required": ["type", "section", "content"], "properties": {
                    "type": {"type": "string", "enum": ["ADD"]},
                    "section": {"type": "string", "enum": sections},
                    "content": {"type": "string", "minLength": 1}}}}}}
    return prompt, schema, counted


def commit_additions(counted, value, schema, *, token_count, token_budget):
    """Apply native ADD/count semantics, with no score gate or content rewriting."""
    validate(value, schema)
    if any("\n" in op["content"] or "\r" in op["content"] or not op["content"].strip()
           for op in value["operations"]):
        raise ValueError("Malformed single-line ACE addition, never repaired")
    result, next_id = apply_curator_operations(counted, value["operations"], get_next_global_id(counted))
    old, new = bullets(counted), bullets(result)
    if not set(old) <= set(new) or any(old[k]["content"] != new[k]["content"] for k in old):
        raise ValueError("Native ADD must not rewrite existing bullet content")
    if len(new) - len(old) != len(value["operations"]):
        raise ValueError("ACE native addition count differs")
    tokens = token_count(text=result)
    if tokens > token_budget:
        raise ValueError("Full native playbook exceeds capacity; do not truncate or score-select")
    return {"playbook": result, "next_id": next_id, "actual_tokens": tokens,
            "stats": get_playbook_stats(result)}
