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


def actor_payload(row, bank, *, grounded=True, direct_numeric=False, asset_references=False):
    if not grounded:
        raise ValueError("Only the public-namespace claim contract is implemented")
    if direct_numeric and any(s["guidance"]["operators"] for s in bank):
        raise ValueError("Direct-answer skills cannot publish numerical programs")
    if asset_references and not direct_numeric:
        raise ValueError("Public asset references require the common direct-answer contract")
    supplied = visible(active_bank(row, bank), row["family"])
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
        messages.append({"role": "user", "content":
                         "Background reusable skills. The current legal case follows. "
                         "Use these only when applicable; they are not current answers:\n" +
                         json.dumps(delivered, ensure_ascii=False, separators=(",", ":"))})
    messages.append({"role": "user", "content":
        (("Public case-local literal asset-mention references (IDs reset in every case; "
          "closed public lexicon; all legal judgments remain yours):\n" + json.dumps(asset_catalog, ensure_ascii=False,
          separators=(",", ":")) + "\n\n") if asset_references else "") +
        "Public citation label vocabulary. These are public headers in the already-given "
        "allowable jurisdictions, NOT an asset-eligibility answer:\n" +
        json.dumps(catalog, ensure_ascii=False, separators=(",", ":")) +
        "\n\n" + (direct_case_input(row, asset_references=asset_references)
                    if direct_numeric else active_case_input(row))})
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


def acceptance(parent_current, candidate_current, parent_prior, candidate_prior):
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
    improvement = any(_head_admission(f, a, b, pa, pb)["strict_current_improvement"] for f in FAMILIES)
    return {"accepted": (current_ok and prior_ok and current_full_ok and prior_full_ok
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


def task_admission(parent_current, candidate_current, parent_prior, candidate_prior):
    """Select TRAIN edit coordinates, never inference answers or case subsets."""
    a, b = metrics(parent_current), metrics(candidate_current)
    pa, pb = metrics(parent_prior), metrics(candidate_prior)
    return {family: _head_admission(family, a, b, pa, pb) for family in FAMILIES}


def _head_admission(family, a, b, pa, pb):
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
    return {"accepted": bool(current_ok and prior_ok and strict and full_current_ok and full_prior_ok
                             and current_audit_ok and prior_audit_ok),
            "current_nonregression": current_ok, "prior_nonregression": prior_ok,
            "strict_current_improvement": bool(strict),
            "current_full_output_nonregression": full_current_ok,
            "prior_full_output_nonregression": full_prior_ok,
            "current_negative_asset_and_format_nonregression": current_audit_ok,
            "prior_negative_asset_and_format_nonregression": prior_audit_ok}


def legal_scope_admission(coordinates, parent_current, candidate_current, parent_prior, candidate_prior):
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
            **_head_admission(family, *(metrics(rows) for rows in groups)),
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


def balanced_replay_gain(before, after):
    """TRAIN selection over paired, already observed full replays, not a TEST metric."""
    for records in (before, after):
        if len({(r["case_id"], r["family"]) for r in records}) != len(records):
            raise ValueError("Adaptive selection requires distinct paired source/tasks")
    paired_effect(before, after)
    a, b = metrics(before), metrics(after)
    if not set(FAMILIES) <= set(a) or not set(FAMILIES) <= set(b):
        raise ValueError("Adaptive selection requires complete paired EC and EV replays")
    gains = [b[f]["f1"] - a[f]["f1"] for f in FAMILIES]
    return min(gains), sum(gains) / len(gains)


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
    fields = ("delta", "reason", "source_program_compile_error", "composition_error",
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


def teacher_evidence_rows(current, seen, observations, rejected, *, history_limit=16):
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
    parent_quality = {i: min(quality(observations[(i, f)]) for f in FAMILIES)
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
    bindings = {str(p.relative_to(ROOT)): sha(p) for p in sorted(files)}
    packages = {dist.metadata["Name"]: dist.version for dist in importlib.metadata.distributions()}
    manifest = {"config_sha256": sha(config_path), "files": bindings, "packages": packages,
                "prepared_at": now(), "no_this_run_performance_observed_before_freeze": True,
                "warm_sources_are_previously_observed_TRAIN": bool(cfg.get("warm_source_case_ids"))}
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
        if self.cfg["skill_commit_policy"] == "adaptive_legal" and self.cfg.get(
                "adaptive_commit_objective") != "seen_source_min_family_gain_then_mean_v1":
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

    def answer(self, row, bank, stage, arm):
        self.check()
        grounded = self.cfg.get("execution_contract") in (
            "source_grounded_claim_operations", "direct_statutory_claims")
        direct = (self.cfg.get("execution_contract") == "direct_statutory_claims"
                  or arm == "empty_direct_numeric")
        asset_references = self.cfg.get("execution_contract_version") == 14
        messages, schema, supplied = actor_payload(row, bank, grounded=grounded,
            direct_numeric=direct, asset_references=asset_references)
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

    def teacher_body(self, current, seen, observations, rejected):
        evidence, evidence_manifest = teacher_evidence_rows(current, seen, observations, rejected)
        supplied_ids = set(evidence_manifest["selected_source_ids"])
        parent_tokens = self.meter.token_count(text=json.dumps(self.bank, ensure_ascii=False,
                                                               separators=(",", ":")))
        statutes = {csha(r["components"]["statutes"]): r["components"]["statutes"] for r in seen}
        # Task text is retained exactly, but the long public law corpus appears once.
        contracts = {r["family"]: {k: r["components"][k] for k in
                     ("instruction", "meta_instruction")}
                     for r in seen}
        grounded = self.cfg.get("execution_contract") in (
            "source_grounded_claim_operations", "direct_statutory_claims")

        emitted_cache = {}

        def observation_view(record, *, include_emitted=False):
            if not grounded:
                return record
            receipt = record.get("execution_receipt")
            value = {"case_id": record["case_id"], "family": record["family"],
                    "native_program": record.get("native_program"),
                    "physical_alias_of_identical_wire": record.get("physical_alias_of_identical_wire"),
                    "executed_answer": (record.get("parsed") or {}).get("answer"),
                    "parse_error": record["parse_error"], "execution_error": record.get("execution_error"),
                    "score": record["score"], "actual_operations": None if receipt is None else [
                        {k: op[k] for k in ("asset_name", "asset_value", "citation", "operator_id",
                                           "limit", "claim_value")}
                        for op in receipt["actual_claim_operations"]]}
            if include_emitted:
                path = record["raw_call_path"]
                if path not in emitted_cache:
                    call = read(ROOT / path)["calls"][0]
                    response = call["response"]
                    choice = response["choices"][0]
                    message = choice["message"]
                    reasoning = message.get("reasoning_content") or ""
                    native = message.get("content") or ""
                    emitted_cache[path] = {
                        "raw_call_path": path, "canonical_call_sha256": csha(call),
                        "response_id": response["id"],
                        "finish_reason": choice["finish_reason"],
                        "prompt_tokens": response["usage"]["prompt_tokens"],
                        "completion_tokens": response["usage"]["completion_tokens"],
                        "max_completion_tokens": call["request"]["max_tokens"],
                        "emitted_by_executor_unverified": True,
                        "reasoning": {"text": reasoning[-1024:], "characters": len(reasoning),
                            "canonical_text_sha256": csha(reasoning),
                            "truncated_to_tail": len(reasoning) > 1024},
                        "native": native}
                emitted = copy.deepcopy(emitted_cache[path])
                native = emitted.pop("native")
                if record["parse_error"] is not None:
                    emitted["failed_native_final"] = {
                        "head": native[:256],
                        "tail": native[-256:] if len(native) > 512 else native[256:],
                        "characters": len(native), "canonical_text_sha256": csha(native),
                        "middle_omitted": len(native) > 512}
                value["source_model_emitted_evidence"] = emitted
            return value

        cases = []
        empty_by_key = {(r["case_id"], r["family"]): r for r in self.prequential_empty}
        frozen_by_key = {(r["case_id"], r["family"]): r for r in self.prequential_frozen}
        for row in evidence:
            target = read(ROOT / self.cfg["grading_directory"] /
                          f"{row['case_id']}.json")["targets"][row["family"]]
            cases.append({"source_case_id": row["case_id"], "family": row["family"],
                          **({"public_asset_reference_catalog": public_asset_catalog(row)}
                             if self.cfg.get("execution_contract_version") == 14 else {}),
                          "facts": row["components"]["facts"],
                          "public_solved_steps": row["components"]["solved_steps"],
                          "public_statutes_ref": csha(row["components"]["statutes"]),
                          "original_training_target": target,
                          "actual_same_case_empty_answer": observation_view(
                              empty_by_key[(row["case_id"], row["family"])]),
                          "actual_same_case_frozen_initial_answer": observation_view(
                              frozen_by_key[(row["case_id"], row["family"])]),
                          "actual_parent_answer": observation_view(
                              observations[(row["case_id"], row["family"])], include_emitted=True)})
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
        actual_contracts = {}
        for row in seen:
            key = "+".join(sorted(allowable_namespaces(row)))
            if self.cfg.get("execution_contract_version") == 14:
                key += ";asset_mentions=" + str(len(public_asset_catalog(row)))
            group = actual_contracts.setdefault(key, {})
            if row["family"] not in group:
                messages, schema, _ = actor_payload(row, self.bank, grounded=True,
                    direct_numeric=self.cfg.get("execution_contract") == "direct_statutory_claims",
                    asset_references=self.cfg.get("execution_contract_version") == 14)
                group[row["family"]] = {"system": messages[0]["content"],
                                        "response_schema": schema}
        return {"current_source_case_ids": sorted({r["case_id"] for r in current}),
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
                "actual_actor_system": (next(group["EC"]["system"] for group in actual_contracts.values()
                    if "EC" in group) if self.cfg.get("execution_contract_version") == 14 else ACTOR_SYSTEM),
                "complete_public_statutes": statutes,
                "actual_system_and_response_schema_by_public_context": actual_contracts,
                "already_seen_training": cases, "rejected_candidate_feedback": rejected_view,
                "training_evidence_manifest": evidence_manifest,
                "selected_record_view_preserves_program_answer_score_and_error": grounded,
                "bounded_emitted_evidence_contract": {
                    "roles": ["actual_parent_answer", "rejected_candidate_replay"],
                    "reasoning_tail_max_characters": 1024,
                    "failed_native_final_head_tail_max_characters": 512,
                    "unabridged_raw_artifacts_retained": True,
                    "not_a_verified_causal_explanation": True},
                "future_cases_and_labels_not_supplied": True}

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
        old_rows = [r for r in seen if r["case_id"] not in {v["case_id"] for v in current}]
        prior = [self.latest[(r["case_id"], r["family"])] for r in old_rows]
        observations = {**self.latest, **{(r["case_id"], r["family"]): r for r in parent_current}}
        initial_current, initial_prior = copy.deepcopy(parent_current), copy.deepcopy(prior)
        rejected = []
        if closed_loop and self.current_batch > 1:
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
            body = self.teacher_body(current, seen, observations, rejected)
            supplied_ids = body["training_evidence_manifest"]["selected_source_ids"]
            system = DIRECT_AUTHOR_SYSTEM if direct else AUTHOR_SYSTEM + PROGRAM_AUTHOR_ADDITION
            if closed_loop:
                system += CANDIDATE_FEEDBACK_ADDITION
                body["candidate_feedback_contract"] = {
                    "policy": "carry_partial_and_refine", "attempt": attempt,
                    "max_attempts": self.cfg["max_candidate_attempts"],
                    "current_attempt_parent_bank_sha256": csha(before),
                    "previous_publication_only_not_unbounded_history": True,
                    "failure_witness_limit_per_proposal": 8,
                    "single_final_publication_after_bounded_TRAIN_refinement": True}
            delta = self.teacher_call(name, system,
                body,
                differential_schema(FAMILIES, before, supplied_ids,
                                    guidance_schema=guidance_schema))
            candidate = apply_differential_publication(before, delta, FAMILIES,
                supplied_ids, guidance_schema=guidance_schema)
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
                                "source_program_compile_error": repr(exc), "new_native_calls": 0}
                    RunStore.immutable_json(self.out / "candidates" / f"{name}.json", decision)
                    decisions.append(decision)
                    rejected.append(decision)
                    continue
            tokens = self.meter.token_count(text=json.dumps(candidate, ensure_ascii=False,
                                                            separators=(",", ":")))
            if tokens > self.cfg["library_token_hard_cap"]:
                decision = {"accepted": False, "reason": "complete_library_token_cap",
                            "actual_tokens": tokens, "candidate": candidate, "delta": delta}
                RunStore.immutable_json(self.out / "candidates" / f"{name}.json", decision)
                decisions.append(decision)
                rejected.append(decision)
                continue
            if candidate == before:
                decisions.append({"accepted": False, "explicit_noop": True, "delta": delta})
                break
            replay = self.grade(self._dispatch.native(
                lambda r: self.answer(r, candidate, name + "_replay", "candidate"), seen))
            keys = {r["case_id"] for r in current}
            candidate_current = [r for r in replay if r["case_id"] in keys]
            candidate_prior = [r for r in replay if r["case_id"] not in keys]
            full_proposal = acceptance(parent_current, candidate_current, prior, candidate_prior)
            task_decisions = task_admission(parent_current, candidate_current, prior, candidate_prior)
            policy = self.cfg["skill_commit_policy"]
            coordinates, scope_decisions, accepted_coordinates = None, {}, []
            if policy in ("legal_scope", "adaptive_legal"):
                coordinates = legal_edit_coordinates(before, candidate, seen)
                scope_decisions = legal_scope_admission(
                    coordinates, parent_current, candidate_current, prior, candidate_prior)
                accepted_coordinates = [c["id"] for c in coordinates if scope_decisions[c["id"]]["accepted"]]
            accepted_tasks = ([f for f in FAMILIES if task_decisions[f]["accepted"]]
                              if policy == "task_local" else
                              [f for f in FAMILIES if any(c["task"] == f and c["id"] in accepted_coordinates
                                                         for c in coordinates)]
                              if policy in ("legal_scope", "adaptive_legal") else
                              list(FAMILIES) if full_proposal["accepted"] else [])
            decision = {"accepted": False, "candidate": candidate, "delta": delta,
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
                    decision.update(acceptance(parent_current, actual_current, prior, actual_prior))
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
                component_gain = (balanced_replay_gain(parent_replay, decision["actual_replay"])
                                  if decision["accepted"] else None)
                joint_gain = (balanced_replay_gain(parent_replay, replay)
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
                decision["proposal_fully_committed"] = decision["accepted"] and all(
                    task_view(decision["candidate"], f) == task_view(candidate, f) for f in FAMILIES)
                if decision["accepted"]:
                    actual_current = [r for r in decision["actual_replay"] if r["case_id"] in keys]
                    actual_prior = [r for r in decision["actual_replay"] if r["case_id"] not in keys]
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
                if feedback is None:
                    break
                # Keep the accepted subset as the next attempt's real parent.
                # A failed later proposal cannot undo it or use cached scores.
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
            if not acceptance(initial_current, final_current, initial_prior, final_prior)["accepted"]:
                raise ValueError("Final refined bank must also pass the original batch-parent full gate")
        publication = {"at": now(), "bank": self.bank, "parent_bank_sha256": csha(batch_parent),
                       "skill_commit_policy": self.cfg["skill_commit_policy"],
                       "bank_sha256": csha(self.bank), "training_decisions": decisions,
                       "future_performance_not_used": True,
                       "training_acceptance_does_not_guarantee_generalization": True}
        if closed_loop:
            publication["candidate_feedback_policy"] = "carry_partial_and_refine"
        RunStore.immutable_json(self.out / "publications" / f"b{self.current_batch}.json", publication)
        return publication

    def execute(self):
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
