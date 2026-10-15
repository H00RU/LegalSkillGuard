"""Finite source-disjoint learning comparison, not official confirmation.

The only new solver intervention is frozen public-scope execution of published
queries. ACE keeps native ADD and counter helpers under Apache-2.0; its common
legal output and no-oracle-retry adaptations are explicitly declared. No judge,
best-bank selection, answer rewriting, fallback, or additional model is used.
"""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import os
import signal
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from jsonschema import validate

from legal_skill_guard.experiment.storage import RunStore, safe_component
from legal_skill_guard.inference.codex_cli_client import (
    CODEX_TURN_INPUT_CHARACTER_LIMIT,
    CodexCLIClient,
    render_structured_codex_prompt,
    run_process_tree,
)
from legal_skill_guard.inference.native import WireClient
from legal_skill_guard.inference.openai_client import GenerationConfig
from legal_skill_guard.report import write_report
from legal_skill_guard.task import (
    marked_text,
    original_feedback,
    original_metrics,
    render_library,
    solver_messages,
)
from legal_skill_guard.utils.hashing import canonical_json_sha256

from .ace_native import (
    apply_curator_operations,
    get_next_global_id,
    get_playbook_stats,
    parse_playbook_line,
    update_bullet_counts,
)
from .audit import close, original_score
from .catalog import decode_teacher_body, encode_teacher_body
from .encoding import lean_final_messages
from .interface import (
    QUERY_API_SYSTEM,
    TEACHER_SYSTEM,
    callable_skill_schema,
    compact_receipts,
    execute_plan,
    final_messages,
    publication_schema,
    publish,
    validate_queries,
)
from .packing import LEGEND, pack_cases
from .publication import paired

ROOT = Path(__file__).resolve().parents[2]


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def now():
    return datetime.now(UTC).isoformat()


LEARNERS = ("experience", "source_only", "ace_legal")


FINAL_ARMS = ("strong_empty", "empty_receipts", "static", *LEARNERS)


ENDPOINTS = (
    "label_accuracy",
    "evidence_micro_f1_gold_non_neutral",
    "evidence_query_mean_f1_gold_non_neutral",
    "joint_exact_accuracy",
)


ACE_SECTIONS = (
    "STRATEGIES & INSIGHTS",
    "FORMULAS & CALCULATIONS",
    "CODE SNIPPETS & TEMPLATES",
    "COMMON MISTAKES TO AVOID",
    "PROBLEM-SOLVING HEURISTICS",
    "CONTEXT CLUES & INDICATORS",
    "OTHERS",
)


INITIAL_PLAYBOOK = "\n\n".join("## " + s for s in ACE_SECTIONS)


def author_constant(filename, name):
    path = ROOT / "third_party/ace/prompts" / filename
    for node in ast.parse(path.read_text()).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == name for t in node.targets
        ):
            return ast.literal_eval(node.value)
    raise ValueError("Missing pinned author prompt constant: " + name)


GENERATOR_PROMPT = author_constant("generator.py", "GENERATOR_PROMPT")


REFLECTOR_PROMPT = author_constant("reflector.py", "REFLECTOR_PROMPT")


CURATOR_PROMPT = author_constant("curator.py", "CURATOR_PROMPT")


def bullets(playbook):
    return {b["id"]: b for line in playbook.splitlines() if (b := parse_playbook_line(line))}


def scope_plan(labels, bank):
    return {
        key: {
            "skill_ids": [s["id"] for s in bank if key in s["hypothesis_ids"]],
            "generic_queries": [],
        }
        for key in labels
    }


def points(units):
    value = original_metrics(units)
    value["joint_exact_accuracy"] = value["joint_exact_correct"] / value["hypotheses"]
    return value


class Comparison:
    def check(self):
        if self.stop:
            raise InterruptedError("Operator stop at artifact-safe boundary")
        for path, digest in self.bindings.items():
            if sha(path) != digest:
                raise ValueError("Frozen source/input changed: " + path)
        env = read(ROOT / self.cfg["inference_environment"])
        p = Path("/proc") / str(env["pid"]) / "cmdline"
        observed = [v.decode() for v in p.read_bytes().split(b"\0") if v] if p.is_file() else []
        if observed != env["actual_argv"]:
            raise RuntimeError("Frozen 8B service changed; no fallback")
        if (p.parent / "stat").read_text().rsplit(")", 1)[1].split()[19] != env[
            "process_start_ticks"
        ]:
            raise RuntimeError("Frozen model process was replaced; no fallback")

    def call(self, dest, messages, schema, max_tokens, metadata):
        self.check()
        generation = self.cfg["generation"]
        client = WireClient(generation)
        tokens = client.token_count(messages=messages)
        if tokens + max_tokens > generation["context_tokens"]:
            raise ValueError("Full original input exceeds frozen capacity; never clip")
        response = None
        error = None
        self.progress(
            metadata["stage"],
            current_arm=metadata["arm"],
            current_document_id=metadata["document_id"],
            current_call=metadata["call_role"],
        )
        try:
            response = asdict(
                client.generate(
                    messages,
                    GenerationConfig(
                        temperature=generation["temperature"],
                        top_p=generation["top_p"],
                        top_k=generation["top_k"],
                        max_tokens=max_tokens,
                        seed=generation["seed"],
                        disable_thinking=False,
                        response_schema=schema,
                        response_schema_name="contractnli_callable_" + metadata["call_role"],
                    ),
                )
            )
        except Exception as exc:
            error = repr(exc)
        record = {
            "calls": client.native,
            "response": response,
            "transport_error": error,
            "prompt_tokens_server": tokens,
            "token_count_source": "same_live_vllm_tokenizer_not_generation",
            **metadata,
        }
        RunStore.immutable_json(dest, record)
        if client.native:
            self.native.append(record)
        if error:
            raise RuntimeError("Native failure retained, no retry: " + error)
        if len(client.native) != 1 or response is None:
            raise ValueError("Exactly one actual native call required")
        wire = client.native[0]["response"]
        if (
            wire["id"] != response["raw_id"]
            or wire["usage"]["prompt_tokens"] != tokens
            or (wire["choices"][0]["message"].get("content") or "").strip() != response["content"]
        ):
            raise ValueError("Native identity/content/token-count mismatch")
        return response

    # Reuse only the audited native call, model identity and progress primitives.
    # No legacy initialization, routing, learner, resume, or delivery is inherited.
    def __init__(self, config_path, *, run_id=None):
        self.config_path = Path(config_path).resolve()
        self.cfg = read(self.config_path)
        self.run_id = safe_component(run_id or self.cfg["run_id"])
        self.out = ROOT / "runs" / self.run_id
        self.report = ROOT / self.cfg["report_directory"] / self.run_id
        if self.out.exists():
            raise FileExistsError("New Run ID required; never overwrite or retry")
        frozen = read(self.config_path.with_suffix(".frozen.json"))
        if frozen["config_sha256"] != sha(self.config_path):
            raise ValueError("Frozen configuration differs")
        self.bindings = frozen["files"]
        self.meter = WireClient(self.cfg["generation"])
        packet = read(ROOT / self.cfg["input_packet"])
        self.labels, self.training = packet["public_hypotheses"], packet["training"]
        self.future, self.groups = (
            packet["development_inputs_no_annotation_sets"],
            packet["development_component_groups"],
        )
        assert len(self.labels) == 17 and len(self.training) == 32 and len(self.future) == 24
        assert {r["batch"] for r in self.training} == set(range(1, 9))
        assert len({r["id"] for r in self.training + self.future}) == 56
        assert all("annotation_sets" not in r for r in self.future)
        self.banks = {"experience": [], "source_only": [], "ace_legal": INITIAL_PLAYBOOK}
        self.static = []
        self.before, self.after = {a: {} for a in LEARNERS}, {a: {} for a in LEARNERS}
        self.versions = {canonical_json_sha256([]): []}
        self.native, self.units, self.teachers = [], [], []
        self.teacher_attempts, self.current_batch, self.stop = 0, 0, False
        self.summaries, self.retention = [], []
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, lambda *_: setattr(self, "stop", True))

    def progress(self, stage, **extra):
        extra.setdefault("current_batch", self.current_batch)
        RunStore.atomic_json(
            self.out / "progress.json",
            {
                "at": now(),
                "run_id": self.run_id,
                "state": "running",
                "stage": stage,
                "completed_native_calls": len(self.native),
                "planned_native_calls": self.cfg["planned_new_native_calls"],
                "completed_teacher_calls": len(self.teachers),
                "teacher_attempts": self.teacher_attempts,
                **extra,
            },
        )

    def messages(self, arm, row, bank):
        if arm == "ace_legal":
            ids = [{"id": key} for key in bullets(bank)]
            messages, schema = solver_messages(
                row, self.labels, ids, self.cfg["bundled_solver_system"]
            )
            # Preserve full native bullet text/counters/order, once. Adapt only
            # the task's native answer/used-ID fields to the common 17-item schema.
            prefix = GENERATOR_PROMPT.split("Your output should be a json object", 1)[0]
            messages[0]["content"] += (
                "\n"
                + prefix
                + (
                    "\nFor this legal task use the supplied common output_contract, "
                    "not ACE final_answer/reasoning/bullet_ids wrapper fields. "
                    "Report relevant native bullet IDs per hypothesis in used_skill_ids; "
                    "reason is a short public rationale, not private thinking. "
                    "Reflection is empty: no current gold or current-case correction is provided."
                )
            )
            body = json.loads(messages[1]["content"])
            body.update(
                {
                    "original_public_short_descriptions": {
                        k: v["short_description"] for k, v in self.labels.items()
                    },
                    "ACE_playbook_verbatim": bank,
                    "ACE_current_case_reflection": "(empty)",
                }
            )
            messages[1]["content"] = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
            return messages, schema, None, None
        trace = plan = None
        if arm != "strong_empty":
            plan = scope_plan(self.labels, bank)
            trace = execute_plan(row, self.labels, bank, plan)
        messages, schema = final_messages(
            row, self.labels, bank, self.cfg["bundled_solver_system"], trace
        )
        if trace is not None:
            messages = lean_final_messages(messages)
        return messages, schema, plan, trace

    def answer(self, stage, arm, row, bank, gold=None):
        messages, schema, plan, trace = self.messages(arm, row, bank)
        destination = self.out / stage / arm / str(row["id"])
        base = {
            "stage": stage,
            "arm": arm,
            "document_id": row["id"],
            "published_library": copy.deepcopy(bank),
            "published_library_sha256": canonical_json_sha256(bank),
            "call_role": "final",
            "no_native_planning_call": True,
        }
        response = self.call(
            destination.with_suffix(".final.native.json"),
            messages,
            schema,
            self.cfg["generation"]["max_tokens"],
            base,
        )
        unit = {
            **base,
            "response": response,
            "plan_response": None,
            "actual_public_plan": plan,
            "actual_factual_trace": trace,
            "plan_native_artifact": None,
            "hypothesis_ids": list(self.labels),
            "raw_artifact": str(destination.with_suffix(".final.native.json")),
            "no_answer_rewrite_or_current_gold_or_legal_host_verdict": True,
        }
        if gold is not None:
            unit.update(original_feedback(response, row, gold, list(self.labels)))
        RunStore.immutable_json(destination.with_suffix(".public.json"), unit)
        self.units.append(unit)
        return unit

    def collect(self, stage, arm, rows, bank):
        return [
            self.answer(stage, arm, r, bank, r["annotation_sets"][0]["annotations"]) for r in rows
        ]

    def teacher_call(self, name, system, body, schema):
        self.check()
        dest = self.out / "teacher" / name
        settings = self.cfg["teacher"]

        def capture(argv, **kwargs):
            value = run_process_tree(argv, **kwargs)
            RunStore.immutable_json(
                dest / "event_log.json",
                {
                    "returncode": value.returncode,
                    "event_log": value.stdout or "",
                    "stderr": value.stderr or "",
                },
            )
            return value

        client = CodexCLIClient(
            model=settings["model"],
            reasoning_effort=settings["reasoning_effort"],
            executable="/usr/bin/codex",
            cache_root=dest / "cache",
            command_runner=capture,
            timeout_seconds=settings["timeout_seconds"],
            retries=0,
            invocation_budget_path=ROOT / settings["ledger"],
            max_invocations=settings["total_invocation_budget"],
            context_window_tokens=872000,
            auto_compact_token_limit=800000,
            max_input_tokens=settings["max_input_tokens"],
        )
        user = (
            body
            if isinstance(body, str)
            else json.dumps(body, ensure_ascii=False, separators=(",", ":"))
        )
        request = {
            "purpose": self.run_id + "_" + name,
            "system_prompt": system,
            "user_prompt": user,
            "output_schema": schema,
        }
        chars = len(render_structured_codex_prompt(system, user))
        if chars > CODEX_TURN_INPUT_CHARACTER_LIMIT:
            raise ValueError("Complete teacher input exceeds character capacity; never truncate")
        RunStore.immutable_json(dest / "wire_request.json", client.request_payload(**request))
        self.teacher_attempts += 1
        self.progress("teacher", current_arm=name, teacher_prompt_characters=chars)
        response = asdict(client.generate_json(**request))
        RunStore.immutable_json(dest / "response.json", response)
        self.teachers.append({"name": name, **response})
        if response["cache_hit"] or response["invocation"].get("tool_events_detected"):
            raise ValueError("Fresh existing teacher without tools required")
        validate(response["value"], schema)
        return response["value"]

    def validate_bank(self, arm, bank):
        if arm == "ace_legal":
            if len(bullets(bank)) != sum(
                parse_playbook_line(line) is not None for line in bank.splitlines()
            ):
                raise ValueError("Duplicate native ACE bullet IDs; no repair")
            rendered = bank
        else:
            if len({s["id"] for s in bank}) != len(bank):
                raise ValueError("Duplicate published IDs")
            for skill in bank:
                validate(skill, callable_skill_schema(self.labels))
                if len(skill["hypothesis_ids"]) != len(set(skill["hypothesis_ids"])):
                    raise ValueError("Duplicate public scope")
                validate_queries(skill["queries"])
            rendered = render_library(bank)
        count = self.meter.token_count(text=rendered)
        if count > self.cfg["library_token_hard_cap"]:
            raise ValueError("Complete library exceeds capacity; never truncate or choose old bank")
        return count

    def observation(self, unit):
        return {
            "stage": unit["stage"],
            "public_valid": unit["public_valid"],
            "public_error": unit["public_error"],
            "parsed_public_answer": unit["parsed"],
            "unparsed_public_content": unit["response"]["content"]
            if not unit["public_valid"]
            else None,
            "actual_plan": unit["actual_public_plan"],
            "actual_factual_trace": compact_receipts(unit["actual_factual_trace"]),
            "policy_version_sha256": unit["published_library_sha256"],
            "original_component_feedback": [
                {k: v for k, v in q.items() if k not in ("gold", "prediction")}
                for q in unit["queries"]
            ],
            "raw_id": unit["response"]["raw_id"],
            "plan_raw_id": None,
            "raw_artifact": unit["raw_artifact"],
            "plan_native_artifact": None,
        }

    def update_callable(self, arm, batch):
        parent = self.banks[arm]
        seen = [r for r in self.training if r["batch"] <= batch]
        cases, historical = [], set()
        for row in seen:
            before = (
                [self.observation(u) for u in self.before[arm][row["id"]]]
                if arm == "experience"
                else []
            )
            after = (
                [self.observation(u) for u in self.after[arm].get(row["id"], [])]
                if arm == "experience"
                else []
            )
            historical.update(o["policy_version_sha256"] for o in before + after)
            cases.append(
                {
                    "document_id": row["id"],
                    "original_full_contract_with_spans": marked_text(row),
                    "original_annotations": row["annotation_sets"][0]["annotations"],
                    "actual_before_publication_observations": before,
                    "actual_prior_post_publication_observations": after,
                }
            )
        original = {
            "arm_information_boundary": (
                "Same cumulative seen source/Gold plus own actual public traces only"
                if arm == "experience"
                else "Same cumulative seen source/Gold only; no solver output, metrics or trajectories"
            ),
            "original_public_hypotheses": self.labels,
            "complete_actual_parent_library": parent,
            "all_seen_train_cases": pack_cases(cases),
            "actual_historical_policy_versions": {h: self.versions[h] for h in sorted(historical)},
            "lossless_teacher_encoding": LEGEND,
            "solver_delivery_contract": "Only public hypothesis scope selects all stored queries. There is no lawyer planning call or generic query. Full source remains present; receipts never decide relevance or labels.",
            "full_serialized_library_token_cap": self.cfg["library_token_hard_cap"],
        }
        body = encode_teacher_body(original)
        decoded = decode_teacher_body(body)
        assert decoded["all_seen_train_cases"] == cases
        assert (
            decoded["actual_historical_policy_versions"]
            == original["actual_historical_policy_versions"]
        )
        system = TEACHER_SYSTEM + (
            " The actual solver executes all applicable published queries by their public scope, then answers once. "
            "There is no autonomous action-selection stage to diagnose in this run. "
            "Respect the supplied full serialized library token cap; do not fill it unnecessarily."
        )
        schema = publication_schema(self.labels, parent, [r["id"] for r in seen])
        value = self.teacher_call(f"{arm}_b{batch}", system, body, schema)
        bank = publish(parent, value, self.labels, [r["id"] for r in seen])
        count = self.validate_bank(arm, bank)
        RunStore.immutable_json(
            self.out / "update_transactions" / f"{arm}_b{batch}.json",
            {
                "at": now(),
                "arm": arm,
                "batch": batch,
                "actual_parent": parent,
                "actual_teacher_value": value,
                "publication": bank,
                "library_tokens": count,
                "parent_sha256": canonical_json_sha256(parent),
                "publication_sha256": canonical_json_sha256(bank),
                "complete_seen_source_gold_own_history_roundtrip": True,
                "source_case_ids": [r["id"] for r in seen],
                "source_only_contains_no_solver_observations": arm == "source_only",
                "future_retention_other_arms_and_private_thinking_excluded": True,
                "no_effect_admission_rollback_or_mandatory_growth": True,
            },
        )
        self.versions[canonical_json_sha256(bank)] = copy.deepcopy(bank)
        return bank

    def update_ace(self, batch):
        parent = self.banks["ace_legal"]
        rows = [r for r in self.training if r["batch"] == batch]
        reflections, tags = [], []
        known = bullets(parent)
        for row in rows:
            unit = self.before["ace_legal"][row["id"]][0]
            cited = sorted(
                {
                    sid
                    for q in (unit["parsed"] or {}).values()
                    for sid in q.get("used_skill_ids", [])
                }
            )
            if not set(cited) <= set(known):
                raise ValueError("Unknown native ACE bullet citation")
            tag_schema = {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["id", "tag"],
                    "properties": {
                        "id": {"type": "string"},
                        "tag": {"type": "string", "enum": ["helpful", "harmful", "neutral"]},
                    },
                },
            }
            # Structured Outputs cannot express uniqueItems. The exact cited
            # ID set and uniqueness remain mandatory in the host check below.
            tag_schema.update(minItems=len(cited), maxItems=len(cited))
            if cited:
                tag_schema["items"]["properties"]["id"]["enum"] = cited
            else:
                tag_schema["maxItems"] = 0
            fields = (
                "reasoning",
                "error_identification",
                "root_cause_analysis",
                "correct_approach",
                "key_insight",
            )
            schema = {
                "type": "object",
                "additionalProperties": False,
                "required": [*fields, "bullet_tags"],
                "properties": {
                    **{f: {"type": "string"} for f in fields},
                    "bullet_tags": tag_schema,
                },
            }
            question = json.dumps(
                {"original_hypotheses": self.labels, "full_original_contract": marked_text(row)},
                ensure_ascii=False,
            )
            prompt = REFLECTOR_PROMPT.format(
                question,
                json.dumps(unit["parsed"], ensure_ascii=False),
                unit["response"]["content"],
                json.dumps(row["annotation_sets"][0]["annotations"], ensure_ascii=False),
                json.dumps(unit["queries"], ensure_ascii=False),
                "\n".join(known[s]["raw_line"] for s in cited),
            )
            value = self.teacher_call(
                f"ace_legal_reflector_b{batch}_doc{row['id']}",
                "Use the pinned ACE reflector task below. The trace is the actual public answer only, not hidden reasoning. "
                "Compare both original relations and complete binary evidence. Tag exactly the cited bullets once each. "
                "No tools, future cases or invented solver actions. Return the requested JSON.",
                prompt,
                schema,
            )
            if len({t["id"] for t in value["bullet_tags"]}) != len(value["bullet_tags"]) or set(
                t["id"] for t in value["bullet_tags"]
            ) != set(cited):
                raise ValueError(
                    "ACE reflection must tag exactly its actual cited bullets; no repair"
                )
            reflections.append({"document_id": row["id"], "reflection": value})
            tags.extend(value["bullet_tags"])
        # Native batch semantics: repeated IDs in the same aggregate use the
        # author's last tag, not silently corrected per-document accumulation.
        counted = update_bullet_counts(parent, tags) if tags else parent
        sections = [s.lower().replace(" ", "_").replace("&", "and") for s in ACE_SECTIONS]
        schema = {
            "type": "object",
            "additionalProperties": False,
            "required": ["reasoning", "operations"],
            "properties": {
                "reasoning": {"type": "string"},
                "operations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["type", "section", "content"],
                        "properties": {
                            "type": {"type": "string", "enum": ["ADD"]},
                            "section": {"type": "string", "enum": sections},
                            "content": {"type": "string"},
                        },
                    },
                },
            },
        }
        context = json.dumps(
            [{"full_original_contract": marked_text(r), "hypotheses": self.labels} for r in rows],
            ensure_ascii=False,
        )
        prompt = CURATOR_PROMPT.format(
            token_budget=self.cfg["library_token_hard_cap"],
            current_step=sum(r["batch"] <= batch for r in self.training),
            total_samples=len(self.training),
            playbook_stats=json.dumps(get_playbook_stats(counted)),
            recent_reflection=json.dumps(reflections, ensure_ascii=False),
            current_playbook=counted,
            question_context=context,
        )
        value = self.teacher_call(
            f"ace_legal_curator_b{batch}",
            "Use the pinned ACE ADD-only curator task below. One configured curator group combines the current batch. "
            "The runtime playbook must generalize: do not store document IDs, parties, dates, source indices or per-case answer tables. "
            "Keep each bullet on one line, within the supplied full playbook token cap. No tools or future cases.",
            prompt,
            schema,
        )
        if any(
            "\n" in op["content"] or "\r" in op["content"] or not op["content"].strip()
            for op in value["operations"]
        ):
            raise ValueError("Malformed native ACE single-line addition; no repair")
        bank, next_id = apply_curator_operations(
            counted, value["operations"], get_next_global_id(counted)
        )
        old, new = bullets(counted), bullets(bank)
        if not set(old) <= set(new) or any(old[k]["content"] != new[k]["content"] for k in old):
            raise ValueError("ACE ADD modified prior native bullet content")
        if len(new) - len(old) != len(value["operations"]):
            raise ValueError("Native ACE addition count differs")
        count = self.validate_bank("ace_legal", bank)
        RunStore.immutable_json(
            self.out / "update_transactions" / f"ace_legal_b{batch}.json",
            {
                "at": now(),
                "batch": batch,
                "actual_parent": parent,
                "actual_reflections": reflections,
                "native_aggregate_tags": tags,
                "counted_parent": counted,
                "actual_teacher_value": value,
                "publication": bank,
                "next_id": next_id,
                "library_tokens": count,
                "parent_sha256": canonical_json_sha256(parent),
                "publication_sha256": canonical_json_sha256(bank),
                "native_ADD_and_last_duplicate_tag_counter_semantics_preserved": True,
                "configured_one_curator_group_no_reducer_required": True,
                "no_gold_reflection_fed_back_to_current_lawyer_or_train_retry": True,
                "no_best_bank_or_effect_admission": True,
            },
        )
        return bank

    def initial_static(self):
        schema = {
            "type": "object",
            "additionalProperties": False,
            "required": ["skills"],
            "properties": {
                "skills": {"type": "array", "items": callable_skill_schema(self.labels)}
            },
        }
        value = self.teacher_call(
            "static_task_only",
            "Create a compact task-only legal source-inspection library for the original public hypotheses and query API. "
            "No contracts, gold, solver trajectories or outcomes are supplied; never invent them. "
            "Skills contain arbitrary id, distinct public hypothesis_ids, concise operational guidance and queries; "
            "do not fix the number or types. No case tables, entities, dates, source indices or outside law. "
            "Only published public scope will select all stored queries. Respect the full serialized library token cap. "
            + QUERY_API_SYSTEM,
            {
                "original_public_hypotheses": self.labels,
                "no_seen_cases_or_trajectories": True,
                "full_serialized_library_token_cap": self.cfg["library_token_hard_cap"],
            },
            schema,
        )
        self.validate_bank("static", value["skills"])
        return value["skills"]

    def execute(self):
        self.check()
        RunStore.immutable_json(
            self.out / "launch.json", {"at": now(), "pid": os.getpid(), "argv": sys.argv}
        )
        RunStore.immutable_json(
            self.out / "declaration.json",
            {
                "at": now(),
                "run_id": self.run_id,
                "config": self.cfg,
                "frozen_bindings": self.bindings,
                "all_three_learners_from_empty_own_trajectories": True,
                "official_dev_test_not_used": True,
                "not_canonical_unmodified_ACE_or_paper_confirmation": True,
            },
        )
        RunStore.immutable_json(
            self.out / "source_snapshot.json",
            {
                "files": {
                    p: {"sha256": h, "utf8_text": Path(p).read_text()}
                    for p, h in self.bindings.items()
                    if Path(p).suffix in (".py", ".md", ".txt") or Path(p).name == "LICENSE"
                }
            },
        )
        ready = WireClient(self.cfg["generation"]).readiness()
        RunStore.immutable_json(self.out / "native_readiness.json", ready)
        if not ready["ready"]:
            raise RuntimeError("Frozen 8B unavailable; no alternative model")
        t = self.cfg["teacher"]
        checker = CodexCLIClient(
            model=t["model"],
            cache_root=self.out / "teacher_admin",
            executable="/usr/bin/codex",
            invocation_budget_path=ROOT / t["ledger"],
            max_invocations=t["total_invocation_budget"],
        )
        readiness, budget = checker.preflight(), checker.invocation_budget_status()
        RunStore.immutable_json(
            self.out / "teacher_readiness.json", {"readiness": readiness, "budget": budget}
        )
        if not readiness["ready"] or budget["available"] < self.cfg["planned_new_teacher_calls"]:
            raise RuntimeError("Declared existing teacher allowance unavailable before learning")
        self.static = self.initial_static()
        for batch in range(1, 9):
            self.current_batch = batch
            rows = [r for r in self.training if r["batch"] == batch]
            before = {}
            for arm in LEARNERS:
                if batch == 1 and arm == "source_only":
                    before[arm] = []
                    for row, cold in zip(rows, before["experience"], strict=True):
                        expected, _, _, _ = self.messages(arm, row, [])
                        raw = read(Path(cold["raw_artifact"]))
                        if raw["calls"][0]["request"]["messages"] != expected:
                            raise ValueError("Cold sharing requires bit-identical actual messages")
                        shared = {**cold, "arm": arm, "shared_cold_actual_native_no_new_call": True}
                        RunStore.immutable_json(
                            self.out / f"batch{batch}_before" / arm / f"{row['id']}.shared.json",
                            shared,
                        )
                        before[arm].append(shared)
                else:
                    before[arm] = self.collect(f"batch{batch}_before", arm, rows, self.banks[arm])
                for u in before[arm]:
                    self.before[arm][u["document_id"]] = [u]
            strong = self.collect(f"batch{batch}_control", "strong_empty", rows, [])
            after = {}
            order = LEARNERS[(batch - 1) % 3 :] + LEARNERS[: (batch - 1) % 3]
            for arm in order:
                self.banks[arm] = (
                    self.update_ace(batch)
                    if arm == "ace_legal"
                    else self.update_callable(arm, batch)
                )
                after[arm] = self.collect(f"batch{batch}_after", arm, rows, self.banks[arm])
                for u in after[arm]:
                    self.after[arm][u["document_id"]] = [u]
            summary = {
                "at": now(),
                "batch": batch,
                "source_ids": [r["id"] for r in rows],
                "before": {a: points(us) for a, us in before.items()},
                "after": {a: points(us) for a, us in after.items()},
                "strong_empty": points(strong),
                "update_effects": {a: paired(before[a], after[a]) for a in LEARNERS},
                "actual_library_counts": {
                    a: len(bullets(bank)) if a == "ace_legal" else len(bank)
                    for a, bank in self.banks.items()
                },
                "actual_library_hashes": {
                    a: canonical_json_sha256(bank) for a, bank in self.banks.items()
                },
                "after_is_seen_training_fit_not_unseen_transfer": True,
            }
            self.summaries.append(summary)
            RunStore.immutable_json(self.out / f"batch{batch}_summary.json", summary)
            write_report(self.out)
            self.progress("batch_complete", completed_batches=batch)
            if batch in (4, 8):
                first = [r for r in self.training if r["batch"] == 1]
                check = {
                    a: points(self.collect(f"retention_b{batch}", a, first, self.banks[a]))
                    for a in LEARNERS
                }
                self.retention.append(
                    {"batch": batch, "metrics": check, "never_to_teacher_or_update_gate": True}
                )
                RunStore.immutable_json(self.out / f"retention_b{batch}.json", self.retention[-1])
        fixed = {
            "at": now(),
            "learners": self.banks,
            "static": self.static,
            "last_published_not_best_checkpoint": True,
            "no_future_predictions_or_gold_yet": True,
        }
        RunStore.immutable_json(self.out / "libraries_frozen_before_later.json", fixed)
        ungraded = {a: [] for a in FINAL_ARMS}
        for index, row in enumerate(self.future):
            offset = index % len(FINAL_ARMS)
            for arm in FINAL_ARMS[offset:] + FINAL_ARMS[:offset]:
                bank = (
                    self.banks[arm] if arm in self.banks else self.static if arm == "static" else []
                )
                ungraded[arm].append(self.answer("later", arm, row, bank))
        self.finish(ungraded)

    def finish(self, ungraded):
        self.check()
        if (
            len(self.native) != self.cfg["planned_new_native_calls"]
            or len(self.teachers) != self.cfg["planned_new_teacher_calls"]
        ):
            raise ValueError("Declared full finite native/teacher matrix required")
        if any(len(v) != len(self.future) for v in ungraded.values()):
            raise ValueError("All six conditions must finish before future Gold access")
        gold = read(ROOT / self.cfg["grading_only"])["annotations"]
        future = {r["id"]: r for r in self.future}
        by = {
            a: [
                {
                    **u,
                    **original_feedback(
                        u["response"],
                        future[u["document_id"]],
                        gold[str(u["document_id"])],
                        list(self.labels),
                    ),
                }
                for u in units
            ]
            for a, units in ungraded.items()
        }
        training_rows = {r["id"]: r for r in self.training}
        for u in self.units:
            if u["document_id"] in training_rows:
                row = training_rows[u["document_id"]]
                expected = original_score(
                    u["response"], row, row["annotation_sets"][0]["annotations"], list(self.labels)
                )
                close(expected, {k: u[k] for k in expected})
        for arm, units in by.items():
            for u in units:
                row = future[u["document_id"]]
                expected = original_score(
                    u["response"], row, gold[str(row["id"])], list(self.labels)
                )
                close(expected, {k: u[k] for k in expected})
                raw = read(Path(u["raw_artifact"]))
                assert raw["response"] == u["response"]
                messages, _, plan, trace = self.messages(arm, row, u["published_library"])
                assert messages == raw["calls"][0]["request"]["messages"]
                assert plan == u["actual_public_plan"] and trace == u["actual_factual_trace"]
                RunStore.immutable_json(
                    self.out / "development_results" / arm / f"{row['id']}.json", u
                )
        identities = [n["response"]["raw_id"] for n in self.native]
        if len(identities) != len(set(identities)):
            raise ValueError("Actual native invocation identity repeated")
        results = {a: points(units) for a, units in by.items()}
        lookup = {a: {u["document_id"]: u for u in units} for a, units in by.items()}
        contrasts = [("experience", c) for c in FINAL_ARMS if c != "experience"]
        intervals = {}
        rng = np.random.default_rng(self.cfg["bootstrap_seed"])
        for treatment, control in contrasts:
            draws = {e: [] for e in ENDPOINTS}
            for _ in range(self.cfg["bootstrap_draws"]):
                selected = [
                    i
                    for g in rng.integers(0, len(self.groups), len(self.groups))
                    for i in self.groups[g]
                ]
                a, b = (points([lookup[arm][i] for i in selected]) for arm in (control, treatment))
                for e in ENDPOINTS:
                    if a[e] is not None and b[e] is not None:
                        draws[e].append(b[e] - a[e])
            intervals[f"{treatment}_minus_{control}"] = {
                e: {
                    "point": results[treatment][e] - results[control][e],
                    "ci95_descriptive": [float(v) for v in np.quantile(values, [0.025, 0.975])],
                }
                for e, values in draws.items()
                if values
            }
        costs = {
            f: sum(n["response"][f] for n in self.native)
            for f in ("prompt_tokens", "completion_tokens")
        }
        teacher_costs = {
            f: sum(t["invocation"]["usage"][f] for t in self.teachers)
            for f in ("input_tokens", "output_tokens", "reasoning_output_tokens")
        }
        done = {
            "at": now(),
            "run_id": self.run_id,
            "new_native_calls": len(self.native),
            "new_teacher_calls": len(self.teachers),
            "training_documents": len(self.training),
            "batches": self.summaries,
            "retention": self.retention,
            "future_documents": len(self.future),
            "source_groups": self.groups,
            "development": results,
            "paired_effects": {f"{a}_minus_{b}": paired(by[b], by[a]) for a, b in contrasts},
            "descriptive_source_group_intervals": intervals,
            "native_usage": costs,
            "teacher_usage": teacher_costs,
            "teacher_role_counts": {
                a: sum(t["name"].startswith(a) for t in self.teachers)
                for a in ("experience", "source_only", "ace_legal", "static")
            },
            "native_usage_by_arm": {
                a: {
                    f: sum(n["response"][f] for n in self.native if n["arm"] == a)
                    for f in ("prompt_tokens", "completion_tokens")
                }
                for a in FINAL_ARMS
            },
            "teacher_usage_by_arm": {
                a: {
                    f: sum(
                        t["invocation"]["usage"][f]
                        for t in self.teachers
                        if t["name"].startswith(a)
                    )
                    for f in ("input_tokens", "output_tokens", "reasoning_output_tokens")
                }
                for a in ("experience", "source_only", "ace_legal", "static")
            },
            "one_learning_replica_each_not_cross_repeat_stability_or_official_confirmation": True,
            "ACE_core_preserved_legal_batch_no_oracle_retry_adaptation_not_unmodified_author_run": True,
            "teacher_budget_and_information_history_differences_explicit_not_exact_compute_matched": True,
            "all_invalid_and_adverse_cases_retained_no_effect_gate": True,
        }
        RunStore.immutable_json(self.out / "completion.json", done)
        RunStore.immutable_json(self.report / "complete_metrics.json", done)
        RunStore.atomic_json(
            self.out / "progress.json",
            {
                "at": now(),
                "run_id": self.run_id,
                "state": "completed",
                "stage": "complete_eight_batch_six_arm_comparison",
                "completed_native_calls": len(self.native),
                "planned_native_calls": self.cfg["planned_new_native_calls"],
                "completed_teacher_calls": len(self.teachers),
                "current_batch": 8,
            },
        )
