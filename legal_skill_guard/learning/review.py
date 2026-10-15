"""Learn answer-inspection skills, then apply them to an actual lawyer draft.

This is a new development intervention, not an established performance fix.
The lawyer makes both calls. No host legal verdict, answer merging, evidence
closure, confidence gate, fallback, or score-based publication is performed.
"""

from __future__ import annotations

import copy
import json
import os
import signal
import sys
import zipfile
from pathlib import Path

import numpy as np
from jsonschema import validate

from legal_skill_guard.data import FUTURE_IDS, TRAIN_IDS, source_components
from legal_skill_guard.experiment.storage import RunStore, safe_component
from legal_skill_guard.inference.codex_cli_client import CodexCLIClient
from legal_skill_guard.inference.native import WireClient
from legal_skill_guard.report import write_report
from legal_skill_guard.task import marked_text, original_feedback, output_schema
from legal_skill_guard.utils.hashing import canonical_json_sha256

from .audit import close, original_score
from .experiment import ENDPOINTS, ROOT, Comparison, now, points, read, sha
from .interface import final_messages
from .publication import (
    DELTA_TEACHER_SYSTEM,
    apply_differential_publication,
    differential_schema,
    paired,
    skill_record_schema,
)

REVIEW_SYSTEM = (
    " You are now inspecting an actual earlier answer to this SAME NDA. The draft "
    "is fallible model output, not a reference answer or a source of contract facts. "
    "Read the original NDA to check it. Review each existing relation and its "
    "evidence separately: an evidence omission alone does not reverse a relation; "
    "a wrong relation is not cured just by adding citations. Make a source-grounded "
    "correction where needed and preserve a decision when inspection supports it. "
    "Do not change a decision merely to demonstrate that a review occurred. "
    "For each evidence set inspect governing language, conditions, exceptions and "
    "independent parallel support, including redundant support required by this "
    "task; do not add neighbouring or same-topic clauses without proposition-specific "
    "support. Use only the skills listed under the matching hypothesis. These "
    "lists organize applicability, not hidden context isolation. Skills are "
    "inspection procedures, never facts about the current NDA or automatic verdicts. "
    "Return the COMPLETE final answer in the original output schema, not patches "
    "or a critique. The host will score your exact answer without merging it with "
    "the draft, filling evidence, or selecting between answers. A failed draft "
    "does not remove the obligation to answer. No further tools or retries."
)

REVIEW_TEACHER_SYSTEM = DELTA_TEACHER_SYSTEM + (
    " The executed method is draft -> skill-guided inspection -> complete final "
    "native lawyer answer. Every new case uses the current learned bank in that "
    "inspection call; the independent draft is NOT the method's final answer. "
    "There are no lexical queries, retrieval examples, extra reflector, current-case "
    "gold at inference, or host legal decisions. Learn compact conditional checks "
    "that a weak lawyer can APPLY TO AN EXISTING ANSWER: what observable feature "
    "should trigger source inspection, what textual condition settles that check, "
    "and what to preserve when that condition is absent. Distinguish relation "
    "correction from evidence completion and evidence exclusion. Do not merely "
    "repeat the task instructions or broaden a rule to fit one case. Before "
    "generalizing, contrast every available seen case supporting the boundary "
    "with the actual seen counterexamples; do not fabricate a successful execution. "
    "All cumulative original annotations and own failures remain in the input. "
    "Use the observed draft/before/after differences to diagnose the changed "
    "component, but do not claim that self-reported skill IDs prove causation. "
    "Keep useful parent checks verbatim unless a boundary correction is warranted. "
    "Runtime records have only id, hypothesis_ids and guidance. No mandatory types, "
    "count or growth. CREATE/UPDATE/DELETE/MERGE/NOOP retain the existing atomic "
    "editor semantics. No case IDs, parties, dates, span indices, answer tables "
    "or benchmark-specific exceptions in guidance. Original labels are feedback, "
    "not universal law. Runtime sees only the published checks under each public "
    "hypothesis. Full-bank visibility in one call must not be mistaken for isolation."
)


def review_messages(row, labels, bank, system, draft):
    """Use only source/public task/actual draft/bank. Never inspect annotations."""
    schema = output_schema(row, list(labels), bank)
    # The shared task builder intentionally reuses its common field object.
    # Per-hypothesis restrictions require independent copies before editing.
    schema["properties"] = {k: copy.deepcopy(v) for k, v in schema["properties"].items()}
    grouped = {}
    for key in labels:
        applicable = [s for s in bank if key in s["hypothesis_ids"]]
        ids = [s["id"] for s in applicable]
        field = schema["properties"][key]["properties"]["used_skill_ids"]
        if ids:
            field["items"]["enum"] = ids
        else:
            field.update(items={"type": "string"}, maxItems=0)
        grouped[key] = [{"id": s["id"], "guidance": s["guidance"]} for s in applicable]
    common = copy.deepcopy(schema["properties"][next(iter(labels))])
    # The actual schema enforces the original coordinate range. Do not repeat a
    # long numeric candidate list or one hypothesis's skill-ID range as answers.
    common["properties"]["spans"]["items"] = {"type": "integer"}
    common["properties"]["used_skill_ids"] = {"type": "array", "items": {"type": "string"}}
    body = {
        "full_contract_with_original_span_markers": marked_text(row),
        "hypotheses": {k: v["hypothesis"] for k, v in labels.items()},
        "original_public_short_descriptions": {
            k: v["short_description"] for k, v in labels.items()
        },
        "untrusted_actual_initial_answer": {
            "content": draft["content"],
            "finish_reason": draft["finish_reason"],
        },
        "learned_inspection_skills_by_hypothesis": grouped,
        "output_contract": {
            "required_hypothesis_keys": list(labels),
            "common_schema_for_each_hypothesis": common,
            "used_skill_ids_must_come_from_matching_hypothesis_list": True,
            "schema_is_permitted_values_not_current_answers": True,
        },
    }
    return [
        {"role": "system", "content": system + REVIEW_SYSTEM},
        {"role": "user", "content": json.dumps(body, ensure_ascii=False, separators=(",", ":"))},
    ], schema


def prepare_review_packets(root, cfg):
    """Original TRAIN only; metadata selection, no outcome-based case choices."""
    archive = root / cfg["source_archive"]
    if sha(archive) != cfg["source_archive_sha256"]:
        raise ValueError("Pinned original archive differs")
    with zipfile.ZipFile(archive) as z:
        data = json.loads(z.read("contract-nli/train.json"))
    docs = {r["id"]: r for r in data["documents"]}
    training_ids = cfg["training_ids"]
    excluded = set(cfg["already_used_training_or_transfer_or_probe_ids"])
    later_ids = [i for i in TRAIN_IDS if i not in excluded][:8]
    if later_ids != cfg["expected_later_ids"] or set(training_ids) & set(later_ids):
        raise ValueError("Frozen ordered source selection differs")
    selected = set(training_ids + later_ids)
    groups = source_components(data["documents"])
    if selected & set(FUTURE_IDS) or any(
        len(set(g) & selected) > 1
        or (set(g) & selected and set(g) & set(FUTURE_IDS))
        or (set(g) & set(later_ids) and set(g) & excluded)
        for g in groups
    ):
        raise ValueError("Protected source or duplicate component selected")
    packet = {
        "public_hypotheses": data["labels"],
        "training": [{**docs[i], "batch": j // 2 + 1} for j, i in enumerate(training_ids)],
        "later_inputs_no_annotation_sets": [
            {k: v for k, v in docs[i].items() if k != "annotation_sets"} for i in later_ids
        ],
    }
    RunStore.immutable_json(root / cfg["input_packet"], packet)
    RunStore.immutable_json(
        root / cfg["grading_only"],
        {
            "annotations": {
                str(i): docs[i]["annotation_sets"][0]["annotations"] for i in later_ids
            },
            "read_only_after_all_later_native_answers_saved": True,
        },
    )
    selection = {
        "training_ids": training_ids,
        "future_ids": later_ids,
        "source_archive_sha256": cfg["source_archive_sha256"],
        "read_members": ["contract-nli/train.json"],
        "selection": "first8 remaining IDs in existing TRAIN_IDS metadata order, after declared exclusions",
        "source_disjoint": True,
        "official_dev_test_opened": False,
        "possible_historical_developer_exposure_not_official_blind_test": True,
    }
    RunStore.immutable_json(root / cfg["preselection"], selection)
    return selection


class ReviewStudy(Comparison):
    """Reuse audited transport/editor/storage, not the legacy study control flow."""

    def __init__(self, config_path, *, run_id=None):
        self.config_path = Path(config_path).resolve()
        self.cfg = read(self.config_path)
        self.run_id = safe_component(run_id or self.cfg["run_id"])
        self.out = ROOT / "runs" / self.run_id
        self.report = ROOT / self.cfg["report_directory"] / self.run_id
        if self.out.exists():
            raise FileExistsError("New Run ID required")
        frozen = read(self.config_path.with_suffix(".frozen.json"))
        if frozen["config_sha256"] != sha(self.config_path):
            raise ValueError("Frozen configuration differs")
        self.bindings = frozen["files"]
        packet = read(ROOT / self.cfg["input_packet"])
        self.labels, self.training = packet["public_hypotheses"], packet["training"]
        self.future = packet["later_inputs_no_annotation_sets"]
        if (len(self.labels), len(self.training), len(self.future)) != (17, 8, 8):
            raise ValueError("Declared four-batch repair study only")
        if any(sum(r["batch"] == b for r in self.training) != 2 for b in range(1, 5)):
            raise ValueError("Each of the four batches must have two sources")
        if any("annotation_sets" in r for r in self.future):
            raise ValueError("Future inference input contains annotations")
        self.meter = WireClient(self.cfg["generation"])
        self.native, self.units, self.teachers, self.shared_units = [], [], [], []
        self.teacher_attempts, self.current_batch, self.stop = 0, 0, False
        self.bank, self.drafts, self.before, self.after = [], {}, {}, {}
        self.versions = {canonical_json_sha256([]): []}
        self.summaries = []
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, lambda *_: setattr(self, "stop", True))

    def messages(self, arm, row, bank):
        if arm == "strong_empty":
            if bank:
                raise ValueError("Independent draft must have empty memory")
            messages, schema = final_messages(
                row, self.labels, [], self.cfg["bundled_solver_system"]
            )
        elif arm in ("empty_review", "skill_review"):
            if arm == "empty_review" and bank:
                raise ValueError("Empty-review control cannot receive learned memory")
            messages, schema = review_messages(
                row,
                self.labels,
                bank,
                self.cfg["bundled_solver_system"],
                self.drafts[row["id"]]["response"],
            )
        else:
            raise ValueError("Unknown answer-review arm")
        return messages, schema, None, None

    def validate_bank(self, arm, bank):
        if arm != "skill_review" or len({s["id"] for s in bank}) != len(bank):
            raise ValueError("Invalid review bank identity")
        for s in bank:
            validate(s, skill_record_schema(self.labels))
            if len(s["hypothesis_ids"]) != len(set(s["hypothesis_ids"])):
                raise ValueError("Duplicate public hypothesis scope")
        count = self.meter.token_count(text=json.dumps(bank, ensure_ascii=False))
        if count > self.cfg["library_token_hard_cap"]:
            raise ValueError("Complete bank exceeds cap; no truncation or old-bank fallback")
        return count

    @staticmethod
    def observation(unit):
        return {
            "stage": unit["stage"],
            "raw_artifact": unit["raw_artifact"],
            "actual_public_response": unit["response"],
            "policy_version_sha256": unit["published_library_sha256"],
            "public_valid": unit["public_valid"],
            "public_error": unit["public_error"],
            "original_component_feedback": unit["queries"],
        }

    def update_review(self, batch):
        seen = [r for r in self.training if r["batch"] <= batch]
        cases = [
            {
                "document_id": r["id"],
                "original_full_contract_with_spans": marked_text(r),
                "original_annotations": r["annotation_sets"][0]["annotations"],
                "actual_independent_draft": self.observation(self.drafts[r["id"]]),
                "actual_skill_review_before_learning": self.observation(self.before[r["id"]]),
                "actual_prior_after_learning": self.observation(self.after[r["id"]])
                if r["id"] in self.after
                else None,
            }
            for r in seen
        ]
        body = {
            "original_public_hypotheses": self.labels,
            "complete_actual_parent_library": self.bank,
            "all_seen_original_train_cases": cases,
            "actual_historical_policy_versions": self.versions,
            "full_serialized_library_token_cap": self.cfg["library_token_hard_cap"],
            "no_future_retention_other_arms_or_private_thinking": True,
        }
        value = self.teacher_call(
            f"skill_review_b{batch}",
            REVIEW_TEACHER_SYSTEM,
            body,
            differential_schema(self.labels, self.bank, [r["id"] for r in seen]),
        )
        bank = apply_differential_publication(
            self.bank, value, self.labels, [r["id"] for r in seen]
        )
        tokens = self.validate_bank("skill_review", bank)
        RunStore.immutable_json(
            self.out / "update_transactions" / f"skill_review_b{batch}.json",
            {
                "at": now(),
                "batch": batch,
                "actual_parent": self.bank,
                "actual_teacher_value": value,
                "publication": bank,
                "library_tokens": tokens,
                "source_case_ids": [r["id"] for r in seen],
                "no_effect_gate_rollback_or_mandatory_growth": True,
            },
        )
        self.versions[canonical_json_sha256(bank)] = copy.deepcopy(bank)
        return bank

    def execute(self):
        self.check()
        RunStore.immutable_json(
            self.out / "launch.json", {"at": now(), "pid": os.getpid(), "argv": sys.argv}
        )
        RunStore.immutable_json(
            self.out / "declaration.json",
            {
                "at": now(),
                "config": self.cfg,
                "frozen_bindings": self.bindings,
                "new_method_development_not_confirmed_improvement": True,
                "draft_plus_review_same_model_both_empty_and_skill_conditions": True,
                "all_skill_edits_unconditionally_published": True,
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
        ready = self.meter.readiness()
        t = self.cfg["teacher"]
        checker = CodexCLIClient(
            model=t["model"],
            executable="/usr/bin/codex",
            cache_root=self.out / "teacher_admin",
            invocation_budget_path=ROOT / t["ledger"],
            max_invocations=t["total_invocation_budget"],
        )
        teacher_ready, budget = checker.preflight(), checker.invocation_budget_status()
        RunStore.immutable_json(
            self.out / "readiness.json",
            {"native": ready, "teacher": teacher_ready, "teacher_budget": budget},
        )
        if not ready["ready"] or not teacher_ready["ready"] or budget["available"] < 4:
            raise RuntimeError("Declared model/teacher unavailable; no substitutes")
        for batch in range(1, 5):
            self.current_batch = batch
            rows = [r for r in self.training if r["batch"] == batch]
            base, empty, before, after = [], [], [], []
            for r in rows:
                draft = self.collect(f"batch{batch}_draft", "strong_empty", [r], [])[0]
                self.drafts[r["id"]] = draft
                base.append(draft)
                control = self.collect(f"batch{batch}_control", "empty_review", [r], [])[0]
                empty.append(control)
                if batch == 1:
                    messages, schema, _, _ = self.messages("skill_review", r, [])
                    wire = read(control["raw_artifact"])["calls"][0]["request"]
                    if (
                        wire["messages"] != messages
                        or wire["response_format"]["json_schema"]["schema"] != schema
                    ):
                        raise ValueError(
                            "Cold sharing requires identical actual messages and schema"
                        )
                    current = {
                        **control,
                        "stage": "batch1_before",
                        "arm": "skill_review",
                        "shared_actual_empty_review_no_new_generation": True,
                    }
                    self.shared_units.append(current)
                    RunStore.immutable_json(
                        self.out / "batch1_before" / "skill_review" / f"{r['id']}.shared.json",
                        current,
                    )
                else:
                    current = self.collect(f"batch{batch}_before", "skill_review", [r], self.bank)[
                        0
                    ]
                self.before[r["id"]] = current
                before.append(current)
            self.bank = self.update_review(batch)
            after = self.collect(f"batch{batch}_after", "skill_review", rows, self.bank)
            for u in after:
                self.after[u["document_id"]] = u
            summary = {
                "at": now(),
                "batch": batch,
                "source_ids": [r["id"] for r in rows],
                "before": {
                    "strong_empty": points(base),
                    "empty_review": points(empty),
                    "skill_review": points(before),
                },
                "after": {"skill_review": points(after)},
                "strong_empty": points(base),
                "empty_review": points(empty),
                "update_effects": paired(before, after),
                "draft_to_before": paired(base, before),
                "draft_to_after": paired(base, after),
                "actual_library_counts": {"skill_review": len(self.bank)},
                "after_is_seen_training_fit_not_unseen_transfer": True,
            }
            self.summaries.append(summary)
            RunStore.immutable_json(self.out / f"batch{batch}_summary.json", summary)
            write_report(self.out)
            self.progress("batch_complete", completed_batches=batch)
        first = [r for r in self.training if r["batch"] == 1]
        retained = self.collect("retention_b4", "skill_review", first, self.bank)
        RunStore.immutable_json(
            self.out / "retention_b4.json",
            {
                "metrics": points(retained),
                "B1_M1_to_M4": paired([self.after[r["id"]] for r in first], retained),
                "never_to_teacher_or_effect_gate": True,
            },
        )
        RunStore.immutable_json(
            self.out / "library_frozen_before_later.json",
            {"at": now(), "library": self.bank, "last_published_not_best_checkpoint": True},
        )
        later = {a: [] for a in ("strong_empty", "empty_review", "skill_review")}
        for j, r in enumerate(self.future):
            draft = self.answer("later_draft", "strong_empty", r, [])
            self.drafts[r["id"]] = draft
            later["strong_empty"].append(draft)
            for a in (
                ("empty_review", "skill_review") if j % 2 == 0 else ("skill_review", "empty_review")
            ):
                later[a].append(
                    self.answer("later", a, r, [] if a == "empty_review" else self.bank)
                )
        self.finish_review(later)

    def finish_review(self, later):
        self.check()
        if (len(self.native), len(self.teachers), len(self.shared_units)) != (56, 4, 2):
            raise ValueError("Complete declared call matrix required")
        if any(len(v) != 8 for v in later.values()):
            raise ValueError("All24 later answers required before reading Gold")
        gold = read(ROOT / self.cfg["grading_only"])["annotations"]
        future = {r["id"]: r for r in self.future}
        by = {}
        for arm, units in later.items():
            by[arm] = []
            for u in units:
                r = future[u["document_id"]]
                scored = original_feedback(u["response"], r, gold[str(r["id"])], list(self.labels))
                independent = original_score(
                    u["response"], r, gold[str(r["id"])], list(self.labels)
                )
                close(independent, {k: scored[k] for k in independent})
                raw = read(u["raw_artifact"])
                messages, schema, _, _ = self.messages(arm, r, u["published_library"])
                wire = raw["calls"][0]["request"]
                if (
                    raw["response"] != u["response"]
                    or wire["messages"] != messages
                    or wire["response_format"]["json_schema"]["schema"] != schema
                ):
                    raise ValueError("Actual source/draft/skill/schema/answer wire mismatch")
                value = {**u, **scored}
                RunStore.immutable_json(self.out / "later_scored" / arm / f"{r['id']}.json", value)
                by[arm].append(value)
        training = {r["id"]: r for r in self.training}
        for u in self.units:
            if u["document_id"] in training:
                r = training[u["document_id"]]
                expected = original_score(
                    u["response"], r, r["annotation_sets"][0]["annotations"], list(self.labels)
                )
                close(expected, {k: u[k] for k in expected})
        results = {a: points(v) for a, v in by.items()}
        rng = np.random.default_rng(self.cfg["bootstrap_seed"])
        intervals = {}
        for control in ("strong_empty", "empty_review"):
            draws = {e: [] for e in ENDPOINTS}
            for _ in range(self.cfg["bootstrap_draws"]):
                indices = rng.integers(0, 8, 8)
                a, b = (points([by[arm][i] for i in indices]) for arm in ("skill_review", control))
                for e in ENDPOINTS:
                    draws[e].append(a[e] - b[e])
            intervals[control] = {
                e: {
                    "point": results["skill_review"][e] - results[control][e],
                    "ci95_descriptive_conditional_on_one_bank": list(
                        map(float, np.quantile(x, [0.025, 0.975]))
                    ),
                }
                for e, x in draws.items()
            }
        raw_ids = [n["response"]["raw_id"] for n in self.native]
        if len(set(raw_ids)) != len(raw_ids):
            raise ValueError("Duplicate physical generation identity")
        done = {
            "at": now(),
            "run_id": self.run_id,
            "new_native_calls": 56,
            "new_teacher_calls": 4,
            "explicit_shared_cold_reviews": 2,
            "batches": self.summaries,
            "development": results,
            "paired_skill_minus_control": {
                a: paired(by[a], by["skill_review"]) for a in ("strong_empty", "empty_review")
            },
            "descriptive_source_intervals": intervals,
            "native_usage": {
                k: sum(n["response"][k] for n in self.native)
                for k in ("prompt_tokens", "completion_tokens")
            },
            "teacher_usage": {
                k: sum(t["invocation"]["usage"][k] for t in self.teachers)
                for k in ("input_tokens", "output_tokens", "reasoning_output_tokens")
            },
            "not_official_test_or_independent_learning_repeat": True,
            "native_final_answers_not_host_merged_repaired_or_selected": True,
        }
        RunStore.immutable_json(self.out / "completion.json", done)
        RunStore.immutable_json(self.report / "complete_metrics.json", done)
        write_report(self.out)
        RunStore.atomic_json(
            self.out / "progress.json",
            {
                "at": now(),
                "run_id": self.run_id,
                "state": "completed",
                "completed_native_calls": 56,
                "completed_teacher_calls": 4,
                "completed_batches": 4,
            },
        )
