"""Bounded source-disjoint EC/EV skill learning, not a final paper evaluation.

Reuses the audited native/teacher transports and differential edits. Unlike the
old NDA run, training replays can reject ineffective candidate edits. This is
declared TRAIN optimization, not test-time retry or an independent validation
claim. All candidate outputs, costs and rejected edits remain on disk.
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
from pathlib import Path

from jsonschema import validate

from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.inference.native import WireClient
from legal_skill_guard.learning.claim_execution import (
    InvalidClaimProgram,
    execute_claims,
    execute_limit,
    law_blocks,
    operator_catalog,
    operator_schema,
)
from legal_skill_guard.learning.claim_execution import (
    answer_schema as claim_answer_schema,
)
from legal_skill_guard.learning.experiment import Comparison, now, read, sha
from legal_skill_guard.learning.legal_namespace import (
    SCOPES,
    active_bank,
    allowable_namespaces,
    decode_claim_plan,
    decode_classification,
    public_catalog,
    statutory_catalog,
    validate_scopes,
)
from legal_skill_guard.learning.publication import (
    apply_differential_publication,
    differential_schema,
)
from legal_skill_guard.openexempt import (
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

GUIDANCE = {"type": "object", "additionalProperties": False,
            "required": ["when", "procedure", "avoid_when"], "properties": {
                key: {"type": "string", "minLength": 1}
                for key in ("when", "procedure", "avoid_when")}}
EXECUTABLE_GUIDANCE = copy.deepcopy(GUIDANCE)
EXECUTABLE_GUIDANCE["required"].append("operators")
EXECUTABLE_GUIDANCE["properties"]["operators"] = {
    "type": "array", "items": operator_schema()}
EXECUTABLE_GUIDANCE["required"].append("jurisdiction")
EXECUTABLE_GUIDANCE["properties"]["jurisdiction"] = {
    "type": "string", "enum": list(SCOPES)}
ACTOR_SYSTEM = (
    "Apply only the supplied statutes and public solved steps to the original facts. "
    "Return a JSON object mapping actual asset descriptions to ALL applicable public "
    "citation label IDs from the supplied vocabulary, or [] if none. A label is only "
    "the predeclared encoding of its displayed citation; decide legal eligibility yourself."
)
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
    "operations and legal conditions the executor can perform. Explain a generic "
    "calculation using variables where useful, never a current-case answer. Do not "
    "request private chain of thought or invent a successful trajectory. "
    "Rules here concern the supplied benchmark statute version, not current legal advice. "
    "Each skill has when/procedure/avoid_when and public family scope EC and/or EV. "
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
    "The full skill library must fit4096 actual target model tokens; aim2500. "
    "Candidate edits are replayed with the SAME frozen executor. TRAIN acceptance "
    "requires current-source original mean F1 OR full-output EV F1 improvement without "
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
    "answers. This replaces only FINAL ANSWER formatting. Submit only the assets JSON, "
    "without explanation or skill-use self-report. For each asset supply its original "
    "asset_name and numeric asset_value from Facts. Do not copy a format example, a law ceiling, "
    "or another asset's value. No long quotation is required. Select EVERY applicable "
    "public citation label, not just one. Each displayed label encodes one exact public "
    "statutory citation in the given allowable legal framework. For each "
    "claim supply citation_ref and limit_expression only. A string is your inline ceiling "
    "expression. JSON null explicitly invokes the ONE published routine bound to that "
    "same citation. Do not choose or output an internal operator ID. If that law has no "
    "published routine, write its expression yourself; null then is an invalid call. "
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
    "active routine per citation in the whole bank, combining N-dependent variants or "
    "leaving uncommon variants to inline calculation. A native null limit_expression "
    "invokes that same citation's routine; an expression string is inline. There is no "
    "separate operator-ID selection task. Write reusable statutory CEILING expressions, never "
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
    return [copy.deepcopy(s) for s in bank if family in s["hypothesis_ids"]]


def actor_payload(row, bank, *, grounded=True):
    if not grounded:
        raise ValueError("Only the public-namespace claim contract is implemented")
    supplied = visible(active_bank(row, bank), row["family"])
    if row["family"] == "EC":
        # Keep all classification guidance, but EV-only executable bodies are
        # not actions in the original EC output contract.
        for skill in supplied:
            skill["guidance"].pop("operators", None)
    system = PROGRAM_ACTOR_SYSTEM if row["family"] == "EV" else ACTOR_SYSTEM
    messages = [{"role": "system", "content": system}]
    if supplied:
        messages.append({"role": "user", "content":
                         "Background reusable skills. The current legal case follows. "
                         "Use these only when applicable; they are not current answers:\n" +
                         json.dumps(supplied, ensure_ascii=False, separators=(",", ":"))})
    catalog = public_catalog(row)
    messages.append({"role": "user", "content":
        "Public citation label vocabulary. These are public headers in the already-given "
        "allowable jurisdictions, NOT an asset-eligibility answer:\n" +
        json.dumps(catalog, ensure_ascii=False, separators=(",", ":")) +
        "\n\n" + active_case_input(row)})
    labels = {"type": "string", "enum": list(catalog)}
    if row["family"] == "EV":
        schema = claim_answer_schema(supplied)
        claim = schema["properties"]["assets"]["items"]["properties"]["claims"]["items"]
        claim["properties"].pop("citation")
        claim["properties"]["citation_ref"] = labels
        claim["required"] = ["citation_ref", "limit_expression"]
    else:
        schema = answer_schema("EC")
        schema["additionalProperties"]["items"] = labels
    return messages, schema, supplied


def acceptance(parent_current, candidate_current, parent_prior, candidate_prior):
    a, b = metrics(parent_current), metrics(candidate_current)
    pa, pb = metrics(parent_prior), metrics(candidate_prior)
    current_ok = all(b[f]["f1"] + 1e-12 >= a[f]["f1"] for f in FAMILIES)
    prior_ok = not parent_prior or all(pb[f]["f1"] + 1e-12 >= pa[f]["f1"] for f in FAMILIES)
    current_full_ok = b["EV"]["full_output_f1"] + 1e-12 >= a["EV"]["full_output_f1"]
    prior_full_ok = not parent_prior or pb["EV"]["full_output_f1"] + 1e-12 >= pa["EV"]["full_output_f1"]
    improvement = (b["mean_family_f1"] > a["mean_family_f1"] + 1e-12
                   or b["EV"]["full_output_f1"] > a["EV"]["full_output_f1"] + 1e-12)
    return {"accepted": current_ok and prior_ok and current_full_ok and prior_full_ok and improvement,
            "current_family_nonregression": current_ok,
            "prior_family_nonregression": prior_ok, "strict_current_improvement": improvement,
            "current_full_output_nonregression": current_full_ok,
            "prior_full_output_nonregression": prior_full_ok,
            "parent_current": a, "candidate_current": b,
            "parent_prior": pa, "candidate_prior": pb,
            "TRAIN_optimization_not_independent_validation": True}


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


def freeze(config_path):
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


class Online:
    # Audited transports only; no NDA initialization, scoring or old update logic.
    check = Comparison.check
    call = Comparison.call
    teacher_call = Comparison.teacher_call

    def __init__(self, config_path):
        self.cfg = read(config_path)
        if (self.cfg.get("execution_contract") != "source_grounded_claim_operations"
                or self.cfg.get("execution_contract_version") != 8):
            raise ValueError("This source implements explicit public-namespace contract v8 only")
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
        self.bank, self.latest, self.summaries = [], {}, []
        if self.cfg.get("initial_library_publication"):
            initial = read(ROOT / self.cfg["initial_library_publication"])["bank"]
            self.bank = copy.deepcopy(initial)
            operator_catalog(self.bank)
            validate_scopes(self.bank, self.rows[0]["components"]["statutes"])
            if self.bank != initial:
                raise ValueError("Initialization changed historical knowledge")
        self.frozen_bank = copy.deepcopy(self.bank)
        self.prequential_empty, self.prequential_skills, self.prequential_frozen = [], [], []
        self.meter = WireClient(self.cfg["generation"])
        self.out.mkdir(parents=True)
        RunStore.immutable_json(self.out / "initialization.json", {
            "bank": self.bank, "parent_publication": self.cfg.get("initial_library_publication"),
            "initial_library_kind": self.cfg.get("initial_library_kind"),
            "initial_case_exposure": self.cfg.get("initial_library_prior_exposure_distinct_sources", 0),
            "all_episode_labels_unseen_before_this_run": self.cfg.get("all_episode_labels_unseen_before_this_run", False),
            "prior_stateless_queries_without_label_feedback": self.cfg.get("prior_stateless_queries_without_label_feedback", []),
            "input_contract": self.cfg.get("input_contract")})
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, lambda *_: setattr(self, "stop", True))
        self.check()
        if not self.meter.readiness()["ready"]:
            raise RuntimeError("Existing frozen 8B service unavailable")
        self.progress("initialized")

    def progress(self, stage, **extra):
        RunStore.atomic_json(self.out / "progress.json", {
            "at": now(), "run_id": self.run_id, "state": "running", "stage": stage,
            "current_batch": self.current_batch, "completed_native_calls": len(self.native),
            "completed_teacher_calls": len(self.teachers), "teacher_attempts": self.teacher_attempts,
            "cross_stage_identical_wire_reuses": len(self.reuse_events),
            "library_records": len(self.bank), **extra})

    def answer(self, row, bank, stage, arm):
        self.check()
        grounded = self.cfg.get("execution_contract") == "source_grounded_claim_operations"
        messages, schema, supplied = actor_payload(row, bank, grounded=grounded)
        catalog = public_catalog(row)
        fingerprint = csha({"messages": messages, "schema": schema,
                            "generation": self.cfg["generation"]})
        path = self.out / "native" / stage / f"{row['case_id']}_{row['family']}_{arm}.json"
        RunStore.immutable_json(path.with_suffix(".input.json"), {
            "messages": messages, "schema": schema, "bank_sha256": csha(bank),
            "delivered_skill_ids": [s["id"] for s in supplied],
            "original_prompt_sha256": csha(row["prompt"]),
            "actual_active_case_input_sha256": csha(active_case_input(row)),
            "public_citation_catalog": catalog,
            "public_allowable_jurisdictions": sorted(allowable_namespaces(row)),
            "public_citation_catalog_sha256": csha(catalog),
            "format_only_demonstrations_not_in_inference_input": True,
            "no_private_case_annotations_or_current_target": True})
        if fingerprint in self.request_cache:
            original = self.request_cache[fingerprint]
            result = {**copy.deepcopy(original), "case_id": row["case_id"],
                      "source_key": row["source_key"], "family": row["family"],
                      "stage": stage, "arm": arm, "bank_sha256": csha(bank),
                      "delivered_skill_ids": [s["id"] for s in supplied],
                      "physical_alias_of_identical_wire": {"fingerprint": fingerprint,
                          "raw_call_path": original["raw_call_path"],
                          "not_an_independent_generation": True,
                          "execution_receipt_is_from_original_call": True}}
            result.pop("score", None)  # Never cache or propagate reference feedback.
            self.reuse_events.append({"stage": stage, "case_id": row["case_id"],
                "family": row["family"], "arm": arm, "fingerprint": fingerprint,
                "raw_call_path": original["raw_call_path"]})
            RunStore.immutable_json(path.with_suffix(".answer.json"), result)
            self.progress(stage, current_arm=arm, current_document_id=row["case_id"],
                          current_call="identical_wire_reuse_not_new_generation")
            return result
        response = self.call(path, messages, schema, self.cfg["generation"]["max_tokens"], {
            "stage": stage, "arm": arm, "document_id": row["case_id"],
            "family": row["family"], "call_role": "openexempt", "bank_sha256": csha(bank)})
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
        native_program, execution_receipt, execution_error = None, None, None
        if grounded and row["family"] == "EV" and parse_error is None:
            native_program = decode_claim_plan(parsed, catalog)
            try:
                answer, execution_receipt = execute_claims(native_program["assets"],
                    row["components"]["facts"], row["components"]["statutes"], supplied)
                parsed = {"answer": answer}
            except InvalidClaimProgram as exc:
                execution_error = repr(exc)
                parse_error = "Invalid explicitly submitted action: " + execution_error
        elif parse_error is None:
            # Original root task answer; this wrapper is internal storage only,
            # not an additional model-generated explanation or second answer.
            parsed = {"answer": decode_classification(parsed, catalog)}
        result = {"case_id": row["case_id"], "source_key": row["source_key"],
                  "family": row["family"], "stage": stage, "arm": arm,
                  "bank_sha256": csha(bank), "parsed": parsed,
                  "parse_error": parse_error, "raw_call_path": str(path.relative_to(ROOT)),
                  "native_program": native_program, "execution_receipt": execution_receipt,
                  "public_label_submission": public_label_submission,
                  "execution_error": execution_error,
                  "delivered_skill_ids": [s["id"] for s in supplied]}
        RunStore.immutable_json(path.with_suffix(".answer.json"), result)
        self.request_cache[fingerprint] = copy.deepcopy(result)
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
        statutes = {csha(r["components"]["statutes"]): r["components"]["statutes"] for r in seen}
        # Task text is retained exactly, but the long public law corpus appears once.
        contracts = {r["family"]: {k: r["components"][k] for k in
                     ("instruction", "meta_instruction")}
                     for r in seen}
        grounded = self.cfg.get("execution_contract") == "source_grounded_claim_operations"

        def observation_view(record):
            if not grounded:
                return record
            receipt = record.get("execution_receipt")
            return {"case_id": record["case_id"], "family": record["family"],
                    "native_program": record.get("native_program"),
                    "physical_alias_of_identical_wire": record.get("physical_alias_of_identical_wire"),
                    "executed_answer": (record.get("parsed") or {}).get("answer"),
                    "parse_error": record["parse_error"], "execution_error": record.get("execution_error"),
                    "score": record["score"], "actual_operations": None if receipt is None else [
                        {k: op[k] for k in ("asset_name", "asset_value", "citation", "operator_id",
                                           "limit", "claim_value")}
                        for op in receipt["actual_claim_operations"]]}

        cases = []
        empty_by_key = {(r["case_id"], r["family"]): r for r in self.prequential_empty}
        frozen_by_key = {(r["case_id"], r["family"]): r for r in self.prequential_frozen}
        for row in seen:
            target = read(ROOT / self.cfg["grading_directory"] /
                          f"{row['case_id']}.json")["targets"][row["family"]]
            cases.append({"source_case_id": row["case_id"], "family": row["family"],
                          "facts": row["components"]["facts"],
                          "public_solved_steps": row["components"]["solved_steps"],
                          "public_statutes_ref": csha(row["components"]["statutes"]),
                          "original_training_target": target,
                          "actual_same_case_empty_answer": observation_view(
                              empty_by_key[(row["case_id"], row["family"])]),
                          "actual_same_case_frozen_initial_answer": observation_view(
                              frozen_by_key[(row["case_id"], row["family"])]),
                          "actual_parent_answer": observation_view(
                              observations[(row["case_id"], row["family"])])})
        rejected_view = []
        for decision in rejected:
            value = {k: v for k, v in decision.items() if k != "actual_replay"}
            if "actual_replay" in decision:
                value["actual_replay"] = [observation_view(r) for r in decision["actual_replay"]]
            rejected_view.append(value)
        actual_contracts = {}
        for row in seen:
            key = "+".join(sorted(allowable_namespaces(row)))
            group = actual_contracts.setdefault(key, {})
            if row["family"] not in group:
                messages, schema, _ = actor_payload(row, self.bank, grounded=True)
                group[row["family"]] = {"system": messages[0]["content"],
                                        "response_schema": schema}
        return {"current_source_case_ids": sorted({r["case_id"] for r in current}),
                "task_boundary": {"start_task_id": 2,
                    "public_prior": "allowable jurisdictions already supplied; do not recompute them",
                    "outputs": "all eligible asset-law alternatives, not a final jointly allocated portfolio"},
                "current_parent_library": self.bank, "task_contracts": contracts,
                "public_citation_label_catalog": statutory_catalog(seen[0]["components"]["statutes"]),
                "actual_actor_system": ACTOR_SYSTEM, "complete_public_statutes": statutes,
                "actual_system_and_response_schema_by_public_context": actual_contracts,
                "already_seen_training": cases, "rejected_candidate_feedback": rejected_view,
                "program_and_result_view_omits_only_duplicate_CPU_trace_provenance": grounded,
                "future_cases_and_labels_not_supplied": True}

    def update(self, current, seen, parent_current):
        before = copy.deepcopy(self.bank)
        old_rows = [r for r in seen if r["case_id"] not in {v["case_id"] for v in current}]
        prior = [self.latest[(r["case_id"], r["family"])] for r in old_rows]
        observations = {**self.latest, **{(r["case_id"], r["family"]): r for r in parent_current}}
        rejected = []
        decisions = []
        grounded = self.cfg.get("execution_contract") == "source_grounded_claim_operations"
        guidance_schema = EXECUTABLE_GUIDANCE if grounded else GUIDANCE
        for attempt in range(1, self.cfg["max_candidate_attempts"] + 1):
            name = f"b{self.current_batch}_candidate{attempt}"
            delta = self.teacher_call(name, AUTHOR_SYSTEM + (PROGRAM_AUTHOR_ADDITION if grounded else ""),
                self.teacher_body(current, seen, observations, rejected),
                differential_schema(FAMILIES, before, sorted({r["case_id"] for r in seen}),
                                    guidance_schema=guidance_schema))
            candidate = apply_differential_publication(before, delta, FAMILIES,
                sorted({r["case_id"] for r in seen}), guidance_schema=guidance_schema)
            if grounded:
                try:
                    validate_scopes(candidate, current[0]["components"]["statutes"])
                    for skill in candidate:
                        if skill["guidance"]["operators"] and "EV" not in skill["hypothesis_ids"]:
                            raise InvalidClaimProgram("Claim operators require public EV scope")
                    for operator in operator_catalog(candidate).values():
                        # Compile/run pure source arithmetic, not a model qualification loop.
                        for source in current:
                            if operator["citation"] not in law_blocks(source["components"]["statutes"]):
                                raise InvalidClaimProgram("Operator citation is not a current public header")
                            execute_limit(operator["limit_expression"], source["components"]["facts"])
                except InvalidClaimProgram as exc:
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
            replay = self.grade([self.answer(r, candidate, name + "_replay", "candidate") for r in seen])
            keys = {r["case_id"] for r in current}
            candidate_current = [r for r in replay if r["case_id"] in keys]
            candidate_prior = [r for r in replay if r["case_id"] not in keys]
            decision = {**acceptance(parent_current, candidate_current, prior, candidate_prior),
                        "candidate": candidate, "delta": delta, "actual_tokens": tokens,
                        "current_effect": paired_effect(parent_current, candidate_current),
                        "prior_effect": paired_effect(prior, candidate_prior),
                        "actual_replay": replay}
            RunStore.immutable_json(self.out / "candidates" / f"{name}.json", decision)
            decisions.append(decision)
            if decision["accepted"]:
                self.bank = candidate
                self.latest = {(r["case_id"], r["family"]): r for r in replay}
                break
            rejected.append(decision)
        if self.bank == before:
            self.latest = observations
        publication = {"at": now(), "bank": self.bank, "parent_bank_sha256": csha(before),
                       "bank_sha256": csha(self.bank), "training_decisions": decisions,
                       "future_performance_not_used": True,
                       "training_acceptance_does_not_guarantee_generalization": True}
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
            empty, skills, frozen = [], [], []
            native_before = len(self.native)
            for row in current:
                # Fixed rotation, and exact-wire sharing only. No quality selection.
                arms = ("empty", "frozen_initial", "skills")
                offset = (row["case_id"] + FAMILIES[row["family"]]) % len(arms)
                arms = arms[offset:] + arms[:offset]
                answers, executed = {}, {}
                for arm in arms:
                    bank = self.bank if arm == "skills" else self.frozen_bank if arm == "frozen_initial" else []
                    messages, schema, _ = actor_payload(row, bank, grounded=True)
                    fingerprint = csha({"messages": messages, "schema": schema,
                                        "generation": self.cfg["generation"]})
                    if fingerprint in executed:
                        original = executed[fingerprint]
                        answers[arm] = {**copy.deepcopy(original), "arm": arm,
                            "bank_sha256": csha(bank),
                            "physical_alias_of_identical_wire": {"fingerprint": fingerprint,
                                "raw_call_path": original["raw_call_path"],
                                "not_an_independent_generation": True}}
                    else:
                        answers[arm] = self.answer(row, bank, f"b{batch}_prequential", arm)
                        executed[fingerprint] = answers[arm]
                empty.append(answers["empty"])
                skills.append(answers["skills"])
                frozen.append(answers["frozen_initial"])
            # Current labels are first read only after ALL current arms exist.
            self.grade(empty + skills + frozen)
            RunStore.immutable_json(self.out / "batches" / f"b{batch}_prequential_records.json",
                                    {"empty": empty, "skills": skills, "frozen_initial": frozen})
            self.prequential_empty.extend(empty)
            self.prequential_skills.extend(skills)
            self.prequential_frozen.extend(frozen)
            pre = {"batch": batch, "source_cases": batch_size, "tasks_per_arm": len(current),
                   "empty": metrics(empty), "skills": metrics(skills), "frozen_initial": metrics(frozen),
                   "effect": paired_effect(empty, skills), "parent_bank_sha256": csha(self.bank),
                   "online_minus_frozen": paired_effect(frozen, skills),
                   "prequential_actual_new_native_calls": len(self.native) - native_before,
                   "parent_skill_count": len(self.bank), "official_test_opened": False}
            RunStore.immutable_json(self.out / "batches" / f"b{batch}_prequential.json", pre)
            self.progress("prequential_scored", latest_batch=pre)
            publication = self.update(current, seen, skills)
            pre["resulting_bank_sha256"] = publication["bank_sha256"]
            pre["resulting_skill_count"] = len(self.bank)
            pre["accepted_update"] = publication["parent_bank_sha256"] != publication["bank_sha256"]
            self.summaries.append(pre)
            RunStore.atomic_json(self.out / "batch_summary.json", self.summaries)
            self.progress("batch_complete", latest_batch=pre)
            # A fixed falsification stop, not a choice of an earlier winning bank.
            recent = self.summaries[-2:]
            if len(recent) == 2 and all(r["parent_skill_count"] and
                    (r["effect"]["mean_f1_difference"] < -0.02
                     or r["online_minus_frozen"]["mean_f1_difference"] < -0.02
                     or r["skills"]["EV"]["full_output_f1"]
                        < r["frozen_initial"]["EV"]["full_output_f1"] - 0.02) for r in recent):
                return "stopped_repeated_forward_harm"
        return "completed_bounded_mechanism_study"

    def run(self):
        status = "failed"
        try:
            status = self.execute()
            completion = {"at": now(), "run_id": self.run_id, "status": status,
                          "batch_summary": self.summaries, "bank": self.bank,
                          "prequential_empty": metrics(self.prequential_empty),
                          "prequential_skills": metrics(self.prequential_skills),
                          "prequential_frozen_initial": metrics(self.prequential_frozen),
                          "paired": paired_effect(self.prequential_empty, self.prequential_skills),
                          "online_minus_frozen": paired_effect(self.prequential_frozen, self.prequential_skills),
                          "actual_native_calls": len(self.native),
                          "actual_teacher_responses": len(self.teachers),
                          "actual_teacher_attempts": self.teacher_attempts,
                          "cross_stage_identical_wire_reuses": self.reuse_events,
                          "native_prompt_tokens": sum(v["response"]["prompt_tokens"] for v in self.native if v["response"]),
                          "native_completion_tokens": sum(v["response"]["completion_tokens"] for v in self.native if v["response"]),
                          "no_official_test_or_paper_success_claim": True}
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
    parser.add_argument("action", choices=("prepare", "run"))
    parser.add_argument("config", type=Path)
    args = parser.parse_args()
    config_path = args.config.resolve()
    if args.action == "prepare":
        receipt = prepare(read(config_path))
        frozen = freeze(config_path)
        print(json.dumps({"prepared": receipt, "bound_files": len(frozen["files"])}))
    else:
        with (ROOT / "artifacts/openexempt_training.lock").open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            Online(config_path).run()


if __name__ == "__main__":
    main()
