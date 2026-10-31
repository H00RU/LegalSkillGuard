"""Bounded source-disjoint EC/EV skill learning, not a final paper evaluation.

Reuses the audited native/teacher transports and differential edits. Unlike the
old NDA run, training replays can reject ineffective candidate edits. This is
declared TRAIN optimization, not test-time retry or an independent validation
claim. All candidate outputs, costs and rejected edits remain on disk.
Contracts v12/v13 admit public-law/task TRAIN edits; v13 uses direct task answers.
Optional v14 binds the same legal answers to public literal-mention references.
Native-response reuse never reuses a previously computed answer.
"""

from __future__ import annotations

import argparse
import copy
import fcntl
import hashlib
import importlib.metadata
import json
import signal
import tarfile
import traceback
from contextlib import nullcontext
from pathlib import Path

from jsonschema import ValidationError, validate

from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.inference.native import WireClient
from legal_skill_guard.learning.claim_execution import (
    InvalidClaimProgram,
    execute_claims,
    execute_limit,
    law_blocks,
    operator_catalog,
)
from legal_skill_guard.learning.claim_execution import (
    answer_schema as claim_answer_schema,
)
from legal_skill_guard.learning.experiment import Comparison, now, read, sha
from legal_skill_guard.learning.phase_dispatch import PhaseDispatch
from legal_skill_guard.learning.legal_namespace import (
    active_bank,
    allowable_namespaces,
    decode_asset_references,
    decode_claim_plan,
    decode_classification,
    decode_reference,
    public_asset_catalog,
    public_catalog,
    statutory_catalog,
    validate_scopes,
)
from legal_skill_guard.learning.publication import (
    apply_differential_publication,
    differential_schema,
)
from legal_skill_guard.learning.task_scoped_skills import (
    SCOPED_GUIDANCE_SCHEMA,
    compose_legal_edits,
    compose_task_edits,
    legal_edit_coordinates,
    task_view,
    validate_scoped_bank,
)
from legal_skill_guard.openexempt import (
    ACTIVE_CASE_FIELDS,
    FAMILIES,
    ROOT,
    UPSTREAM,
    active_case_input,
    answer_schema,
    evaluate,
    metrics,
    prepare,
    upstream,
)
from legal_skill_guard.utils.hashing import canonical_json_sha256 as csha

EXECUTABLE_GUIDANCE = SCOPED_GUIDANCE_SCHEMA
DIRECT_GUIDANCE = copy.deepcopy(SCOPED_GUIDANCE_SCHEMA)
DIRECT_GUIDANCE["properties"]["operators"]["maxItems"] = 0
ACTOR_SYSTEM = (
    "Apply only the supplied statutes and public solved steps to the original facts. "
    "Return a JSON object mapping actual asset descriptions to ALL applicable public "
    "citation label IDs from the supplied vocabulary, or [] if none. A label is only "
    "the predeclared encoding of its displayed citation; decide legal eligibility yourself."
)
DIRECT_NUMERIC_SYSTEM = (
    "Apply only the original facts, supplied statutes and public solved steps. "
    "Answer the original EV task directly: map actual asset descriptions to ALL "
    "independently applicable citation_ref/claim_value alternatives, or [] if none. "
    "Each public reference only encodes its displayed citation, not eligibility. "
    "Calculate numeric claim_value amounts yourself. Return the exact JSON answer, "
    "not a program, an explanation, a selected portfolio, or a skill-use report."
)

DIRECT_AUTHOR_SYSTEM = (
    "Improve the supplied frozen Qwen3-8B's reusable legal decision procedures from "
    "ACTUAL already-seen OpenExempt TRAIN observations. The actor answers EC and EV "
    "directly, with the same public facts, statutes, solved steps and response schema "
    "as the strong empty-library control. Its weights never change. It has NO program "
    "interpreter or stored numerical routines. All skill operators arrays MUST be empty. "
    "Do not tell it to use null, call a routine, write code, or submit a claim plan. "
    "Plain-language statutory calculations may be taught where an actual error warrants "
    "them, but prioritize observed legal-selection and factual-grounding mistakes. "
    "Use only the benchmark statute version and released TRAIN evidence supplied here; "
    "no tools, outside law, future cases, test answers or invented successful experience. "
    "Compare the actual parent prediction, released target, and same-case controls. "
    "Identify the mistaken legal condition or omitted alternative before changing a skill. "
    "An extra law, a missing law and a wrong amount require different corrections. "
    "The native_claim_feedback identifies these errors with the unchanged original "
    "asset/claim matcher and amount tolerance; the original answer, target and scores "
    "remain authoritative. Repair an omitted alternative with a public factual trigger, "
    "not a circular condition such as 'when already valuing this paragraph'. Retain "
    "every independently eligible alternative rather than replacing a specific law "
    "with a general-property alternative or vice versa. For valuation repairs, state "
    "the final protected amount for the WHOLE named asset. Distinguish a per-debtor "
    "statutory ceiling from the asset-level output; do not leave a half-interest as "
    "the final answer, or double every ceiling merely because two debtors exist. "
    "Attach exclusions to the particular alternative they exclude, not every other "
    "applicable alternative for that asset. Derive the legal branches from the supplied "
    "statute and TRAIN evidence, not a new universal spouse or allocation rule. "
    "Verify the task and supplied statute before treating a cap as an eligibility test. "
    "Write short decision instructions: which factual condition to check, which legal "
    "alternative it enables, and which exception prevents a false positive. Keep correct "
    "unrelated boundaries verbatim; do not rewrite a whole jurisdiction for style, "
    "broaden a rule from one case, or add a generic instruction already present. "
    "Do not store case IDs, debtors, exact asset names or values, answer tables, output "
    "format tricks, or copied target sets in skills. Public statutory citations and "
    "statutory dollar limits may be used where supported by the supplied law. "
    "Each skill has id, hypothesis_ids listing its public EC/EV tasks, and guidance. "
    "Guidance contains by_task, jurisdiction and an empty operators array. Each declared "
    "task has exactly one explicit when/procedure/avoid_when block. Identical task "
    "guidance may share one block; different task guidance costs its full stored tokens. "
    "Jurisdiction is one supplied legal namespace, or ALL only for genuinely shared "
    "procedure. Only the public task and already-given allowable jurisdictions select "
    "guidance; they do not supply asset eligibility answers. "
    "Publish minimal CREATE, UPDATE, DELETE or MERGE deltas against original parent IDs. "
    "Unmentioned skills stay verbatim. UPDATE retains its one target ID; DELETE has one "
    "target and null skill; MERGE consumes at least two IDs; CREATE has no target. "
    "Do not force library growth. Delete misleading guidance, merge true duplication, "
    "or explicitly NOOP if no grounded repair is available. Audit source_case_ids and "
    "rationales must reference supplied seen sources and never reach the actor. "
    "The body declares the fixed TRAIN commit policy. Under legal_scope, public "
    "co-visible namespaces, shared guidance changes and moved IDs couple edits. "
    "A coordinate needs current-source evidence and native task F1 nonregression on "
    "current and prior sources. BOTH EC and EV also preserve full-output F1, avoid "
    "increases in claims on negative/unscored assets and format failures, and require "
    "strict current improvement in at least one of those real outcomes. Native EC "
    "can hide false citations on assets with no applicable law; never call those safe. "
    "Other declared policies assess entire tasks or the whole proposal instead. "
    "Under adaptive_legal, a globally admissible complete proposal and an admissible "
    "dependency-composed proposal are compared using their already observed seen-TRAIN "
    "replays. Prefer the larger minimum EC/EV native-F1 gain, then the larger mean "
    "gain; exact ties retain the complete proposal. A complete proposal need not pass "
    "every smaller context's gate. No extra answer generation or changed scorer is used. "
    "The final single composed library must still pass the full TRAIN gate. Replay "
    "uses ALL seen sources, not just the communication subset, and is training "
    "optimization, not validation or proof of generalization. No answer repair, "
    "extra inference model, per-case answer selection, or changed scorer is allowed. "
    "Respect the actual target-tokenizer cap and combination headroom in the body. "
    "Keep edits concise enough that accepted components and unchanged guidance fit "
    "together. Bounded emitted excerpts are unverified executor output, not verified "
    "causal explanations; check them against facts, law, target and actual feedback. "
    "Return only the exact delta JSON schema."
)

CANDIDATE_FEEDBACK_ADDITION = (
    " Candidate feedback may include a partially committed previous proposal. "
    "Its accepted flag describes the ORIGINAL decision, not acceptance of every edit. "
    "Distinguish its committed coordinates from uncommitted changes and actual failure "
    "witnesses. References point to this request's actual parent observations in "
    "already_seen_training, not invented pre-proposal runs or stale prior parents. "
    "Use failed replay evidence to revise unresolved "
    "changes, rather than repeat an unsupported edit. Each attempt targets the parent "
    "IDs supplied for THAT attempt; do not target IDs created within the same delta. "
    "A prior accepted subset remains in the current parent. All changes still require "
    "full seen-TRAIN replay and the unchanged admission gates. This is bounded TRAIN "
    "refinement, never an inference retry or future-case feedback."
)

TEACHER_EVIDENCE_CONTRACT = "native_claim_task_projection_updates_v5"
UTILITY_TEACHER_EVIDENCE_CONTRACT = "native_claim_complete_output_utility_v6"
LEGACY_ADMISSION = "strict_native_full_counts_v1"
UTILITY_ADMISSION = "complete_output_utility_prior1pp_v1"
UTILITY_SELECTION = "seen_source_min_full_output_gain_then_mean_v2"
BOUNDED_FAILURE_HISTORY = "latest_unsuccessful_per_task_v1"
TASK_PROJECTION_TEACHING = (
    " This call teaches only the public task declared by teaching_task. The other "
    "task is an independent actor, not a prerequisite already solved for this one. "
    "Change only the declared task's rendered guidance; the other task's complete "
    "projection must remain byte-identical, including skill IDs and jurisdiction. "
    "An existing EC-only skill may gain an EV block without changing its EC block, "
    "and a shared block may be split to preserve the unselected task verbatim. "
    "CREATE, UPDATE, DELETE and MERGE remain available within that boundary; do not "
    "force a skill count or one skill per jurisdiction. Separate independently "
    "triggered decisions when bundling them hides a reusable action. Use this task's "
    "actual answers and released targets to repair its own missing eligibility, "
    "co-applicable alternatives or amount computation. Resolve invariant conditions "
    "under the declared independent-alternative task before leaving a calculation "
    "conditional on an unavailable prerequisite. Do not rewrite the other task to "
    "make the library look symmetric. NOOP is valid; the other scheduled task will "
    "still be taught. This is one bounded coordinate update, not a quality retry."
)
CONSOLIDATION_TEACHING = (
    " Acquisition is complete. All optimization sources were already observed during "
    "the completed training stream; there is no new current cohort or validation set. "
    "The packet's current_source_case_ids name a bounded communication focus, not "
    "the full optimization population. consolidation_scope lists all seen sources "
    "whose original answers are replayed together under the unchanged native/full-output, "
    "negative-claim and format gate. Correct residual errors while preserving useful "
    "guidance across this population. No new source, TEST answer, inference stage, "
    "tolerance relaxation or extra same-task retry is available."
)
EXECUTION_EXAMPLE_MARKER = "\nExecution example:"
EXECUTION_AWARE_ADDITION = (
    " Diagnose the reusable instruction's operational adequacy, not just whether "
    "its legal sentences are true. SKILL_DEFECT includes missing or wrong knowledge, "
    "underspecified eligibility, unavailable prerequisites, circular triggers, "
    "overloaded rule units and an ineffective representation of otherwise true law. "
    "Repeated omissions across supplied sources, or the same failure after an "
    "existing reminder, require reconsidering the instruction itself; do not call "
    "them isolated EXECUTION_LAPSE merely because a legal sentence is correct. "
    "Use actual_actor_skill_messages and their context references to inspect exactly "
    "what this task sees. EC and EV do not share their skill blocks or model answers. "
    "EV must decide eligibility as well as amounts from its own supplied inputs; "
    "do not assume its EC classification has already been solved unless it literally "
    "appears in the supplied public solved steps. Every task block must be usable "
    "with those inputs alone. A circular instruction such as 'for an eligible law' "
    "does not teach the missing eligibility condition. "
    "For SKILL_DEFECT, rewrite or reorganize the relevant when/procedure/avoid_when "
    "text and use the normal CREATE/UPDATE/DELETE/MERGE edits as needed. Separate "
    "independent decisions when one overloaded block hides them, without a fixed "
    "number of skills. Preserve supported legal conditions, exclusions and numeric "
    "semantics, but do not freeze an inadequate wording just because it contains "
    "a true rule. Do not import another method's library or add case-specific answers. "
    "Reserve EXECUTION_LAPSE for an isolated slip supported by the actual comparable "
    "success/failure observations; a quoted sentence alone does not establish that "
    "the instruction is complete. Quote its current rule anchor. Return delta and diagnoses. "
    "Each changed (skill_id, task) projection needs exactly one diagnosis, including "
    "created and deleted projections. Its source_case_ids are already supplied TRAIN "
    "sources. SKILL_DEFECT may use the normal differential edits; an empty anchor "
    "means a genuinely missing rule, not permission to invent evidence. "
    "For EXECUTION_LAPSE, keep the skill ID, task, jurisdiction, operators, when and "
    "avoid_when unchanged. Preserve the entire knowledge procedure before the exact "
    "delimiter '\\nExecution example:'. Append or replace only its compact teaching "
    "example after that delimiter. Keep at most one example section per block; "
    "update or deduplicate it rather than accumulating reminders. The exact anchor "
    "must occur in that block's existing knowledge, not an invented paraphrase. "
    "Use concrete final-output behavior, not a synonym of the existing rule: show "
    "coexisting independently applicable citations in an asset's JSON, or binding "
    "the protected amount to the asset's value instead of blindly copying a cap. "
    "Only teach conditions supported by the supplied law and actual TRAIN evidence. "
    "Public native final submissions show the actor's actual output representation; "
    "they are not automatically successful examples. Deidentify instances and do "
    "not save whole training answers. Mark any hypothetical numerical illustration "
    "as hypothetical, never as a new verified successful experience. Future assets "
    "still require their own eligibility and numeric decisions. No output repair, "
    "extra inference call, routing layer, program, or fallback is introduced. "
    "All text and examples share the original complete-library token cap. Empty "
    "delta and diagnoses are valid when no reusable change is warranted. "
)


def teaching_system_contract(system, contract):
    """Project the declared v6 contract into text; never change actor inputs."""
    if contract not in (LEGACY_ADMISSION, UTILITY_ADMISSION):
        raise ValueError("Unknown frozen admission contract")
    old_anchor = ("SKILL_DEFECT may use the normal differential edits; an empty anchor "
                  "means a genuinely missing rule, not permission to invent evidence.")
    new_anchor = (
        "SKILL_DEFECT may use the normal differential edits. For every newly created "
        "(skill_id, task) projection, including a split or a MERGE into a new ID, use "
        "an empty rule_anchor: the new ID has no old projection to quote. For an existing "
        "projection, a nonempty anchor must quote that same ID/task's actual parent text. "
        "An empty anchor for an existing projection denotes a genuinely missing rule, "
        "not permission to invent evidence.")
    if old_anchor not in system or CANDIDATE_FEEDBACK_ADDITION not in system:
        raise ValueError("The v6 teacher system lost a declared contract section")
    system = system.replace(old_anchor, new_anchor).replace(CANDIDATE_FEEDBACK_ADDITION, (
        " Candidate feedback retains at most the latest unsuccessful or partially "
        "committed historical proposal per teaching task, each with at most eight real "
        "TRAIN witnesses. Its accepted flag and origin describe the original decision. "
        "Historical candidate outputs were generated under their recorded proposed bank; "
        "they are NOT a new replay from the current parent. Current-parent reference "
        "answers are separately supplied in already_seen_training. Compare these actual "
        "observations without inventing an old parent or a fresh rerun. A NOOP or an "
        "unrelated successful edit does not erase the last failure. Target only IDs in "
        "this attempt's actual parent, never IDs created earlier in the same delta. "
        "Keep committed changes and correct remaining defects using the declared full "
        "TRAIN admission contract. This is bounded training feedback, not an inference "
        "retry or access to future cases."))
    if contract == UTILITY_ADMISSION:
        old_gate = (
            "A coordinate needs current-source evidence and native task F1 nonregression on "
            "current and prior sources. BOTH EC and EV also preserve full-output F1, avoid "
            "increases in claims on negative/unscored assets and format failures, and require "
            "strict current improvement in at least one of those real outcomes.")
        new_gate = (
            "A coordinate needs current-source evidence. Preserve BOTH native and complete-output "
            "mean F1 on the current cohort and on ALL already-seen sources, separately per task. "
            "On the prior cohort each mean may decrease by at most 0.01, one percentage point, "
            "relative to its actual parent. Require strict current improvement. Invalid answers "
            "still score zero and complete-output F1 still penalizes every false claim, including "
            "negative or unmatched assets. Report all format and false-claim counts, but their "
            "individual counts are diagnostics, not additional absolute zero-increase vetoes. "
            "The all-seen constraint must also hold for the final actual composed library.")
        old_rank = "Prefer the larger minimum EC/EV native-F1 gain, then the larger mean gain;"
        if old_gate not in system or old_rank not in system:
            raise ValueError("The utility teacher lost its original gate or ranking section")
        system = system.replace(old_gate, new_gate).replace(
            old_rank, "Prefer the larger minimum EC/EV complete-output-F1 gain, then the larger mean gain;")
    return system


def diagnosed_edit_schema(delta_schema, source_ids):
    """Audit metadata stays outside the skill bank and actor prompt."""
    diagnosis = {"type": "object", "additionalProperties": False,
        "properties": {"skill_id": {"type": "string"},
            "task": {"type": "string", "enum": list(FAMILIES)},
            "kind": {"type": "string", "enum": ["SKILL_DEFECT", "EXECUTION_LAPSE"]},
            "rule_anchor": {"type": "string"},
            "source_case_ids": {"type": "array", "minItems": 1,
                "items": {"type": "integer", "enum": sorted(source_ids)}}},
        "required": ["skill_id", "task", "kind", "rule_anchor", "source_case_ids"]}
    return {"type": "object", "additionalProperties": False,
        "properties": {"delta": delta_schema, "diagnoses": {"type": "array", "items": diagnosis}},
        "required": ["delta", "diagnoses"]}


def validate_edit_diagnoses(parent, candidate, diagnoses, source_ids):
    """Protect correct text, not scores; the original replay gates remain separate."""
    before = {(s["id"], f): s for f in FAMILIES for s in task_view(parent, f)}
    after = {(s["id"], f): s for f in FAMILIES for s in task_view(candidate, f)}
    changed = {key for key in before.keys() | after.keys() if before.get(key) != after.get(key)}
    indexed = {(d["skill_id"], d["task"]): d for d in diagnoses}
    if len(indexed) != len(diagnoses) or set(indexed) != changed:
        raise ValueError("Diagnose exactly the actual changed skill/task projections")
    for key, diagnosis in indexed.items():
        sources = diagnosis["source_case_ids"]
        if not sources or not set(sources) <= set(source_ids):
            raise ValueError("Edit diagnosis requires supplied TRAIN sources")
        old, new = before.get(key), after.get(key)
        anchor = diagnosis["rule_anchor"]
        if diagnosis["kind"] == "EXECUTION_LAPSE":
            if old is None or new is None:
                raise ValueError("Execution teaching cannot create or delete legal knowledge")
            a, b = old["guidance"], new["guidance"]
            if any(a[k] != b[k] for k in ("when", "avoid_when", "jurisdiction", "operators")):
                raise ValueError("Execution lapse changed a protected legal field")
            knowledge = a["procedure"].partition(EXECUTION_EXAMPLE_MARKER)[0]
            if (not b["procedure"].startswith(knowledge + EXECUTION_EXAMPLE_MARKER)
                    or b["procedure"].count(EXECUTION_EXAMPLE_MARKER) != 1):
                raise ValueError("Execution teaching must preserve the exact knowledge prefix")
            if len(anchor) < 20 or not any(anchor in text for text in
                    (knowledge, a["when"], a["avoid_when"])):
                raise ValueError("Execution teaching lacks its exact existing rule anchor")
        elif diagnosis["kind"] == "SKILL_DEFECT":
            if anchor and (old is None or not any(anchor in old["guidance"][k]
                    for k in ("when", "procedure", "avoid_when"))):
                raise ValueError("Knowledge-edit anchor is not in the actual parent")
        else:
            raise ValueError("Unknown edit diagnosis")
    return {"changed_task_blocks": [list(key) for key in sorted(changed)],
            "kinds": {kind: sum(d["kind"] == kind for d in diagnoses)
                      for kind in ("SKILL_DEFECT", "EXECUTION_LAPSE")},
            "diagnoses": copy.deepcopy(diagnoses)}


def validate_task_projection_edit(parent, candidate, task):
    """A teaching step cannot silently perturb an independent actor's memory."""
    if task not in FAMILIES:
        raise ValueError("Declare one original public task for coordinate teaching")
    for other in FAMILIES:
        if other != task and task_view(parent, other) != task_view(candidate, other):
            raise ValueError("Task-coordinate teaching changed an unselected actor projection")
    return {"teaching_task": task, "other_task_projection_unchanged": True}


def direct_case_input(row, *, asset_references=False):
    if row["family"] == "EC" and not asset_references:
        return active_case_input(row)
    content = "\n\n".join(row["components"][key] for key in ACTIVE_CASE_FIELDS
                          if row["components"][key])
    if asset_references:
        values = ("public citation label IDs" if row["family"] == "EC" else
                  "citation_ref and numeric claim_value objects")
        return content + ("\n\nOutput contract: Return a JSON object with exactly all supplied "
            "case-local asset_ref keys; each value is an array of " + values +
            ", or [] when none apply. The references identify mentions, not ownership or eligibility.")
    return content + ("\n\nOutput contract: Return only a JSON object mapping actual asset "
        "descriptions to arrays of citation_ref and numeric claim_value objects, or [] if none.")


AUTHOR_SYSTEM = (
    "Improve a frozen Qwen3-8B's reusable legal task skills from ACTUAL already-seen "
    "OpenExempt TRAIN cases. All labels are training-only original benchmark feedback, "
    "not secret test answers. The next batch is unavailable. Distinguish (1) asset-to-law "
    "classification from (2) claim valuation given applicable law. A procedure that "
    "sounds legally correct is not enough: this very weak executor must actually "
    "apply it. Diagnose observable mistakes using the original public statutes, "
    "facts, true target, actual answers and replay feedback. Use the supplied same-case "
    "empty-library answer as a real counterfactual, especially when it succeeds and "
    "the parent fails. Remove harmful guidance instead of adding formatting rituals. "
    "Do not invent successful trajectories. Give simple ordered "
    "operations and legal conditions the executor can perform. "
    "The source_model_emitted_evidence fields are bounded excerpts the executor "
    "already emitted, not verified explanations or a request for your hidden reasoning. "
    "Use them to locate a false premise or malformed submission, but verify every "
    "repair against the public sources, training target and actual execution receipts. "
    "A length-ended repeated output does not prove that the input was truncated. "
    "Explain a generic "
    "calculation using variables where useful, never a current-case answer. Do not "
    "request private chain of thought or invent a successful trajectory. "
    "Rules here concern the supplied benchmark statute version, not current legal advice. "
    "Each skill declares public family scope EC and/or EV. Its guidance.by_task "
    "contains exactly one when/procedure/avoid_when block for each declared task: "
    "use one block with tasks [EC,EV] for identical text, or separate EC and EV blocks "
    "when their instructions differ. There is no implicit or default guidance. "
    "Only the requested public task's block reaches the executor. Numerical operators "
    "belong to EV; an EC-only record must have an empty operators array. "
    "Each also declares jurisdiction: ALL for genuinely shared procedure with no law-bound "
    "operators, or one public statutory namespace. The host loads only ALL and the "
    "jurisdictions explicitly provided by the public AE solved step. Do not guess from "
    "domicile, broaden a state-specific rule to ALL, or use scope to memorize a case. "
    "Every stored operator must belong to its declared public legal namespace. "
    "No forced skill types, count, growth or one-skill-per-case design. Preserve useful "
    "boundaries, delete misleading guidance and merge genuine duplication. No case "
    "answer tables, particular debtors, exact asset descriptions/values or returned "
    "target sets in skills. Public legal citation numbers and statutory amounts may "
    "be used only when supported by supplied statute text; hypothetical symbols are "
    "preferable to copying a solved case. Hypothesis_ids are merely these public "
    "task family keys, not an NDA hypothesis. Unmentioned parent records remain "
    "verbatim. CREATE has no target; UPDATE preserves its one target ID; DELETE "
    "has one target and null skill; MERGE consumes at least two parent IDs. Targets "
    "must be original parent IDs, not earlier outputs. All audit source_case_ids "
    "must refer to already-seen cases. They and rationales are never delivered to "
    "the executor. Return an explicit NOOP when no grounded repair is available. "
    "The evidence manifest distinguishes all current sources from a bounded set of "
    "historical public-context, regression and failure witnesses. Omitted older "
    "sources are still replayed for TRAIN acceptance; they are not a validation set. "
    "Cite only source IDs actually supplied in this request, not an omitted case. "
    "The full skill library must fit4096 actual target model tokens; aim2500. "
    "The budget receipt reports the parent's actual target-tokenizer size and net "
    "growth headroom, not your own tokenizer's estimate. Respect that headroom when "
    "revising a record; remove redundant wording without changing unrelated correct "
    "boundaries rather than assuming that a one-record edit automatically fits. "
    "Candidate edits are replayed with the SAME frozen executor. The supplied "
    "skill_commit_policy is fixed before the run. Under task_local, EC and EV changes "
    "are admitted independently: a task must strictly improve its current original F1 "
    "(or, for EV, full-output F1), without regressing that task on current or earlier "
    "sources; EV must also preserve full-output F1 on both. Unaccepted task guidance "
    "and programs remain exactly the parent's. The combined committed bank must fit "
    "the same total4096-token cap, counting every distinct block and all programs. "
    "Under legal_scope, admission is further separated by public legal co-visibility "
    "within each task. Jurisdictions occurring together in already-seen public AE "
    "contexts are connected; moved skill IDs join their old and new scopes. A changed "
    "ALL block joins every scope for that task. Each resulting component must strictly "
    "improve its current TRAIN sources and retain its prior sources, with the same "
    "EV full-output protection. Components with no current sources cannot change. "
    "Only accepted components are composed into ONE library. This never routes by "
    "case IDs, asset types or correct answers, and does not change the inference "
    "interface. Full token cost, exact already-observed native-wire coverage and the "
    "original whole-bank TRAIN gate remain mandatory. Unaccepted scopes stay native "
    "wire-identical to their parent, including their numerical programs. "
    "Under whole_bank, the full proposal is accepted or rejected together, without "
    "selecting task edits. Both policies require the actual committed bank to pass "
    "the unchanged full TRAIN acceptance: current-source original mean F1 OR "
    "full-output EV F1 improvement without "
    "regressing either original family F1 or full-output EV F1 on current/earlier sources. "
    "The unchanged official EV macro score ignores some extra predicted assets; "
    "the separately named full-output EV score counts ALL predicted claims, using the "
    "same original asset matcher, claim matcher and5% amount tolerance. Remove false "
    "extra claims even when the original score overlooks them. This is training optimization, not evidence of "
    "new-case generalization. A rejected candidate can be revised once using the "
    "actual failure records; all rejected edits/costs remain. Do not propose a "
    "different output/scorer, fallback, paid service, extra inference judge, or "
    "a benchmark solver. No tools or outside information. Return exact delta JSON."
)

PROGRAM_ACTOR_SYSTEM = (
    "Apply only the original facts, supplied statutes and public solved steps. Decide legal "
    "eligibility yourself; no outside law. Submit an EV claim plan rather than final dollar "
    "answers. This replaces only FINAL ANSWER formatting. Submit only the assets JSON "
    "without explanation or skill-use self-report. "
    "Root has exactly assets (array). Each asset item has asset_name (string), "
    "asset_value (number), and claims (array). Each claim item has citation_ref "
    "(public label string) and limit_expression (JSON null or JSON string). "
    "For each asset supply its original "
    "asset_name and numeric asset_value from Facts. Do not copy a format example, a law ceiling, "
    "or another asset's value. No long quotation is required. Select EVERY applicable "
    "public citation label, not just one. Each displayed label encodes one exact public "
    "statutory citation in the given allowable legal framework. For each "
    "claim select citation_ref FIRST, based on legal applicability, and supply "
    "limit_expression. Supplied citation-only operators lists name the available "
    "numerical routines, not legal eligibility. For a listed citation, the schema "
    "requires JSON null to call its program. Its body is executed, not supplied "
    "for you to copy or rewrite. For an unlisted citation, write the ceiling "
    "expression yourself; null is invalid. The schema distinguishes these two "
    "action forms. Availability "
    "of a numerical program never proves that its citation is legally applicable. "
    "Do not choose or output an internal operator ID. "
    "All inline expressions are quoted JSON strings of 1 to 512 characters containing scalar arithmetic, "
    "including a constant-only ceiling. Never put a citation or prose in an expression. "
    "Expressions may use ordinary dollar numbers in current Facts/statutes, V (this asset's "
    "submitted value), N (1 or2 debtors from Facts), constants0/1/2, +,-,*,/, min/max, and "
    "X if N==2 else Y. For example min(V,C), where C is replaced by the supported numeric "
    "ceiling. Amounts may be written as words in law: translate them to ordinary numeric "
    "literals. The interpreter checks arithmetic syntax, not the legal truth of your numbers. "
    "The string unlimited means the selected law has no dollar ceiling; never use it for "
    "a capped exemption. The executor calculates min(submitted asset value, ceiling), or the "
    "asset value for unlimited, independently per pair. It decodes only the label you chose; "
    "it never chooses eligibility, adds claims or repairs an answer. "
    "Learned operations use identical arithmetic to inline expressions. Their presence does "
    "not prove applicability. If no learned operation covers an eligible law, write its "
    "expression inline. The runtime checks syntax/numbers, not truth, source spelling "
    "or legal applicability. Names and values are never rewritten. A public label is "
    "decoded by its declared table, never normalized, guessed or repaired after a failure. "
    "Return only the exact JSON plan."
)

PROGRAM_AUTHOR_ADDITION = (
    " The EV execution contract is now SOURCE-GROUNDED CLAIM OPERATIONS, not free final-number "
    "generation. Each guidance also has operators, an array which may be empty. An operator "
    "has id,citation,limit_expression. Internal IDs are ASCII provenance only. Keep ONE "
    "active routine per citation in the whole bank, combining supported N-dependent "
    "variants. If its ceiling cannot be expressed with the available public inputs, "
    "leave that citation without a routine rather than publish a wrong universal body. "
    "A native null limit_expression "
    "invokes that same citation's routine; an expression string is inline. There is no "
    "separate operator-ID selection task. Under contract v11 a published citation "
    "requires a null call rather than a rewritten inline formula. The program body "
    "is not rendered to the executor; its legal procedure and public statutes remain "
    "visible. Changing only a program body leaves the native selection request "
    "unchanged, but its plan is re-executed using the new program and bank version. "
    "Neither computed answers nor verifier feedback are reused as predictions. "
    "A new/removed routine or changed procedure can change the native request. "
    "Write reusable statutory CEILING expressions, never "
    "asset values, case names, targets or answers. The full actual system and schema are "
    "supplied. Use original citation strings, ordinary numeric statutory dollar constants, V for the "
    "current asset's value, N for the public debtor count, and generic constants0/1/2. "
    "Do not copy amounts from current Facts into reusable operators: use V instead. "
    "This is a learning requirement, not a runtime numeric-source validator; statutory "
    "amounts written in English words are equally legitimate. For example "
    "min(V,C) uses the actual numeric statutory C, not a literal variable C. Use N, arithmetic "
    "and a N==1/2 conditional only where "
    "that law supports the spouse rule. unlimited is an explicit no-ceiling decision, not "
    "an unresolved-law substitute. Scope operators to EV. "
    "Keep useful procedural guidance for classification, but do not spend revisions merely "
    "restating min(V,C): the shared interpreter already executes it. Learn the legal cap, "
    "cross-reference, category and exception operations the actual errors warrant. The "
    "same weak model still selects the laws and original fact amounts; source validation "
    "does not judge their legal truth. Invalid native programs and execution receipts are "
    "actual experience. Never invent that a stored operator was called or worked. "
    "The empty-library model can write the identical inline program: executable privilege "
    "is not unique to the skill method. Native citation_ref values use the same public "
    "ASCII label table for ALL arms; feedback shows their exact decoded citations. "
    "All program bodies and jurisdiction metadata count toward the4096-token bank."
)


def visible(bank, family):
    return task_view(bank, family)


def actor_payload(row, bank, *, grounded=True, direct_numeric=False, asset_references=False,
                  public_namespace_filter=True):
    if not grounded:
        raise ValueError("Only the public-namespace claim contract is implemented")
    if direct_numeric and any(s["guidance"]["operators"] for s in bank):
        raise ValueError("Direct-answer skills cannot publish numerical programs")
    if asset_references and not direct_numeric:
        raise ValueError("Public asset references require the common direct-answer contract")
    if type(public_namespace_filter) is not bool:
        raise ValueError("Declare the public-namespace projection explicitly")
    # The false branch is a content-preserving mechanism control. The ordinary
    # actor still uses the original public AE filter; neither branch reads gold.
    scoped = active_bank(row, bank) if public_namespace_filter else copy.deepcopy(bank)
    supplied = visible(scoped, row["family"])
    # A caller needs the available interfaces, not their private program bodies.
    # Pure body changes still leave every rendered message and schema unchanged.
    catalog = public_catalog(row)
    references = {citation: ref for ref, citation in catalog.items()}
    delivered = copy.deepcopy(supplied)
    for skill in delivered:
        if row["family"] == "EV" and not direct_numeric:
            skill["guidance"]["operators"] = [
                {"citation_ref": references[op["citation"]]}
                for op in skill["guidance"].get("operators", [])]
        else:
            skill["guidance"].pop("operators", None)
    system = ((DIRECT_NUMERIC_SYSTEM if direct_numeric else PROGRAM_ACTOR_SYSTEM)
              if row["family"] == "EV" else ACTOR_SYSTEM)
    asset_catalog = public_asset_catalog(row) if asset_references else None
    if asset_references:
        system += (" The original description-keyed task specifies the decoded answer. "
            "This profile encodes submitted root keys as the supplied case-local asset_ref "
            "IDs, not description strings or citations. Include every listed ID, using [] "
            "when no exemption is applicable. A reference only identifies a literal mention; "
            "it does not prove debtor ownership, eligibility, value or an exemption amount.")
    messages = [{"role": "system", "content": system}]
    if delivered:
        skill_message = {"role": "user", "content":
            "Background reusable skills. " +
            ("The current legal case follows. " if row["family"] == "EC" else "") +
            "Use these only when applicable; they are not current answers:\n" +
            json.dumps(delivered, ensure_ascii=False, separators=(",", ":"))}
        if row["family"] == "EC":
            messages.append(skill_message)
    messages.append({"role": "user", "content":
        (("Public case-local literal asset-mention references (IDs reset in every case; "
          "closed public lexicon; all legal judgments remain yours):\n" + json.dumps(asset_catalog, ensure_ascii=False,
          separators=(",", ":")) + "\n\n") if asset_references else "") +
        "Public citation label vocabulary. These are public headers in the already-given "
        "allowable jurisdictions, NOT an asset-eligibility answer:\n" +
        json.dumps(catalog, ensure_ascii=False, separators=(",", ":")) +
        "\n\n" + (direct_case_input(row, asset_references=asset_references)
                    if direct_numeric else active_case_input(row))})
    if delivered and row["family"] == "EV":
        messages.append(skill_message)
    labels = {"type": "string", "enum": list(catalog)}
    if row["family"] == "EV" and direct_numeric:
        schema = answer_schema("EV")
        claim = schema["additionalProperties"]["items"]
        claim["required"] = ["citation_ref", "claim_value"]
        claim["properties"] = {"citation_ref": labels, "claim_value": {"type": "number"}}
    elif row["family"] == "EV":
        schema = claim_answer_schema(supplied)
        operators = operator_catalog(supplied)
        if set(operators) - set(catalog.values()):
            raise InvalidClaimProgram("Routine outside the public allowable-law vocabulary")
        branches = []
        # XGrammar 0.1.23 ignores length keywords when pattern is present, so
        # include the existing 512-character bound in the lexical pattern.
        # This is a character alphabet, not a complete identifier/AST grammar;
        # execute_limit still rejects unsupported names, syntax and numbers.
        for cached, expression_schema in (
                (True, {"type": "null"}),
                (False, {"type": "string", "pattern":
                    r"^(unlimited|[0-9ENVaefilmnsx \t\r\n()+*/,.=-]{1,512})$"})):
            references = [ref for ref, citation in catalog.items()
                          if (citation in operators) == cached]
            if references:
                branches.append({"type": "object", "additionalProperties": False,
                    "required": ["citation_ref", "limit_expression"], "properties": {
                        "citation_ref": {"type": "string", "enum": references},
                        "limit_expression": expression_schema}})
        claims = schema["properties"]["assets"]["items"]["properties"]["claims"]
        claims["items"] = branches[0] if len(branches) == 1 else {"anyOf": branches}
    else:
        schema = answer_schema("EC")
        schema["additionalProperties"]["items"] = labels
    if asset_references:
        entry = schema["additionalProperties"]
        schema = {"type": "object", "additionalProperties": False,
                  "required": list(asset_catalog),
                  "properties": {ref: copy.deepcopy(entry) for ref in asset_catalog}}
    return messages, schema, supplied


def acceptance(parent_current, candidate_current, parent_prior, candidate_prior, *,
               contract=LEGACY_ADMISSION):
    if contract not in (LEGACY_ADMISSION, UTILITY_ADMISSION):
        raise ValueError("Unknown frozen admission contract")
    if contract == UTILITY_ADMISSION:
        for before, after in ((parent_current, candidate_current), (parent_prior, candidate_prior)):
            paired_effect(before, after)
            if any(len({(r["case_id"], r["family"]) for r in rows}) != len(rows)
                   for rows in (before, after)):
                raise ValueError("Utility admission requires distinct paired TRAIN tasks")
        if ({(r["case_id"], r["family"]) for r in parent_current}
                & {(r["case_id"], r["family"]) for r in parent_prior}):
            raise ValueError("Current and prior TRAIN tasks must be disjoint")
    a, b = metrics(parent_current), metrics(candidate_current)
    pa, pb = metrics(parent_prior), metrics(candidate_prior)
    current_ok = all(b[f]["f1"] + 1e-12 >= a[f]["f1"] for f in FAMILIES)
    prior_ok = not parent_prior or all(pb[f]["f1"] + 1e-12 >= pa[f]["f1"] for f in FAMILIES)
    current_full_ok = all(b[f]["full_output_f1"] + 1e-12 >= a[f]["full_output_f1"] for f in FAMILIES)
    prior_full_ok = not parent_prior or all(
        pb[f]["full_output_f1"] + 1e-12 >= pa[f]["full_output_f1"] for f in FAMILIES)
    audit_fields = ("negative_or_unscored_asset_claims", "invalid_format")
    current_audit_ok = all(b[f][k] <= a[f][k] for f in FAMILIES for k in audit_fields)
    prior_audit_ok = not parent_prior or all(
        pb[f][k] <= pa[f][k] for f in FAMILIES for k in audit_fields)
    heads = {f: _head_admission(f, a, b, pa, pb, contract=contract) for f in FAMILIES}
    improvement = any(h["strict_current_improvement"] for h in heads.values())
    result = {"accepted": (current_ok and prior_ok and current_full_ok and prior_full_ok
                         and current_audit_ok and prior_audit_ok and improvement),
            "current_family_nonregression": current_ok,
            "prior_family_nonregression": prior_ok, "strict_current_improvement": improvement,
            "current_full_output_nonregression": current_full_ok,
            "prior_full_output_nonregression": prior_full_ok,
            "current_negative_asset_and_format_nonregression": current_audit_ok,
            "prior_negative_asset_and_format_nonregression": prior_audit_ok,
            "parent_current": a, "candidate_current": b,
            "parent_prior": pa, "candidate_prior": pb,
            "TRAIN_optimization_not_independent_validation": True}
    if contract == UTILITY_ADMISSION:
        result.update({
            "accepted": all(h["quality_constraints_satisfied"] for h in heads.values()) and improvement,
            "admission_contract": contract, "prior_mean_loss_limit": .01,
            "prior_family_within_risk_bound": all(h["prior_native_within_risk_bound"] for h in heads.values()),
            "prior_full_output_within_risk_bound": all(h["prior_full_within_risk_bound"] for h in heads.values()),
            "all_seen_family_nonregression": all(h["all_seen_native_nonregression"] for h in heads.values()),
            "all_seen_full_output_nonregression": all(h["all_seen_full_nonregression"] for h in heads.values()),
            "count_changes_are_diagnostic_not_extra_vetoes": True})
    return result


def task_admission(parent_current, candidate_current, parent_prior, candidate_prior, *,
                   contract=LEGACY_ADMISSION):
    """Select TRAIN edit coordinates, never inference answers or case subsets."""
    a, b = metrics(parent_current), metrics(candidate_current)
    pa, pb = metrics(parent_prior), metrics(candidate_prior)
    return {family: _head_admission(family, a, b, pa, pb, contract=contract) for family in FAMILIES}


def _head_admission(family, a, b, pa, pb, *, contract=LEGACY_ADMISSION):
    if contract not in (LEGACY_ADMISSION, UTILITY_ADMISSION):
        raise ValueError("Unknown frozen admission contract")
    current_ok = b[family]["f1"] + 1e-12 >= a[family]["f1"]
    prior_ok = family not in pa or pb[family]["f1"] + 1e-12 >= pa[family]["f1"]
    strict = b[family]["f1"] > a[family]["f1"] + 1e-12
    full_current_ok = b[family]["full_output_f1"] + 1e-12 >= a[family]["full_output_f1"]
    full_prior_ok = (family not in pa or
                     pb[family]["full_output_f1"] + 1e-12 >= pa[family]["full_output_f1"])
    fields = ("negative_or_unscored_asset_claims", "invalid_format")
    current_audit_ok = all(b[family][k] <= a[family][k] for k in fields)
    prior_audit_ok = family not in pa or all(pb[family][k] <= pa[family][k] for k in fields)
    strict |= (b[family]["full_output_f1"] > a[family]["full_output_f1"] + 1e-12
               or any(b[family][k] < a[family][k] for k in fields))
    result = {"accepted": bool(current_ok and prior_ok and strict and full_current_ok and full_prior_ok
                             and current_audit_ok and prior_audit_ok),
            "current_nonregression": current_ok, "prior_nonregression": prior_ok,
            "strict_current_improvement": bool(strict),
            "current_full_output_nonregression": full_current_ok,
            "prior_full_output_nonregression": full_prior_ok,
            "current_negative_asset_and_format_nonregression": current_audit_ok,
            "prior_negative_asset_and_format_nonregression": prior_audit_ok}
    if contract == UTILITY_ADMISSION:
        nc, np = a[family]["tasks"], pa.get(family, {}).get("tasks", 0)
        if b[family]["tasks"] != nc or pb.get(family, {}).get("tasks", 0) != np:
            raise ValueError("Utility admission requires matched current/prior task counts")
        prior_native = not np or pb[family]["f1"] + .01 + 1e-12 >= pa[family]["f1"]
        prior_full = not np or pb[family]["full_output_f1"] + .01 + 1e-12 >= pa[family]["full_output_f1"]
        gains = {
            field: ((b[family][field] - a[family][field]) * nc
                    + ((pb[family][field] - pa[family][field]) * np if np else 0)) / (nc + np)
            for field in ("f1", "full_output_f1")}
        all_native, all_full = gains["f1"] >= -1e-12, gains["full_output_f1"] >= -1e-12
        quality = current_ok and full_current_ok and prior_native and prior_full and all_native and all_full
        result.update({
            "accepted": bool(quality and strict), "admission_contract": contract,
            "prior_mean_loss_limit": .01, "prior_native_within_risk_bound": prior_native,
            "prior_full_within_risk_bound": prior_full,
            "all_seen_native_nonregression": all_native, "all_seen_full_nonregression": all_full,
            "all_seen_native_gain": gains["f1"], "all_seen_full_output_gain": gains["full_output_f1"],
            "quality_constraints_satisfied": bool(quality),
            "count_changes_are_diagnostic_not_extra_vetoes": True})
    return result


def legal_scope_admission(coordinates, parent_current, candidate_current, parent_prior, candidate_prior, *,
                          contract=LEGACY_ADMISSION):
    decisions = {}
    for coordinate in coordinates:
        family, ids = coordinate["task"], set(coordinate["source_case_ids"])
        groups = [[r for r in rows if r["family"] == family and r["case_id"] in ids]
                  for rows in (parent_current, candidate_current, parent_prior, candidate_prior)]
        if any({(r["case_id"], r["family"]) for r in groups[i]}
               != {(r["case_id"], r["family"]) for r in groups[i + 1]} for i in (0, 2)):
            raise ValueError("Legal-scope TRAIN cohorts are not fully paired")
        if not groups[0]:
            decisions[coordinate["id"]] = {"accepted": False, "reason": "no_current_sources"}
            continue
        decisions[coordinate["id"]] = {
            **_head_admission(family, *(metrics(rows) for rows in groups), contract=contract),
            "current_tasks": len(groups[0]), "prior_tasks": len(groups[2])}
    return decisions


def paired_effect(before, after):
    a = {(r["case_id"], r["family"]): r for r in before}
    b = {(r["case_id"], r["family"]): r for r in after}
    if set(a) != set(b):
        raise ValueError("Unpaired original source/tasks")
    delta = [b[k]["score"]["f1"] - a[k]["score"]["f1"] for k in a]
    return {"tasks": len(delta), "help": sum(d > 1e-12 for d in delta),
            "hurt": sum(d < -1e-12 for d in delta),
            "ties": sum(abs(d) <= 1e-12 for d in delta),
            "mean_f1_difference": sum(delta) / len(delta) if delta else 0}


def balanced_replay_gain(before, after, *, contract=LEGACY_ADMISSION):
    """TRAIN selection over paired, already observed full replays, not a TEST metric."""
    for records in (before, after):
        if len({(r["case_id"], r["family"]) for r in records}) != len(records):
            raise ValueError("Adaptive selection requires distinct paired source/tasks")
    paired_effect(before, after)
    a, b = metrics(before), metrics(after)
    if not set(FAMILIES) <= set(a) or not set(FAMILIES) <= set(b):
        raise ValueError("Adaptive selection requires complete paired EC and EV replays")
    if contract not in (LEGACY_ADMISSION, UTILITY_ADMISSION):
        raise ValueError("Unknown frozen admission contract")
    field = "full_output_f1" if contract == UTILITY_ADMISSION else "f1"
    gains = [b[f][field] - a[f][field] for f in FAMILIES]
    return min(gains), sum(gains) / len(gains)


def native_claim_feedback(record, target):
    """TRAIN-only explanation of the existing matcher, never an actor or a scorer."""
    if record["parse_error"] is not None or record["score"]["invalid_format"]:
        return {"invalid_response": True, "errors": [{"kind": "invalid_response"}]}
    family = record["family"]
    evaluator = upstream("evaluator").Evaluator([])
    Claim = upstream("source.pydantic_response").Claim
    answer = {key.strip().lower(): value for key, value in record["parsed"]["answer"].items()}
    used, errors = set(), []
    correct = missing = wrong_targets = extra = wrong_predictions = 0
    for asset, truth in target.items():
        match = evaluator._find_matching_asset_description(asset.strip().lower(), list(answer))
        supplied = answer[match] if match is not None and match not in used else []
        if match is not None:
            used.add(match)
        if family == "EC":
            expected = {citation.strip().lower(): citation for citation in truth}
            predicted = {citation.strip().lower(): citation for citation in supplied}
            correct += len(expected.keys() & predicted.keys())
            for key in sorted(expected.keys() - predicted.keys()):
                missing += 1
                errors.append({"kind": "missing", "asset": asset, "citation": expected[key]})
            for key in sorted(predicted.keys() - expected.keys()):
                extra += 1
                errors.append({"kind": "extra", "asset": asset, "citation": predicted[key]})
            continue
        if family != "EV":
            raise ValueError("Native claim feedback is defined only for EC and EV")
        expected = {Claim(**value).normalized_citation: Claim(**value) for value in truth}
        remaining, found = dict(expected), {}
        for value in supplied:
            claim = Claim(**value)
            paired, relative_error = evaluator._find_matching_claim(claim, list(remaining.values()))
            right = paired is not None and relative_error < .05
            found.setdefault(claim.normalized_citation, []).append((claim.claim_value, right, paired is not None))
            if right:
                remaining.pop(paired.normalized_citation)
            elif paired is None:
                extra += 1
                errors.append({"kind": "extra_or_duplicate", "asset": asset,
                               "citation": claim.citation, "observed_value": claim.claim_value})
            else:
                wrong_predictions += 1
        for key, claim in expected.items():
            values = found.get(key, [])
            right = any(ok for _, ok, _ in values)
            if right:
                correct += 1
            elif values:
                wrong_targets += 1
            else:
                missing += 1
            wrong = [value for value, ok, matched in values if not ok and matched]
            if not right or wrong:
                errors.append({"kind": ("missing" if not values else
                                        "incorrect_value" if not right else "incorrect_extra_value"),
                               "asset": asset, "citation": claim.citation,
                               "expected_value": claim.claim_value, "observed_values": wrong})
    for asset, supplied in answer.items():
        if asset in used:
            continue
        values = ({citation.strip().lower(): citation for citation in supplied}.values()
                  if family == "EC" else supplied)
        for value in values:
            extra += 1
            errors.append({"kind": "extra_asset_claim", "asset": asset,
                           **({"citation": value} if family == "EC" else value)})
    score = record["score"]
    for field, actual in (("full_output_claim_tp", correct),
                          ("full_output_claim_fn", missing + wrong_targets),
                          ("full_output_claim_fp", extra + wrong_predictions)):
        if field in score and score[field] != actual:
            raise ValueError("TRAIN claim feedback disagrees with the original complete-output matcher")
    return {"invalid_response": False, "correct": correct, "missing": missing,
            "incorrect_value": wrong_targets, "extra_or_duplicate": extra,
            "incorrect_value_predictions": wrong_predictions, "errors": errors}


def candidate_feedback(decision, observations, origin, *, witness_limit=8):
    """Bound saved failure evidence; never relabel a partial commit as rejected."""
    if type(witness_limit) is not int or not 1 <= witness_limit <= 8:
        raise ValueError("Candidate feedback allows one to eight real TRAIN witnesses")
    if decision.get("explicit_noop"):
        return None
    accepted = bool(decision.get("accepted"))
    if accepted and (decision.get("proposal_fully_committed")
                     or decision.get("proposed_bank") == decision.get("candidate")):
        return None
    pool = decision.get("proposed_replay", decision.get("actual_replay", []))
    if decision.get("teaching_task") is not None:
        pool = [r for r in pool if r["family"] == decision["teaching_task"]]
    keys = [(r["case_id"], r["family"]) for r in pool]
    if len(keys) != len(set(keys)) or not set(keys) <= set(observations):
        raise ValueError("Candidate feedback must reference distinct already-seen TRAIN observations")

    def severity(record):
        key = record["case_id"], record["family"]
        before, after = observations[key]["score"], record["score"]
        delta = min(after["f1"] - before["f1"],
            after.get("full_output_f1", after["f1"])
            - before.get("full_output_f1", before["f1"]))
        return delta, min(after["f1"], after.get("full_output_f1", 1)), *key

    witnesses = sorted(pool, key=severity)[:witness_limit]
    fields = ("delta", "reason", "teaching_task", "source_program_compile_error", "composition_error",
              "diagnosis_error", "edit_diagnoses", "edit_audit",
              "accepted_tasks", "accepted_legal_coordinates", "legal_scope_admission",
              "task_admission", "proposed_whole_bank_acceptance", "attempt_parent_bank_sha256",
              "adaptive_commit_selection", "proposal_fully_committed")
    return {**{k: copy.deepcopy(decision[k]) for k in fields if k in decision},
        "accepted": accepted, "partially_committed": accepted,
        "candidate_feedback_origin": copy.deepcopy(origin),
        "proposed_bank_sha256": csha(decision.get("proposed_bank", decision.get("candidate"))),
        "decision_candidate_bank_sha256": csha(decision.get("candidate")),
        "full_proposed_replay_task_count": len(pool),
        "feedback_witness_limit": witness_limit,
        "feedback_witness_rule": "worst current-parent delta, then remaining failure, source/task tie break",
        "references_are_current_parent_observations_not_invented_original_runs": True,
        "feedback_witness_replay": copy.deepcopy(witnesses)}


def retained_candidate_feedback(out, current_batch, observations, parent_bank_sha256):
    """One historical failure per task, not a growing ledger or a fabricated replay."""
    retained = {}
    for batch in range(current_batch - 1, 0, -1):
        publication = read(out / "publications" / f"b{batch}.json")
        if batch == current_batch - 1 and publication["bank_sha256"] != parent_bank_sha256:
            raise ValueError("Previous publication must match the actual current parent")
        attempt_parent = publication["parent_bank_sha256"]
        attempts = []
        for index, decision in enumerate(publication["training_decisions"], 1):
            attempts.append((index, decision, attempt_parent))
            if decision.get("accepted"):
                attempt_parent = csha(decision["candidate"])
        if attempt_parent != publication["bank_sha256"]:
            raise ValueError("Historical feedback publication has inconsistent bank lineage")
        for index, decision, original_parent in reversed(attempts):
            task = decision.get("teaching_task")
            if task in retained:
                continue
            feedback = candidate_feedback(decision, observations, {
                "batch": batch, "attempt": index,
                "publication_bank_sha256": publication["bank_sha256"],
                "historical_attempt_parent_bank_sha256": original_parent,
                "current_reference_parent_bank_sha256": parent_bank_sha256,
                "historical_candidate_not_rerun": True})
            if feedback is not None:
                retained[task] = feedback
    return [retained[task] for task in sorted(retained, key=lambda value: value or "")]


def teacher_evidence_rows(current, seen, observations, rejected, *, history_limit=16,
                          families=FAMILIES):
    """Bound teacher communication, never the full TRAIN replay or its scores.

    Keep every current source and every source named by bounded candidate feedback.
    Fill the historical background budget with public-context witnesses, actual
    regressions and parent failures. The mandatory witness union can exceed that
    background budget; dropping a declared rejection witness is never permitted.
    """
    current_ids = {r["case_id"] for r in current}
    by_id = {r["case_id"]: r for r in seen}
    old_ids = set(by_id) - current_ids
    mandatory = {r["case_id"] for d in rejected
                 for r in d.get("feedback_witness_replay", [])}
    if not mandatory <= set(by_id):
        raise ValueError("Teacher feedback witnesses must be already-seen TRAIN sources")
    def quality(record):
        return min(record["score"]["f1"], record["score"].get("full_output_f1", 1.0))
    if not families or not set(families) <= set(FAMILIES):
        raise ValueError("Teacher source selection requires original public tasks")
    parent_quality = {i: min(quality(observations[(i, f)]) for f in families)
                      for i in old_ids}
    groups = {}
    for i in sorted(old_ids):
        groups.setdefault(tuple(sorted(allowable_namespaces(by_id[i]))), []).append(i)
    context_witnesses = [min(ids, key=lambda i: (parent_quality[i], i))
                         for _, ids in sorted(groups.items())]
    harm = {}
    for decision in rejected:
        for record in decision.get("feedback_witness_replay", decision.get("actual_replay", [])):
            i = record["case_id"]
            if i in old_ids:
                before = observations[(i, record["family"])]["score"]
                after = record["score"]
                delta = min(after["f1"] - before["f1"],
                    after.get("full_output_f1", after["f1"])
                    - before.get("full_output_f1", before["f1"]))
                harm[i] = min(harm.get(i, 0.0), delta)
    regressions = sorted((i for i in harm if harm[i] < -1e-12), key=lambda i: (harm[i], i))
    failures = sorted(old_ids, key=lambda i: (parent_quality[i], i))
    required_old = sorted(mandatory & old_ids)
    actual_limit = max(history_limit, len(required_old))
    selected_old = list(dict.fromkeys(
        required_old + context_witnesses + regressions + failures))[:actual_limit]
    selected = current_ids | set(selected_old)
    return [r for r in seen if r["case_id"] in selected], {
        "current_source_ids_all_included": sorted(current_ids),
        "selected_historical_source_ids": sorted(selected_old),
        "selected_source_ids": sorted(selected),
        "all_seen_source_ids": sorted(by_id),
        "omitted_historical_source_ids": sorted(old_ids - set(selected_old)),
        "historical_source_limit": actual_limit,
        "historical_background_source_limit": history_limit,
        "mandatory_feedback_witness_source_ids": sorted(mandatory),
        "all_bounded_feedback_witnesses_included": mandatory <= selected,
        "public_context_witnesses": [i for i in context_witnesses if i in selected],
        "rule": "all bounded feedback witness sources, then public-context witnesses, actual harm and parent failures; ties by source ID",
        "full_seen_TRAIN_replay_and_acceptance_unchanged": True,
        "not_an_independent_validation_set": True}


CONSOLIDATION_PHASE = "post_stream_seen_source_consolidation_v1"


def observed_consolidation_inputs(cfg):
    """Recover a completed TRAIN bank and its real observations, never predictions by score."""
    source = ROOT / "runs" / cfg["consolidation_parent_run"]
    original_path = ROOT / cfg["consolidation_parent_config"]
    original = read(original_path)
    for key in ("generation", "phase_dispatch", "input_packet", "grading_directory",
                "inference_environment", "execution_contract", "execution_contract_version"):
        if cfg[key] != original[key]:
            raise ValueError(f"Consolidation changed the parent execution contract: {key}")
    completed = read(source / "completion.json")
    if not completed["status"].startswith("completed"):
        raise ValueError("Consolidation requires a completed acquisition run")
    rows = read(ROOT / cfg["input_packet"])["rows"]
    latest, empty, extra = {}, [], {original_path, original_path.with_suffix(".frozen.json"),
        source / "completion.json", ROOT / original["protocol"]}
    for batch in range(1, original["planned_batches"] + 1):
        data_path = source / "batches" / f"b{batch}_prequential_records.json"
        pub_path = source / "publications" / f"b{batch}.json"
        data, publication = read(data_path), read(pub_path)
        latest.update({(r["case_id"], r["family"]): r for r in data["skills"]})
        empty.extend(data["empty"])
        for decision in publication["training_decisions"]:
            if decision.get("accepted"):
                latest = {(r["case_id"], r["family"]): r
                          for r in decision["actual_replay"]}
        extra.update((data_path, pub_path))
    parent = read(ROOT / cfg["initial_library_publication"])
    parent_hash = csha(parent["bank"])
    if (parent_hash != publication["bank_sha256"]
            or parent_hash != cfg["consolidation_parent_bank_sha256"]
            or csha(completed["bank"]) != parent_hash):
        raise ValueError("Consolidation must use the actual completed final bank")
    keys = {(r["case_id"], r["family"]) for r in rows}
    if (set(latest) != keys or len(empty) != len(rows)
            or any(r["bank_sha256"] != parent_hash for r in latest.values())):
        raise ValueError("Incomplete original TRAIN observations")
    before = [latest[r["case_id"], r["family"]] for r in rows]
    empties = {(r["case_id"], r["family"]): r for r in empty}
    origins = {}
    for row in rows:
        for record, bank in ((latest[row["case_id"], row["family"]], parent["bank"]),
                             (empties[row["case_id"], row["family"]], [])):
            path = ROOT / record["raw_call_path"]
            raw = read(path)
            if raw.get("transport_error") is not None or len(raw["calls"]) != 1:
                raise ValueError("Imported observations need one real successful transport")
            wire = raw["calls"][0]["request"]
            messages, schema, _ = actor_payload(row, bank, grounded=True,
                direct_numeric=True, asset_references=True)
            if (wire["messages"] != messages
                    or wire["response_format"]["json_schema"]["schema"] != schema
                    or any(wire[k] != cfg["generation"][k] for k in
                           ("model", "temperature", "top_p", "top_k", "max_tokens", "seed"))
                    or wire.get("chat_template_kwargs", {}).get("enable_thinking", True)
                       != (not cfg["generation"]["disable_thinking"])):
                raise ValueError("Historical response is not the same actual native request")
            target = read(ROOT / cfg["grading_directory"] / f"{row['case_id']}.json")["targets"][row["family"]]
            answer = record["parsed"]["answer"] if record["parse_error"] is None else None
            if evaluate(row, answer, target) != record["score"]:
                raise ValueError("Imported original TRAIN grade differs")
            key = csha({"messages": messages, "schema": schema, "generation": cfg["generation"]})
            origin = {"response": raw["response"], "raw_call_path": record["raw_call_path"]}
            if key in origins and origins[key] != origin:
                raise ValueError("Ambiguous historical response; no quality selection is allowed")
            origins[key] = origin
            extra.update((path, path.with_suffix(".input.json")))
    return rows, before, empty, origins, extra, completed


def freeze(config_path, *, additional_sources=()):
    cfg = read(config_path)
    files = set(ROOT.glob("legal_skill_guard/**/*.py"))
    files |= set(UPSTREAM.rglob("*.py")) | set(UPSTREAM.rglob("*.json"))
    files |= set(UPSTREAM.rglob("*.jsonl"))
    files |= set((ROOT / cfg["input_packet"]).parent.rglob("*.json"))
    files |= set((ROOT / cfg["grading_directory"]).glob("*.json"))
    files |= set(ROOT.glob("tests/test_*.py"))
    files.update({Path(__file__).resolve(), Path(config_path).resolve(), ROOT / "pyproject.toml",
                  ROOT / "uv.lock", ROOT / "README.md",
                  ROOT / cfg["protocol"],
                  ROOT / "tests/test_openexempt_contract.py",
                  ROOT / cfg["inference_environment"], ROOT / cfg["upstream_archive"]})
    if cfg.get("initial_library_publication"):
        files.add(ROOT / cfg["initial_library_publication"])
    files.update(ROOT / name for name in cfg.get("inference_dependency_artifacts", []))
    files.update(Path(path).resolve() for path in additional_sources)
    if cfg.get("training_phase") == CONSOLIDATION_PHASE:
        files.update(observed_consolidation_inputs(cfg)[4])
    bindings = {str(p.relative_to(ROOT)): sha(p) for p in sorted(files)}
    packages = {dist.metadata["Name"]: dist.version for dist in importlib.metadata.distributions()}
    manifest = {"config_sha256": sha(config_path), "files": bindings, "packages": packages,
                "prepared_at": now(), "no_this_run_performance_observed_before_freeze": True,
                "warm_sources_are_previously_observed_TRAIN": bool(cfg.get("warm_source_case_ids"))
                    or cfg.get("training_phase") == CONSOLIDATION_PHASE}
    frozen_path = Path(config_path).with_suffix(".frozen.json")
    RunStore.immutable_json(frozen_path, manifest)
    preserve(cfg["run_id"], "source", [*bindings, str(frozen_path.relative_to(ROOT)),
                                      "docs/research/RESEARCH_RESET_20261019.md"])
    return manifest


def preserve(run_id, stage, names):
    """Two independent disks, exact source/data/raw artifacts, no broad cleanup."""
    locations = (Path("/media/sangfor/vdb/legal-skill-backups"),
                 Path("/home/yndx/hhy/legal-skill-rootdisk-backups"))
    receipt = {"at": now(), "stage": stage, "paths": [], "files": len(set(names))}
    for base in locations:
        base.mkdir(parents=True, exist_ok=True)
        archive = base / f"{run_id}-{stage}.tar.gz"
        with tarfile.open(archive, "x:gz") as dest:
            for name in sorted(set(names)):
                dest.add(ROOT / name, arcname=name, recursive=False)
        with tarfile.open(archive) as source:
            if source.getnames() != sorted(set(names)):
                raise ValueError("Backup member mismatch")
            for member in source:
                payload = source.extractfile(member)
                if payload is None or hashlib.sha256(payload.read()).hexdigest() != sha(ROOT / member.name):
                    raise ValueError("Backup content differs from current bytes")
        receipt["paths"].append({"path": str(archive), "sha256": sha(archive)})
    return receipt


def direct_request_key(cfg, row, bank, stage, arm):
    """Identity for locking the unchanged direct actor, not another actor."""
    grounded = cfg.get('execution_contract') in (
        'source_grounded_claim_operations', 'direct_statutory_claims')
    direct = cfg.get('execution_contract') == 'direct_statutory_claims' or arm == 'empty_direct_numeric'
    messages, schema, _ = actor_payload(row, bank, grounded=grounded,
        direct_numeric=direct, asset_references=cfg.get('execution_contract_version') == 14)
    return csha({'messages': messages, 'schema': schema, 'generation': cfg['generation']})


class Online:
    # Audited transports only; no NDA initialization, scoring or old update logic.
    check = Comparison.check
    call = Comparison.call
    teacher_call = Comparison.teacher_call

    def __init__(self, config_path):
        self.cfg = read(config_path)
        evidence = self.cfg.get("teacher_evidence_contract")
        admission = self.cfg.get("admission_contract", LEGACY_ADMISSION)
        if evidence not in (TEACHER_EVIDENCE_CONTRACT, UTILITY_TEACHER_EVIDENCE_CONTRACT):
            raise ValueError("Declare the native-claim-aligned teacher evidence contract before learning")
        if (admission not in (LEGACY_ADMISSION, UTILITY_ADMISSION)
                or (evidence == TEACHER_EVIDENCE_CONTRACT and admission != LEGACY_ADMISSION)):
            raise ValueError("The admission and teacher contracts must agree")
        if evidence == UTILITY_TEACHER_EVIDENCE_CONTRACT and (
                "admission_contract" not in self.cfg
                or self.cfg.get("feedback_retention") != BOUNDED_FAILURE_HISTORY
                or self.cfg.get("execution_contract") != "direct_statutory_claims"
                or self.cfg.get("candidate_feedback_policy") != "carry_partial_and_refine"):
            raise ValueError("The v6 stream requires explicit admission and bounded historical feedback")
        if self.cfg.get("teacher_update_policy") not in (
                "joint_bounded_refinement", "task_projection_coordinate", "joint_fixed_steps"):
            raise ValueError("Declare the teacher update policy explicitly before learning")
        if self.cfg["teacher_update_policy"] == "task_projection_coordinate" and (
                self.cfg.get("task_update_schedule") != list(FAMILIES)
                or self.cfg.get("max_candidate_attempts") != len(FAMILIES)
                or self.cfg.get("candidate_feedback_policy") != "carry_partial_and_refine"):
            raise ValueError("Coordinate teaching requires one scheduled EC and EV update per batch")
        if self.cfg["teacher_update_policy"] == "joint_fixed_steps" and (
                self.cfg.get("training_phase") != CONSOLIDATION_PHASE
                or self.cfg.get("max_candidate_attempts") != 2
                or self.cfg.get("candidate_feedback_policy") != "carry_partial_and_refine"
                or self.cfg.get("task_update_schedule") is not None
                or self.cfg.get("batch_source_cases") != 16):
            raise ValueError("Matched joint consolidation requires two fixed steps and a32-task-record packet")
        if type(self.cfg.get("frozen_after_first_batch_control", False)) is not bool:
            raise ValueError("Declare frozen-after-first-batch evaluation as a boolean")
        if self.cfg.get("candidate_feedback_policy", "batch_only_first_commit") not in (
                "batch_only_first_commit", "carry_partial_and_refine"):
            raise ValueError("Declare the candidate feedback policy before freezing")
        if self.cfg.get("candidate_feedback_policy") == "carry_partial_and_refine" and (
                self.cfg.get("execution_contract") != "direct_statutory_claims"
                or type(self.cfg.get("max_candidate_attempts")) is not int
                or self.cfg["max_candidate_attempts"] not in (1, 2)):
            raise ValueError("Closed-loop feedback uses direct answers and one or two bounded proposals")
        contracts = {"source_grounded_claim_operations": (12,), "direct_statutory_claims": (13, 14)}
        if (self.cfg.get("execution_contract") not in contracts
                or self.cfg.get("execution_contract_version")
                not in contracts[self.cfg["execution_contract"]]):
            raise ValueError("Declare numerical v12, direct v13 or public-asset-reference direct v14")
        if self.cfg.get("skill_commit_policy") not in (
                "legal_scope", "task_local", "whole_bank", "adaptive_legal"):
            raise ValueError("Declare the TRAIN commit policy before freezing")
        expected_objective = (UTILITY_SELECTION if admission == UTILITY_ADMISSION
                              else "seen_source_min_family_gain_then_mean_v1")
        if self.cfg["skill_commit_policy"] == "adaptive_legal" and self.cfg.get(
                "adaptive_commit_objective") != expected_objective:
            raise ValueError("Freeze the adaptive seen-TRAIN selection objective explicitly")
        frozen = read(Path(config_path).with_suffix(".frozen.json"))
        if frozen["config_sha256"] != sha(config_path):
            raise ValueError("Frozen config mismatch")
        self.bindings = frozen["files"]
        self.run_id = self.cfg["run_id"]
        self.out = ROOT / "runs" / self.run_id
        if self.out.exists():
            raise FileExistsError("New Run ID required, never overwrite native outputs")
        self.rows = read(ROOT / self.cfg["input_packet"])["rows"]
        self.native, self.teachers, self.teacher_attempts = [], [], 0
        self.request_cache, self.reuse_events = {}, []
        self.current_batch, self.stop = 0, False
        self._dispatch = PhaseDispatch(self.cfg,
            environment=(read(ROOT / self.cfg['inference_environment'])
                         if self.cfg.get('phase_dispatch') is not None else None),
            on_failure=lambda: setattr(self, 'stop', True))
        self.answer = self._dispatch.locked_requests(self.answer,
            lambda *args, **kwargs: direct_request_key(self.cfg, *args, **kwargs))
        self.teacher_call = self._dispatch.limited_teacher(self.teacher_call)
        self.bank, self.latest, self.summaries = [], {}, []
        if self.cfg.get("initial_library_publication"):
            initial = read(ROOT / self.cfg["initial_library_publication"])["bank"]
            self.bank = copy.deepcopy(initial)
            validate_scoped_bank(self.bank)
            if (self.cfg["execution_contract"] == "direct_statutory_claims"
                    and any(s["guidance"]["operators"] for s in self.bank)):
                raise ValueError("Direct-answer initialization cannot contain numerical programs")
            validate_scopes(self.bank, self.rows[0]["components"]["statutes"])
            if self.bank != initial:
                raise ValueError("Initialization changed historical knowledge")
        self.frozen_bank = copy.deepcopy(self.bank)
        self.first_batch_frozen_bank = copy.deepcopy(self.bank)
        self.prequential_first_batch_frozen = []
        self.prequential_empty, self.prequential_skills, self.prequential_frozen = [], [], []
        self.prequential_direct = []
        self.meter = WireClient(self.cfg["generation"])
        self.out.mkdir(parents=True)
        RunStore.immutable_json(self.out / "initialization.json", {
            "execution_dispatch": self._dispatch.receipt(),
            "bank": self.bank, "parent_publication": self.cfg.get("initial_library_publication"),
            "initial_library_kind": self.cfg.get("initial_library_kind"),
            "initial_case_exposure": self.cfg.get("initial_library_prior_exposure_distinct_sources", 0),
            "all_episode_labels_unseen_before_this_run": self.cfg.get("all_episode_labels_unseen_before_this_run", False),
            "prior_stateless_queries_without_label_feedback": self.cfg.get("prior_stateless_queries_without_label_feedback", []),
            "input_contract": self.cfg.get("input_contract"),
            "frozen_after_first_batch_evaluation_only": self.cfg.get("frozen_after_first_batch_control", False),
            "frozen_after_B1_answers_never_teacher_or_admission_feedback": True})
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, lambda *_: setattr(self, "stop", True))
        self.check()
        if not self.meter.readiness()["ready"]:
            raise RuntimeError("Existing frozen 8B service unavailable")
        self.progress("initialized")

    def progress(self, stage, **extra):
        dispatch = getattr(self, '_dispatch', None)
        with dispatch.progress_lock if dispatch is not None else nullcontext():
            RunStore.atomic_json(self.out / "progress.json", {
                "at": now(), "run_id": self.run_id, "state": "running", "stage": stage,
                "current_batch": self.current_batch, "completed_native_calls": len(self.native),
                "completed_teacher_calls": len(self.teachers), "teacher_attempts": self.teacher_attempts,
                "cross_stage_identical_wire_reuses": len(self.reuse_events),
                "library_records": len(self.bank),
                **({'execution_dispatch': dispatch.receipt()} if dispatch is not None else {}), **extra})

    def answer(self, row, bank, stage, arm, *, public_namespace_filter=True):
        self.check()
        grounded = self.cfg.get("execution_contract") in (
            "source_grounded_claim_operations", "direct_statutory_claims")
        direct = (self.cfg.get("execution_contract") == "direct_statutory_claims"
                  or arm == "empty_direct_numeric")
        asset_references = self.cfg.get("execution_contract_version") == 14
        messages, schema, supplied = actor_payload(row, bank, grounded=grounded,
            direct_numeric=direct, asset_references=asset_references,
            public_namespace_filter=public_namespace_filter)
        asset_catalog = public_asset_catalog(row) if asset_references else None
        catalog = public_catalog(row)
        fingerprint = csha({"messages": messages, "schema": schema,
                            "generation": self.cfg["generation"]})
        path = self.out / "native" / stage / f"{row['case_id']}_{row['family']}_{arm}.json"
        RunStore.immutable_json(path.with_suffix(".input.json"), {
            "messages": messages, "schema": schema, "bank_sha256": csha(bank),
            "delivered_skill_ids": [s["id"] for s in supplied],
            "original_prompt_sha256": csha(row["prompt"]),
            "actual_active_case_input_sha256": csha(direct_case_input(row, asset_references=asset_references)
                if direct else active_case_input(row)),
            "public_citation_catalog": catalog,
            "public_allowable_jurisdictions": sorted(allowable_namespaces(row)),
            "public_citation_catalog_sha256": csha(catalog),
            **({"public_asset_reference_catalog": asset_catalog,
                "public_asset_reference_catalog_sha256": csha(asset_catalog),
                "public_asset_reference_policy": "maximal_literal_mentions_closed_description_lexicon"}
               if asset_references else {}),
            "numerical_program_bodies_rendered_to_actor": False,
            "published_citation_calls_required_by_schema": row["family"] == "EV" and not direct,
            "direct_numeric_empty_control": arm == "empty_direct_numeric",
            "valuation_output_contract": "direct_numeric" if direct else "claim_program",
            "format_only_demonstrations_not_in_inference_input": True,
            "no_private_case_annotations_or_current_target": True})
        alias = None
        raw_call_path = str(path.relative_to(ROOT))
        if fingerprint in self.request_cache:
            original = self.request_cache[fingerprint]
            response = copy.deepcopy(original["response"])
            raw_call_path = original["raw_call_path"]
            alias = {"fingerprint": fingerprint, "raw_call_path": raw_call_path,
                     "not_an_independent_generation": True,
                     "execution_receipt_is_from_original_call": False,
                     "reinterpreted_under_bank_sha256": csha(bank)}
            self.reuse_events.append({"stage": stage, "case_id": row["case_id"],
                "family": row["family"], "arm": arm, "fingerprint": fingerprint,
                "raw_call_path": raw_call_path,
                "execution_bank_sha256": csha(bank)})
        else:
            response = self.call(path, messages, schema, self.cfg["generation"]["max_tokens"], {
                "stage": stage, "arm": arm, "document_id": row["case_id"],
                "family": row["family"], "call_role": "openexempt", "bank_sha256": csha(bank)})
            # Cache only the raw native response. A bank update may change the
            # invoked body while messages/schema remain byte-identical.
            self.request_cache[fingerprint] = {
                "response": copy.deepcopy(response), "raw_call_path": raw_call_path}
        parsed = None
        parse_error = None
        try:
            parsed = json.loads(response["content"])
            validate(parsed, schema)
        except (json.JSONDecodeError, ValueError) as exc:
            parse_error = repr(exc)
        except Exception as exc:
            from jsonschema import ValidationError
            if not isinstance(exc, ValidationError):
                raise
            parse_error = repr(exc)
        if response["finish_reason"] != "stop":
            parse_error = "Incomplete native output: " + str(response["finish_reason"])
        public_label_submission = copy.deepcopy(parsed)
        if asset_references and parse_error is None:
            parsed = decode_asset_references(parsed, asset_catalog)
        native_program, execution_receipt, execution_error = None, None, None
        if grounded and row["family"] == "EV" and not direct and parse_error is None:
            native_program = decode_claim_plan(parsed, catalog)
            try:
                answer, execution_receipt = execute_claims(native_program["assets"],
                    row["components"]["facts"], row["components"]["statutes"], supplied)
                execution_receipt["execution_bank_sha256"] = csha(bank)
                execution_receipt["native_request_fingerprint"] = fingerprint
                parsed = {"answer": answer}
            except InvalidClaimProgram as exc:
                execution_error = repr(exc)
                parse_error = "Invalid explicitly submitted action: " + execution_error
        elif parse_error is None and row["family"] == "EV":
            # Only the shared public-label bijection. No computation, clamping,
            # semantic repair, names/value normalization or second generation.
            parsed = {"answer": {name: [{"citation": decode_reference(c["citation_ref"], catalog),
                                        "claim_value": c["claim_value"]} for c in claims]
                                  for name, claims in parsed.items()}}
        elif parse_error is None:
            # Original root task answer; this wrapper is internal storage only,
            # not an additional model-generated explanation or second answer.
            parsed = {"answer": decode_classification(parsed, catalog)}
        result = {"case_id": row["case_id"], "source_key": row["source_key"],
                  "family": row["family"], "stage": stage, "arm": arm,
                  "bank_sha256": csha(bank), "parsed": parsed,
                  "parse_error": parse_error, "raw_call_path": raw_call_path,
                  "native_program": native_program, "execution_receipt": execution_receipt,
                  "public_label_submission": public_label_submission,
                  "execution_error": execution_error,
                  "delivered_skill_ids": [s["id"] for s in supplied]}
        if alias is not None:
            result["physical_alias_of_identical_wire"] = alias
        RunStore.immutable_json(path.with_suffix(".answer.json"), result)
        if alias is not None:
            self.progress(stage, current_arm=arm, current_document_id=row["case_id"],
                          current_call="identical_native_response_reinterpreted_not_new_generation")
        return result

    def grade(self, records):
        """Called only after both current prequential arms are fully recorded."""
        for record in records:
            if "score" in record:
                continue
            row = next(r for r in self.rows if r["case_id"] == record["case_id"]
                       and r["family"] == record["family"])
            target = read(ROOT / self.cfg["grading_directory"] /
                          f"{row['case_id']}.json")["targets"][row["family"]]
            answer = record["parsed"]["answer"] if record["parse_error"] is None else None
            record["score"] = evaluate(row, answer, target)
        return records

    def teacher_body(self, current, seen, observations, rejected, *, teaching_task=None):
        fixed_joint = self.cfg.get("teacher_update_policy") == "joint_fixed_steps"
        if fixed_joint and teaching_task is not None:
            raise ValueError("Joint teaching cannot silently project to one task")
        if teaching_task is not None:
            if teaching_task not in FAMILIES:
                raise ValueError("Unknown teaching task")
            rejected = [d for d in rejected if d.get("teaching_task") == teaching_task]
        consolidation = self.cfg.get("training_phase") == CONSOLIDATION_PHASE
        optimization_ids = sorted({r["case_id"] for r in current})
        history_limit = 16 // len(FAMILIES) if fixed_joint else 16
        if consolidation:
            # Communication is bounded; optimization still replays every seen source.
            focus_limit = self.cfg["batch_source_cases"] // (len(FAMILIES) if fixed_joint else 1)
            current, _ = teacher_evidence_rows([], current, observations, [],
                history_limit=focus_limit,
                families=(teaching_task,) if teaching_task else FAMILIES)
        evidence, evidence_manifest = teacher_evidence_rows(current, seen, observations, rejected,
            history_limit=history_limit, families=(teaching_task,) if teaching_task else FAMILIES)
        if teaching_task is not None:
            evidence = [r for r in evidence if r["family"] == teaching_task]
        evidence_manifest.update({"teaching_task": teaching_task,
            "selected_task_records": len(evidence),
            "other_task_predictions_and_targets_not_supplied": teaching_task is not None})
        if consolidation:
            evidence_manifest["consolidation_scope"] = {
                "all_optimization_source_ids": optimization_ids,
                "all_sources_previously_observed_TRAIN": True,
                "communication_focus_source_ids": sorted({r["case_id"] for r in current}),
                "bounded_packet_not_a_validation_set": True,
                "original_gate_applied_to_all_seen_sources_together": True,
                "no_new_cases_or_TEST_labels": True}
            if fixed_joint:
                record_limit = self.cfg["batch_source_cases"] + 16
                if len(evidence) > record_limit:
                    raise ValueError("Joint teacher packet exceeds the matched task-record budget")
                evidence_manifest["matched_task_record_budget"] = {
                    "limit": record_limit, "actual": len(evidence),
                    "focus_source_limit": focus_limit, "historical_source_limit": history_limit,
                    "tasks_per_source": len(FAMILIES),
                    "same_task_record_limit_not_same_source_coverage_or_tokens": True}
        supplied_ids = set(evidence_manifest["selected_source_ids"])
        targets = {case: read(ROOT / self.cfg["grading_directory"] / f"{case}.json")["targets"]
                   for case in sorted(supplied_ids)}
        parent_tokens = self.meter.token_count(text=json.dumps(self.bank, ensure_ascii=False,
                                                               separators=(",", ":")))
        statutes = {csha(r["components"]["statutes"]): r["components"]["statutes"] for r in seen}
        # Task text is retained exactly, but the long public law corpus appears once.
        contracts = {r["family"]: {k: r["components"][k] for k in
                     ("instruction", "meta_instruction")}
                     for r in evidence}
        grounded = self.cfg.get("execution_contract") in (
            "source_grounded_claim_operations", "direct_statutory_claims")

        emitted_cache = {}

        def observation_view(record, *, include_emitted=False):
            if not grounded:
                return record
            receipt = record.get("execution_receipt")
            value = {"case_id": record["case_id"], "family": record["family"],
                    "executed_answer": (record.get("parsed") or {}).get("answer"),
                    "parse_error": record["parse_error"], "execution_error": record.get("execution_error"),
                    "score": record["score"]}
            if self.cfg.get("teacher_evidence_contract") == UTILITY_TEACHER_EVIDENCE_CONTRACT:
                value["bank_sha256"] = record.get("bank_sha256")
            if record.get("native_program") is not None:
                value["native_program"] = record["native_program"]
            if receipt is not None:
                value["actual_operations"] = [
                        {k: op[k] for k in ("asset_name", "asset_value", "citation", "operator_id",
                                           "limit", "claim_value")}
                        for op in receipt["actual_claim_operations"]]
            if include_emitted:
                value["public_native_final_submission"] = copy.deepcopy(record.get("public_label_submission"))
                value["native_claim_feedback"] = native_claim_feedback(
                    record, targets[record["case_id"]][record["family"]])
                path = record["raw_call_path"]
                if path not in emitted_cache:
                    call = read(ROOT / path)["calls"][0]
                    response = call["response"]
                    choice = response["choices"][0]
                    message = choice["message"]
                    reasoning = message.get("reasoning_content") or ""
                    native = message.get("content") or ""
                    emitted_cache[path] = {
                        "raw_call_path": path,
                        "finish_reason": choice["finish_reason"],
                        "emitted_by_executor_unverified": True,
                        "reasoning": {"text": reasoning[-1024:], "characters": len(reasoning),
                            "truncated_to_tail": len(reasoning) > 1024},
                        "native": native}
                emitted = copy.deepcopy(emitted_cache[path])
                native = emitted.pop("native")
                if record["parse_error"] is not None:
                    emitted["failed_native_final"] = {
                        "head": native[:256],
                        "tail": native[-256:] if len(native) > 512 else native[256:],
                        "characters": len(native),
                        "middle_omitted": len(native) > 512}
                value["source_model_emitted_evidence"] = emitted
            return value

        cases = []
        empty_by_key = {(r["case_id"], r["family"]): r for r in self.prequential_empty}
        frozen_by_key = {(r["case_id"], r["family"]): r for r in self.prequential_frozen}
        for row in evidence:
            key = row["case_id"], row["family"]
            case = {"source_case_id": row["case_id"], "family": row["family"],
                          **({"public_asset_reference_catalog": public_asset_catalog(row)}
                             if self.cfg.get("execution_contract_version") == 14 else {}),
                          "facts": row["components"]["facts"],
                          "public_solved_steps": row["components"]["solved_steps"],
                          "public_statutes_ref": csha(row["components"]["statutes"]),
                          "original_training_target": targets[row["case_id"]][row["family"]],
                          "actual_same_case_empty_answer": observation_view(
                              empty_by_key[key]),
                          "actual_parent_answer": observation_view(
                              observations[key], include_emitted=True)}
            identity = ("bank_sha256", "raw_call_path", "parsed", "parse_error", "execution_error", "score")
            if all(frozen_by_key[key].get(field) == empty_by_key[key].get(field) for field in identity):
                case["frozen_initial_answer_alias_of"] = "actual_same_case_empty_answer"
            elif consolidation and all(frozen_by_key[key].get(field) == observations[key].get(field)
                                       for field in identity):
                case["frozen_initial_answer_alias_of"] = "actual_parent_answer"
            else:
                case["actual_same_case_frozen_initial_answer"] = observation_view(frozen_by_key[key])
            cases.append(case)
        rejected_view = []
        for decision in rejected:
            replay_fields = {"actual_replay": "full_replay_task_count",
                "proposed_replay": "full_proposed_replay_task_count",
                "feedback_witness_replay": "bounded_feedback_witness_task_count"}
            value = {k: v for k, v in decision.items()
                     if k not in replay_fields}
            for field, count_field in replay_fields.items():
                if field not in decision:
                    continue
                value[count_field] = len(decision[field])
                value[field] = [observation_view(r, include_emitted=True)
                                for r in decision[field] if r["case_id"] in supplied_ids]
                if field == "feedback_witness_replay" and len(value[field]) != len(decision[field]):
                    raise ValueError("A bounded candidate feedback witness was omitted from teacher evidence")
            if "feedback_witness_replay" in decision:
                # This parent may have changed since an earlier TRAIN attempt.
                # Point at its current observation already supplied above; do not
                # duplicate answers/traces or silently retain a stale comparator.
                references = [observations[(r["case_id"], r["family"])]
                              for r in decision["feedback_witness_replay"]
                              if r["case_id"] in supplied_ids]
                value["bounded_feedback_reference_task_count"] = len(references)
                value["feedback_reference_replay"] = [{
                    "case_id": r["case_id"], "family": r["family"],
                    "reference_location": "already_seen_training.actual_parent_answer",
                    "reference_is_this_request_parent": True,
                    "bank_sha256": r.get("bank_sha256"), "score": copy.deepcopy(r["score"]),
                    "raw_call_path": r["raw_call_path"], "record_sha256": csha(r)} for r in references]
            rejected_view.append(value)
        actual_contracts, systems, schemas, system_ids, schema_ids = {}, {}, {}, {}, {}
        skill_messages, skill_message_ids = {}, {}
        for row in seen:
            if teaching_task is not None and row["family"] != teaching_task:
                continue
            key = "+".join(sorted(allowable_namespaces(row)))
            if self.cfg.get("execution_contract_version") == 14:
                key += ";asset_mentions=" + str(len(public_asset_catalog(row)))
            group = actual_contracts.setdefault(key, {})
            if row["family"] not in group:
                messages, schema, _ = actor_payload(row, self.bank, grounded=True,
                    direct_numeric=self.cfg.get("execution_contract") == "direct_statutory_claims",
                    asset_references=self.cfg.get("execution_contract_version") == 14)
                system, schema_key = messages[0]["content"], csha(schema)
                if system not in system_ids:
                    system_ids[system] = f"S{len(system_ids) + 1}"
                    systems[system_ids[system]] = system
                if schema_key not in schema_ids:
                    schema_ids[schema_key] = f"J{len(schema_ids) + 1}"
                    schemas[schema_ids[schema_key]] = schema
                skill_message = next((m["content"] for m in messages
                    if m["content"].startswith("Background reusable skills.")), None)
                if skill_message is not None and skill_message not in skill_message_ids:
                    skill_message_ids[skill_message] = f"K{len(skill_message_ids) + 1}"
                    skill_messages[skill_message_ids[skill_message]] = skill_message
                group[row["family"]] = {"system_ref": system_ids[system],
                    "response_schema_ref": schema_ids[schema_key],
                    "skill_message_ref": skill_message_ids.get(skill_message),
                    "skill_message_position": (("before_case" if row["family"] == "EC"
                                                else "after_case") if skill_message else None)}
        body = {"current_source_case_ids": sorted({r["case_id"] for r in current}),
                "teacher_evidence_contract": self.cfg.get("teacher_evidence_contract", TEACHER_EVIDENCE_CONTRACT),
                "teaching_task": teaching_task,
                "task_projection_update_contract": {
                    "enabled": teaching_task is not None,
                    "other_actor_memory_must_remain_identical": teaching_task is not None,
                    "single_shared_library_not_independent_copies": True,
                    "public_task_boundary_not_predicted_routing": True},
                "execution_teaching_contract": {
                    "knowledge_and_execution_errors_are_distinct": True,
                    "skill_defect_includes_incomplete_or_ineffective_operational_representation": True,
                    "true_legal_sentence_does_not_establish_instruction_adequacy": True,
                    "recurrent_failure_requires_instruction_reconsideration": True,
                    "correct_rule_requires_verbatim_anchor": True,
                    "example_marker": EXECUTION_EXAMPLE_MARKER,
                    "examples_are_in_existing_skill_text_not_a_second_layer": True,
                    "public_native_final_is_observed_not_automatically_correct": True},
                "task_boundary": {"start_task_id": 2,
                    "public_prior": "allowable jurisdictions already supplied; do not recompute them",
                    "outputs": "all eligible asset-law alternatives, not a final jointly allocated portfolio",
                    **({"asset_reference_encoding": {
                        "case_local_IDs_reset_per_case": True,
                        "public_description_only_literal_mentions_not_ownership_or_eligibility": True,
                        "do_not_store_instance_asset_IDs_as_reusable_law_or_amount_answers": True}}
                       if self.cfg.get("execution_contract_version") == 14 else {})},
                "current_parent_library": self.bank, "task_contracts": contracts,
                "skill_commit_policy": self.cfg["skill_commit_policy"],
                "adaptive_commit_objective": self.cfg.get("adaptive_commit_objective"),
                "public_TRAIN_edit_coordinates_before_proposed_shared_edits":
                    legal_edit_coordinates(self.bank, self.bank, seen),
                "full_serialized_library_token_budget": {
                    "actual_parent_tokens": parent_tokens,
                    "hard_cap": self.cfg["library_token_hard_cap"],
                    "net_growth_headroom": self.cfg["library_token_hard_cap"] - parent_tokens,
                    "basis": ("same live executor tokenizer; full text and metadata, no programs"
                              if self.cfg.get("execution_contract") == "direct_statutory_claims" else
                              "same live executor tokenizer; full library including program bodies")},
                "public_citation_label_catalog": statutory_catalog(seen[0]["components"]["statutes"]),
                "actual_actor_systems": systems,
                "actual_response_schemas": schemas,
                "actual_actor_skill_messages": skill_messages,
                "actor_visibility_contract": {
                    "skill_messages_are_exact_task_and_public_context_projections": True,
                    "EC_and_EV_do_not_share_skill_blocks_or_model_predictions": True,
                    "only_literal_public_solved_steps_supply_solved_prerequisites": True,
                    "EV_also_decides_eligibility_not_only_numeric_amounts": True,
                    "skill_message_references_are_teacher_evidence_not_new_actor_inputs": True},
                "complete_public_statutes": statutes,
                "actual_system_and_response_schema_by_public_context": actual_contracts,
                "already_seen_training": cases, "rejected_candidate_feedback": rejected_view,
                "training_evidence_manifest": evidence_manifest,
                "selected_record_view_preserves_program_answer_score_and_error": grounded,
                "native_claim_feedback_contract": {
                    "original_asset_and_claim_matcher_and_5pct_amount_tolerance": True,
                    "original_scores_and_targets_unchanged": True,
                    "only_selected_released_TRAIN_targets": True,
                    "same_response_alias_is_not_an_independent_control": True,
                    "own_B1_never_teacher_or_admission_feedback": True},
                "bounded_emitted_evidence_contract": {
                    "roles": ["actual_parent_answer", "rejected_candidate_replay"],
                    "reasoning_tail_max_characters": 1024,
                    "failed_native_final_head_tail_max_characters": 512,
                    "unabridged_raw_artifacts_retained": True,
                    "not_a_verified_causal_explanation": True},
                "future_cases_and_labels_not_supplied": True}
        if self.cfg.get("teacher_evidence_contract") == UTILITY_TEACHER_EVIDENCE_CONTRACT:
            body["admission_contract"] = self.cfg["admission_contract"]
            body["admission_constraints"] = {
                "current_native_and_full_per_task_must_not_decrease": True,
                "all_seen_native_and_full_per_task_must_not_decrease":
                    self.cfg["admission_contract"] == UTILITY_ADMISSION,
                "prior_mean_loss_limit": .01 if self.cfg["admission_contract"] == UTILITY_ADMISSION else 0,
                "count_diagnostics_are_separate_zero_increase_vetoes":
                    self.cfg["admission_contract"] == LEGACY_ADMISSION,
                "all_original_scores_invalid_zero_and_false_claim_penalties_unchanged": True}
            body["execution_teaching_contract"]["new_projection_including_split_has_empty_anchor"] = True
        return body

    def composed_replay(self, parent, proposed, accepted_tasks, seen, name, *,
                        legal_coordinates=None, accepted_coordinates=()):
        """Execute the actual mixed bank, using only already-observed raw wires.

        This is a TRAIN publication step. No case-level answer selection, new
        native generation, response repair or inference-time fallback occurs.
        """
        composed = (compose_task_edits(parent, proposed, accepted_tasks)
                    if legal_coordinates is None else
                    compose_legal_edits(parent, proposed, legal_coordinates, accepted_coordinates))
        tokens = self.meter.token_count(text=json.dumps(composed, ensure_ascii=False,
                                                        separators=(",", ":")))
        if tokens > self.cfg["library_token_hard_cap"]:
            raise ValueError(f"Composed library exceeds total token cap: {tokens}")
        # Preflight the entire cohort before writing/re-executing any member.
        for row in seen:
            messages, schema, _ = actor_payload(row, composed, grounded=True,
                direct_numeric=self.cfg.get("execution_contract") == "direct_statutory_claims",
                asset_references=self.cfg.get("execution_contract_version") == 14)
            fingerprint = csha({"messages": messages, "schema": schema,
                                "generation": self.cfg["generation"]})
            if fingerprint not in self.request_cache:
                raise ValueError("Task composition changed an evaluated native wire")
        replay = self.grade([self.answer(r, composed, name + "_composed_replay", "candidate")
                             for r in seen])
        return composed, replay, tokens

    def update(self, current, seen, parent_current):
        batch_parent = copy.deepcopy(self.bank)
        before = copy.deepcopy(batch_parent)
        closed_loop = self.cfg.get("candidate_feedback_policy") == "carry_partial_and_refine"
        coordinate = self.cfg["teacher_update_policy"] == "task_projection_coordinate"
        admission = self.cfg.get("admission_contract", LEGACY_ADMISSION)
        bounded_history = self.cfg.get("teacher_evidence_contract") == UTILITY_TEACHER_EVIDENCE_CONTRACT
        fixed_steps = coordinate or self.cfg["teacher_update_policy"] == "joint_fixed_steps"
        old_rows = [r for r in seen if r["case_id"] not in {v["case_id"] for v in current}]
        prior = [self.latest[(r["case_id"], r["family"])] for r in old_rows]
        observations = {**self.latest, **{(r["case_id"], r["family"]): r for r in parent_current}}
        initial_current, initial_prior = copy.deepcopy(parent_current), copy.deepcopy(prior)
        rejected = []
        if closed_loop and bounded_history:
            rejected = retained_candidate_feedback(
                self.out, self.current_batch, observations, csha(batch_parent))
        elif closed_loop and self.current_batch > 1:
            previous = read(self.out / "publications" / f"b{self.current_batch - 1}.json")
            if previous["bank_sha256"] != csha(batch_parent):
                raise ValueError("Previous publication must match the actual current parent")
            for index, previous_decision in enumerate(previous["training_decisions"], 1):
                feedback = candidate_feedback(previous_decision, observations, {
                    "batch": self.current_batch - 1, "attempt": index,
                    "publication_bank_sha256": previous["bank_sha256"]})
                if feedback is not None:
                    rejected.append(feedback)
        decisions = []
        grounded = self.cfg.get("execution_contract") == "source_grounded_claim_operations"
        direct = self.cfg.get("execution_contract") == "direct_statutory_claims"
        guidance_schema = DIRECT_GUIDANCE if direct else EXECUTABLE_GUIDANCE
        for attempt in range(1, self.cfg["max_candidate_attempts"] + 1):
            name = f"b{self.current_batch}_candidate{attempt}"
            teaching_task = self.cfg["task_update_schedule"][attempt - 1] if coordinate else None
            body = (self.teacher_body(current, seen, observations, rejected, teaching_task=teaching_task)
                    if coordinate else self.teacher_body(current, seen, observations, rejected))
            supplied_ids = body["training_evidence_manifest"]["selected_source_ids"]
            system = DIRECT_AUTHOR_SYSTEM if direct else AUTHOR_SYSTEM + PROGRAM_AUTHOR_ADDITION
            if direct:
                system = system.replace(
                    "Do not store case IDs, debtors, exact asset names or values, answer tables, output "
                    "format tricks, or copied target sets in skills.",
                    "Do not store case IDs, debtors, exact asset names or instance values, answer "
                    "tables, or copied target sets. A deidentified procedural output illustration "
                    "is allowed under the execution-teaching contract, not an answer lookup.")
            system += EXECUTION_AWARE_ADDITION
            if coordinate:
                system += TASK_PROJECTION_TEACHING
            if self.cfg.get("training_phase") == CONSOLIDATION_PHASE:
                system += CONSOLIDATION_TEACHING
            if closed_loop:
                system += CANDIDATE_FEEDBACK_ADDITION
                body["candidate_feedback_contract"] = {
                    "policy": "carry_partial_and_refine", "attempt": attempt,
                    "max_attempts": self.cfg["max_candidate_attempts"],
                    "current_attempt_parent_bank_sha256": csha(before),
                    "previous_publication_only_not_unbounded_history": True,
                    "failure_witness_limit_per_proposal": 8,
                    "single_final_publication_after_bounded_TRAIN_refinement": True,
                    "teacher_update_policy": self.cfg["teacher_update_policy"],
                    "teaching_task": teaching_task,
                    "coordinate_steps_not_same_task_retries": coordinate}
            if bounded_history:
                body["candidate_feedback_contract"].pop("previous_publication_only_not_unbounded_history")
                body["candidate_feedback_contract"].update({
                    "history_policy": BOUNDED_FAILURE_HISTORY,
                    "max_historical_proposals_per_task": 1,
                    "historical_candidates_are_not_current_parent_reruns": True})
                system = teaching_system_contract(system, admission)
            response = self.teacher_call(name, system, body,
                diagnosed_edit_schema(differential_schema(FAMILIES, before, supplied_ids,
                    guidance_schema=guidance_schema), supplied_ids))
            delta = response["delta"]
            candidate = apply_differential_publication(before, delta, FAMILIES,
                supplied_ids, guidance_schema=guidance_schema)
            try:
                edit_audit = validate_edit_diagnoses(before, candidate, response["diagnoses"], supplied_ids)
                if coordinate:
                    edit_audit["task_projection_boundary"] = validate_task_projection_edit(
                        before, candidate, teaching_task)
            except ValueError as exc:
                decision = {"accepted": False, "reason": "invalid_edit_diagnosis_or_protected_rule",
                    "candidate": candidate, "delta": delta, "edit_diagnoses": response["diagnoses"],
                    "diagnosis_error": str(exc), "new_native_calls": 0,
                    "teaching_task": teaching_task}
                RunStore.immutable_json(self.out / "candidates" / f"{name}.json", decision)
                decisions.append(decision)
                rejected.append(decision)
                continue
            RunStore.immutable_json(self.out / "teacher" / name / "edit_audit.json", edit_audit)
            if grounded or direct:
                try:
                    validate_scoped_bank(candidate)
                    validate_scopes(candidate, current[0]["components"]["statutes"])
                    for operator in operator_catalog(candidate).values():
                        # Compile/run pure source arithmetic, not a model qualification loop.
                        for source in current:
                            if operator["citation"] not in law_blocks(source["components"]["statutes"]):
                                raise InvalidClaimProgram("Operator citation is not a current public header")
                            execute_limit(operator["limit_expression"], source["components"]["facts"])
                except (ValueError, ValidationError) as exc:
                    decision = {"accepted": False, "candidate": candidate, "delta": delta,
                                "source_program_compile_error": repr(exc), "new_native_calls": 0,
                                "teaching_task": teaching_task}
                    RunStore.immutable_json(self.out / "candidates" / f"{name}.json", decision)
                    decisions.append(decision)
                    rejected.append(decision)
                    continue
            tokens = self.meter.token_count(text=json.dumps(candidate, ensure_ascii=False,
                                                            separators=(",", ":")))
            if tokens > self.cfg["library_token_hard_cap"]:
                decision = {"accepted": False, "reason": "complete_library_token_cap",
                            "actual_tokens": tokens, "candidate": candidate, "delta": delta,
                            "teaching_task": teaching_task}
                RunStore.immutable_json(self.out / "candidates" / f"{name}.json", decision)
                decisions.append(decision)
                rejected.append(decision)
                continue
            if candidate == before:
                decisions.append({"accepted": False, "explicit_noop": True, "delta": delta,
                                  "teaching_task": teaching_task})
                if fixed_steps:
                    continue
                break
            replay = self.grade(self._dispatch.native(
                lambda r: self.answer(r, candidate, name + "_replay", "candidate"), seen))
            keys = {r["case_id"] for r in current}
            candidate_current = [r for r in replay if r["case_id"] in keys]
            candidate_prior = [r for r in replay if r["case_id"] not in keys]
            full_proposal = acceptance(parent_current, candidate_current, prior, candidate_prior,
                                       contract=admission)
            task_decisions = task_admission(parent_current, candidate_current, prior, candidate_prior,
                                            contract=admission)
            policy = self.cfg["skill_commit_policy"]
            coordinates, scope_decisions, accepted_coordinates = None, {}, []
            if policy in ("legal_scope", "adaptive_legal"):
                coordinates = legal_edit_coordinates(before, candidate, seen)
                scope_decisions = legal_scope_admission(
                    coordinates, parent_current, candidate_current, prior, candidate_prior,
                    contract=admission)
                accepted_coordinates = [c["id"] for c in coordinates if scope_decisions[c["id"]]["accepted"]]
            accepted_tasks = ([f for f in FAMILIES if task_decisions[f]["accepted"]]
                              if policy == "task_local" else
                              [f for f in FAMILIES if any(c["task"] == f and c["id"] in accepted_coordinates
                                                         for c in coordinates)]
                              if policy in ("legal_scope", "adaptive_legal") else
                              list(FAMILIES) if full_proposal["accepted"] else [])
            decision = {"accepted": False, "candidate": candidate, "delta": delta,
                        "edit_audit": edit_audit,
                        "teaching_task": teaching_task,
                        "skill_commit_policy": policy,
                        "proposed_bank": candidate, "proposed_tokens": tokens,
                        "proposed_whole_bank_acceptance": full_proposal,
                        "task_admission": task_decisions, "accepted_tasks": accepted_tasks,
                        "legal_edit_coordinates": coordinates, "legal_scope_admission": scope_decisions,
                        "accepted_legal_coordinates": accepted_coordinates,
                        "actual_tokens": tokens, "actual_replay": replay,
                        "TRAIN_optimization_not_independent_validation": True}
            if not accepted_tasks:
                decision["reason"] = ("no_independently_improving_legal_edit" if policy in ("legal_scope", "adaptive_legal") else
                                      "no_independently_improving_task_edit" if policy == "task_local"
                                      else "whole_proposal_failed_original_full_gate")
            else:
                try:
                    committed, actual_replay, actual_tokens = self.composed_replay(
                        before, candidate, accepted_tasks, seen, name,
                        legal_coordinates=coordinates, accepted_coordinates=accepted_coordinates)
                except ValueError as exc:
                    decision["reason"] = "task_composition_rejected"
                    decision["composition_error"] = repr(exc)
                    decision["accepted_tasks"] = []
                    decision["accepted_legal_coordinates"] = []
                else:
                    actual_current = [r for r in actual_replay if r["case_id"] in keys]
                    actual_prior = [r for r in actual_replay if r["case_id"] not in keys]
                    # The original full gate is authoritative, not the mask alone.
                    decision.update(acceptance(parent_current, actual_current, prior, actual_prior,
                                               contract=admission))
                    decision.update({"candidate": committed, "actual_tokens": actual_tokens,
                        "actual_replay": actual_replay, "proposed_replay": replay,
                        "current_effect": paired_effect(parent_current, actual_current),
                        "prior_effect": paired_effect(prior, actual_prior)})
                    if not decision["accepted"]:
                        decision["reason"] = "composed_bank_failed_original_full_gate"
                        decision["accepted_tasks"] = []
                        decision["accepted_legal_coordinates"] = []
            if policy == "adaptive_legal":
                parent_replay = [*parent_current, *prior]
                component_gain = (balanced_replay_gain(parent_replay, decision["actual_replay"],
                                                      contract=admission)
                                  if decision["accepted"] else None)
                joint_gain = (balanced_replay_gain(parent_replay, replay, contract=admission)
                              if full_proposal["accepted"] else None)
                component_assessment = {
                    "accepted": decision["accepted"], "reason": decision.get("reason"),
                    "accepted_legal_coordinates": list(decision["accepted_legal_coordinates"]),
                    "bank_sha256": csha(decision["candidate"]) if decision["accepted"] else None,
                    "gain": component_gain}
                use_joint = (joint_gain is not None
                             and (component_gain is None or joint_gain >= component_gain))
                if use_joint:
                    decision.update(full_proposal)
                    decision.update({"candidate": candidate, "actual_tokens": tokens,
                        "actual_replay": replay, "accepted_tasks": list(FAMILIES),
                        "accepted_legal_coordinates": [],
                        "current_effect": paired_effect(parent_current, candidate_current),
                        "prior_effect": paired_effect(prior, candidate_prior)})
                    decision.pop("reason", None)
                decision["adaptive_commit_selection"] = {
                    "objective": self.cfg["adaptive_commit_objective"],
                    "joint_gain": joint_gain, "component_assessment": component_assessment,
                    "selected": "joint" if use_joint else
                                "dependency_components" if decision["accepted"] else "none",
                    "only_seen_TRAIN_scores_used": True, "new_native_generations": 0}
                if decision["accepted"]:
                    actual_current = [r for r in decision["actual_replay"] if r["case_id"] in keys]
                    actual_prior = [r for r in decision["actual_replay"] if r["case_id"] not in keys]
            # All policies stop on the same delivered task projections, not JSON record layout.
            decision["proposal_fully_committed"] = decision["accepted"] and all(
                task_view(decision["candidate"], f) == task_view(candidate, f) for f in FAMILIES)
            if closed_loop:
                decision["attempt_parent_bank_sha256"] = csha(before)
            RunStore.immutable_json(self.out / "candidates" / f"{name}.json", decision)
            decisions.append(decision)
            if decision["accepted"]:
                self.bank = decision["candidate"]
                self.latest = {(r["case_id"], r["family"]): r for r in decision["actual_replay"]}
                if not closed_loop:
                    break
                feedback = candidate_feedback(decision, self.latest, {
                    "batch": self.current_batch, "attempt": attempt,
                    "current_committed_bank_sha256": csha(self.bank)})
                if feedback is None and not fixed_steps:
                    break
                # Keep the accepted subset as the next attempt's real parent.
                # A failed later proposal cannot undo it or use cached scores.
                if feedback is not None:
                    rejected.append(feedback)
                before = copy.deepcopy(self.bank)
                parent_current = actual_current
                prior = actual_prior
                observations = dict(self.latest)
            elif closed_loop:
                feedback = candidate_feedback(decision, observations, {
                    "batch": self.current_batch, "attempt": attempt,
                    "current_committed_bank_sha256": csha(self.bank)})
                if feedback is not None:
                    rejected.append(feedback)
            else:
                rejected.append(decision)
        if self.bank == batch_parent:
            self.latest = observations
        elif closed_loop:
            final_current = [self.latest[(r["case_id"], r["family"])] for r in current]
            final_prior = [self.latest[(r["case_id"], r["family"])] for r in old_rows]
            if not acceptance(initial_current, final_current, initial_prior, final_prior,
                              contract=admission)["accepted"]:
                raise ValueError("Final refined bank must also pass the original batch-parent full gate")
        publication = {"at": now(), "bank": self.bank, "parent_bank_sha256": csha(batch_parent),
                       "skill_commit_policy": self.cfg["skill_commit_policy"],
                       "teacher_update_policy": self.cfg["teacher_update_policy"],
                       "bank_sha256": csha(self.bank), "training_decisions": decisions,
                       "future_performance_not_used": True,
                       "training_acceptance_does_not_guarantee_generalization": True}
        if closed_loop:
            publication["candidate_feedback_policy"] = "carry_partial_and_refine"
        if bounded_history:
            publication["admission_contract"] = admission
            publication["feedback_retention"] = BOUNDED_FAILURE_HISTORY
        RunStore.immutable_json(self.out / "publications" / f"b{self.current_batch}.json", publication)
        return publication

    def consolidate(self):
        rows, before, empty, origins, _, original = observed_consolidation_inputs(self.cfg)
        if self.cfg.get("teacher_update_policy") not in ("task_projection_coordinate", "joint_fixed_steps"):
            raise ValueError("Consolidation requires a declared fixed two-step teaching schedule")
        if self.cfg["initial_library_prior_exposure_distinct_sources"] != len(rows) // len(FAMILIES):
            raise ValueError("Consolidation must disclose the full prior TRAIN exposure")
        self.current_batch = 1  # Continuation round, not an empty first-encounter batch.
        self.latest = {(r["case_id"], r["family"]): copy.deepcopy(r) for r in before}
        self.request_cache = copy.deepcopy(origins)
        self.prequential_empty = copy.deepcopy(empty)
        self.prequential_direct = copy.deepcopy(empty)
        self.prequential_frozen = copy.deepcopy(before)
        self.prequential_skills = copy.deepcopy(before)
        RunStore.immutable_json(self.out / "consolidation_started.json", {
            "at": now(), "training_phase": CONSOLIDATION_PHASE,
            "parent_acquisition_run": self.cfg["consolidation_parent_run"],
            "parent_bank_sha256": csha(self.bank), "prior_source_exposure": len(rows) // 2,
            "imported_exact_native_origins": len(origins),
            "before_metrics": metrics(before), "all_seen_source_ids": sorted({r["case_id"] for r in rows}),
            "parent_acquisition_teacher_responses": original["actual_teacher_responses"],
            "new_teacher_responses_max": self.cfg["max_candidate_attempts"],
            "new_native_calls_max": len(rows) * (
                2 if self.cfg["teacher_update_policy"] == "joint_fixed_steps" else 1),
            "original_actor_scorer_and_admission_unchanged": True,
            "not_a_new_empty_stream_or_independent_repeat_or_TEST": True})
        publication = self.update(rows, rows, before)
        after = [self.latest[r["case_id"], r["family"]] for r in rows]
        if any(r["bank_sha256"] != publication["bank_sha256"] for r in after):
            raise ValueError("Consolidation summary must use the actually published bank")
        result = {"at": now(), "training_phase": CONSOLIDATION_PHASE,
            "parent_acquisition_run": self.cfg["consolidation_parent_run"],
            "before": metrics(before), "after": metrics(after), "paired": paired_effect(before, after),
            "bank_sha256": publication["bank_sha256"], "bank_records": len(self.bank),
            "actual_new_native_calls": len(self.native), "actual_new_teacher_responses": len(self.teachers),
            "linked_acquisition_native_calls": original["actual_native_calls"],
            "linked_acquisition_teacher_responses": original["actual_teacher_responses"],
            "total_linked_teacher_responses": original["actual_teacher_responses"] + len(self.teachers),
            "full_seen_TRAIN_only_not_future_or_TEST": True}
        self.summaries.append(result)
        RunStore.immutable_json(self.out / "consolidation_result.json", result)
        return "completed_seen_TRAIN_consolidation"

    def execute(self):
        if self.cfg.get("training_phase") == CONSOLIDATION_PHASE:
            return self.consolidate()
        batch_size = self.cfg["batch_source_cases"]
        total = self.cfg["source_cases"] // batch_size
        for batch in range(1, total + 1):
            self.current_batch = batch
            def batch_of(row):
                return row.get("batch", (row["case_id"] - 1) // batch_size + 1)
            current = [r for r in self.rows if batch_of(r) == batch]
            seen = [r for r in self.rows if batch_of(r) <= batch]
            empty, skills, frozen, direct, first_frozen = [], [], [], [], []
            evaluate_first_frozen = self.cfg.get("frozen_after_first_batch_control", False)
            native_before = len(self.native)
            def answer_row(row):
                # Fixed rotation, and exact-wire sharing only. No quality selection.
                arms = ("empty", "frozen_initial", "skills", "empty_direct_numeric")
                if evaluate_first_frozen:
                    arms += ("frozen_after_B1",)
                offset = (row["case_id"] + FAMILIES[row["family"]]) % len(arms)
                arms = arms[offset:] + arms[:offset]
                answers = {}
                for arm in arms:
                    bank = self.bank if arm == "skills" else self.frozen_bank if arm == "frozen_initial" else []
                    if arm == "frozen_after_B1":
                        bank = self.first_batch_frozen_bank
                    # One reuse path for every arm/stage. Even an identical
                    # native response must execute against this arm's bank.
                    answers[arm] = self.answer(row, bank, f"b{batch}_prequential", arm)
                return answers
            for answers in self._dispatch.native(answer_row, current):
                empty.append(answers["empty"])
                skills.append(answers["skills"])
                frozen.append(answers["frozen_initial"])
                direct.append(answers["empty_direct_numeric"])
                if evaluate_first_frozen:
                    first_frozen.append(answers["frozen_after_B1"])
            # Current labels are first read only after ALL current arms exist.
            self.grade(empty + skills + frozen + direct + first_frozen)
            batch_records = {"empty": empty, "skills": skills, "frozen_initial": frozen,
                             "empty_direct_numeric": direct}
            if evaluate_first_frozen:
                batch_records["frozen_after_B1"] = first_frozen
            RunStore.immutable_json(self.out / "batches" / f"b{batch}_prequential_records.json",
                                    batch_records)
            self.prequential_empty.extend(empty)
            self.prequential_skills.extend(skills)
            self.prequential_frozen.extend(frozen)
            self.prequential_direct.extend(direct)
            if evaluate_first_frozen:
                self.prequential_first_batch_frozen.extend(first_frozen)
            pre = {"batch": batch, "source_cases": batch_size, "tasks_per_arm": len(current),
                   "empty": metrics(empty), "skills": metrics(skills), "frozen_initial": metrics(frozen),
                   "empty_direct_numeric": metrics(direct),
                   "effect": paired_effect(empty, skills), "parent_bank_sha256": csha(self.bank),
                   "online_minus_frozen": paired_effect(frozen, skills),
                   "online_minus_direct_numeric": paired_effect(direct, skills),
                   "prequential_actual_new_native_calls": len(self.native) - native_before,
                   "parent_skill_count": len(self.bank), "official_test_opened": False}
            if evaluate_first_frozen:
                pre.update({"frozen_after_B1": metrics(first_frozen),
                    "online_minus_frozen_after_B1": paired_effect(first_frozen, skills),
                    "frozen_after_B1_bank_sha256": csha(self.first_batch_frozen_bank),
                    "frozen_after_B1_snapshot_already_taken": batch > 1,
                    "frozen_after_B1_evaluation_only_not_teacher_feedback": True})
            RunStore.immutable_json(self.out / "batches" / f"b{batch}_prequential.json", pre)
            self.progress("prequential_scored", latest_batch=pre)
            publication = self.update(current, seen, skills)
            if evaluate_first_frozen and batch == 1:
                # A prespecified time boundary, not the first successful/best bank.
                # Empty/rejected B1 remains empty; never wait for a better update.
                self.first_batch_frozen_bank = copy.deepcopy(self.bank)
                RunStore.immutable_json(self.out / "frozen_after_B1.json", {
                    "at": now(), "bank": self.first_batch_frozen_bank,
                    "bank_sha256": csha(self.first_batch_frozen_bank),
                    "publication_bank_sha256": publication["bank_sha256"],
                    "source_case_ids_seen": sorted({r["case_id"] for r in current}),
                    "source_keys_seen": sorted({r["source_key"] for r in current}),
                    "freeze_after_exactly_batch": 1,
                    "not_selected_by_later_performance_or_nonempty_success": True,
                    "evaluation_only_never_teacher_or_admission_feedback": True})
            pre["resulting_bank_sha256"] = publication["bank_sha256"]
            pre["resulting_skill_count"] = len(self.bank)
            pre["accepted_update"] = publication["parent_bank_sha256"] != publication["bank_sha256"]
            self.summaries.append(pre)
            RunStore.atomic_json(self.out / "batch_summary.json", self.summaries)
            self.progress("batch_complete", latest_batch=pre)
            # A fixed falsification stop, not a choice of an earlier winning bank.
            recent = self.summaries[-2:]
            # B1 is the blind prior, not online experience. Repeated evolution
            # harm is assessed from B2 onward, never from a cold B1 alone.
            if batch >= 3 and len(recent) == 2 and all(r["parent_skill_count"] and
                    (r["effect"]["mean_f1_difference"] < -0.02
                     or r["online_minus_frozen"]["mean_f1_difference"] < -0.02
                     or r["online_minus_direct_numeric"]["mean_f1_difference"] < -0.02
                     or r["skills"]["EV"]["full_output_f1"]
                        < r["frozen_initial"]["EV"]["full_output_f1"] - 0.02) for r in recent):
                return "stopped_repeated_forward_harm"
        return "completed_bounded_mechanism_study"

    def run(self):
        status = "failed"
        try:
            status = self.execute()
            completion = {"at": now(), "run_id": self.run_id, "status": status,
                          "execution_dispatch": self._dispatch.receipt(),
                          "batch_summary": self.summaries, "bank": self.bank,
                          "prequential_empty": metrics(self.prequential_empty),
                          "prequential_skills": metrics(self.prequential_skills),
                          "prequential_frozen_initial": metrics(self.prequential_frozen),
                          "prequential_empty_direct_numeric": metrics(self.prequential_direct),
                          "paired": paired_effect(self.prequential_empty, self.prequential_skills),
                          "online_minus_frozen": paired_effect(self.prequential_frozen, self.prequential_skills),
                          "online_minus_direct_numeric": paired_effect(self.prequential_direct,
                                                                        self.prequential_skills),
                          "actual_native_calls": len(self.native),
                          "actual_teacher_responses": len(self.teachers),
                          "actual_teacher_attempts": self.teacher_attempts,
                          "cross_stage_identical_wire_reuses": self.reuse_events,
                          "native_prompt_tokens": sum(v["response"]["prompt_tokens"] for v in self.native if v["response"]),
                          "native_completion_tokens": sum(v["response"]["completion_tokens"] for v in self.native if v["response"]),
                          "no_official_test_or_paper_success_claim": True}
            if self.cfg.get("frozen_after_first_batch_control", False):
                completion.update({"prequential_frozen_after_B1": metrics(self.prequential_first_batch_frozen),
                    "online_minus_frozen_after_B1": paired_effect(
                        self.prequential_first_batch_frozen, self.prequential_skills),
                    "frozen_after_B1_bank_sha256": csha(self.first_batch_frozen_bank),
                    "frozen_after_B1_evaluation_only_not_teacher_feedback": True})
            if self.cfg.get("training_phase") == CONSOLIDATION_PHASE:
                completion = {k: v for k, v in completion.items()
                              if not k.startswith(("prequential_", "online_minus_")) and k != "paired"}
                completion.update({"training_phase": CONSOLIDATION_PHASE,
                    "parent_acquisition_run": self.cfg["consolidation_parent_run"],
                    "not_new_first_forecasts_or_independent_repeat_or_TEST": True,
                    "consolidation_result": self.summaries[-1]})
            RunStore.immutable_json(self.out / "completion.json", completion)
        except Exception as exc:
            RunStore.immutable_json(self.out / "failure.json", {
                "at": now(), "error": repr(exc), "traceback": traceback.format_exc(),
                "actual_native_calls": len(self.native), "actual_teacher_responses": len(self.teachers),
                "actual_teacher_attempts": self.teacher_attempts, "actual_bank": self.bank,
                "cross_stage_identical_wire_reuses": self.reuse_events})
            raise
        finally:
            self.progress("terminal", state=status)
            files = [str(p.relative_to(ROOT)) for p in self.out.rglob("*")
                     if p.is_file() and "/cache/" not in str(p)]
            receipt = preserve(self.run_id, "actual-terminal", files)
            RunStore.immutable_json(self.out / "terminal_preservation.json", receipt)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "freeze", "run"))
    parser.add_argument("config", type=Path)
    args = parser.parse_args()
    config_path = args.config.resolve()
    if args.action == "prepare":
        receipt = prepare(read(config_path))
        frozen = freeze(config_path)
        print(json.dumps({"prepared": receipt, "bound_files": len(frozen["files"])}))
    elif args.action == "freeze":
        # Explicitly finish staged offline preparation without regenerating cases.
        frozen = freeze(config_path)
        print(json.dumps({"bound_files": len(frozen["files"])}))
    else:
        with (ROOT / "artifacts/openexempt_training.lock").open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            Online(config_path).run()


if __name__ == "__main__":
    main()
