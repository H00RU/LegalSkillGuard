"""Unregistered teacher-grounding candidate; the live66-bound Run is unchanged.

Training-only witness statements must cover the supplied source window and all
original Gold members. They are auditable teacher claims, not an independent
semantic verifier, runtime memory, efficacy admission or answer repair.
"""

from __future__ import annotations

import copy
import json

from jsonschema import validate

from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.task import render_library

from .experiment import now
from .literal_evidence import LITERAL_TEACHER_NOTICE, LiteralEvidenceStudy, literal_feedback_view
from .publication import apply_differential_publication, differential_schema, publication_statistics, skill_record_schema
from .skill_tables import COLUMNS, scoped_budget_view, table_skill_messages
from .task_local import LOCAL_GUIDANCE_SCHEMA, LOCAL_TEACHER_SYSTEM, bounded_teacher_packet, task_skill_projection


WITNESS_NOTICE = (
    " First account for EVERY original Gold evidence member in "
    "training_evidence_accounts, across ALL public hypotheses and ALL supplied "
    "cases, exactly once per batch, including successful cases, governing "
    "language, exceptions and independent redundant support. Give each member's "
    "brief source function and the inspection needed to retain it, not only a "
    "minimal classification justification. Empty Gold is not proof of absence. "
    "Then for each non-delete edit assess its actual when condition in EVERY "
    "supplied case in witness_checks, not only the selected source_case_ids. "
    "Each record has one when condition shared by its declared scope. For a "
    "label-implying record it must be a concrete sufficient source condition, "
    "not a task/topic trigger; compare its implied relation with EVERY scoped "
    "hypothesis's different-label witnesses. If distinct conditions are needed, "
    "write clear separate records rather than mix their meaning. A sufficient "
    "condition need not cover all same-label cases, and its absence never implies "
    "NM. State established/not_established/unresolved, cite original coordinates "
    "and give a brief public boundary fact before distilling the runtime rule. "
    "These are public factual explanations, not private reasoning. If no generic "
    "separating condition is justified, a null-relation inspection remains valid. "
    "Do not invent conditions or force growth. DELETE uses empty witness_checks. "
    "Case IDs, coordinates and case-specific accounts stay in training metadata, "
    "never in runtime guidance. Runtime receives all original words in lossless "
    "scoped tables under a shared field-name header; this removes repeated keys, "
    "not knowledge, scope or source access. Both master and actual table projection "
    "must fit the token cap. Keep runtime concise; the evidence detail belongs in "
    "training accounts, not copied case tables. No extra critic, legal host "
    "adjudicator, semantic admission, answer completion, bank choice or fallback."
)


def witness_publication_schema(labels, parent, rows):
    """One global member account plus one condition assessment per edit/case."""
    ids = [r["id"] for r in rows]
    if not rows or len(ids) != len(set(ids)) or any(not r["spans"] for r in rows):
        raise ValueError("Actual distinct nonempty original source window required")
    schema = differential_schema(labels, parent, ids, guidance_schema=LOCAL_GUIDANCE_SCHEMA)
    schema["$defs"] = {
        f"source_{r['id']}_coordinates": {
            "type": "array", "items": {"type": "integer", "minimum": 0, "maximum": len(r["spans"]) - 1},
        } for r in rows
    }
    schema["$defs"]["condition_status"] = {"type": "string", "enum": ["established", "not_established", "unresolved"]}
    accounts = {}
    for h in labels:
        cases = {}
        for row in rows:
            members = row["annotation_sets"][0]["annotations"][h]["spans"]
            cases[str(row["id"])] = {
                "type": "object", "additionalProperties": False,
                "required": [str(i) for i in members],
                "properties": {str(i): {"type": "string", "minLength": 1, "maxLength": 160} for i in members},
            }
        accounts[h] = {"type": "object", "additionalProperties": False, "required": list(cases), "properties": cases}
    schema["properties"] = {
        "training_evidence_accounts": {"type": "object", "additionalProperties": False, "required": list(accounts), "properties": accounts},
        **schema["properties"],
    }
    schema["required"] = ["training_evidence_accounts", *schema["required"]]
    cases = {}
    for row in rows:
        fields = {
            "source_condition_status": {"$ref": "#/$defs/condition_status"},
            "source_condition_evidence": {"$ref": f"#/$defs/source_{row['id']}_coordinates"},
            "brief_boundary_fact": {"type": "string", "minLength": 1, "maxLength": 240},
        }
        cases[str(row["id"])] = {"type": "object", "additionalProperties": False, "required": list(fields), "properties": fields}
    op = schema["properties"]["operations"]["items"]
    existing = op["properties"]
    op["properties"] = {
        "operation": existing["operation"], "target_ids": existing["target_ids"],
        "witness_checks": {"anyOf": [
            {"type": "object", "additionalProperties": False, "required": list(cases), "properties": cases},
            {"type": "object", "additionalProperties": False, "required": [], "properties": {}},
        ]},
        **{k: v for k, v in existing.items() if k not in ("operation", "target_ids")},
    }
    op["required"] = list(op["properties"])
    return schema


def publish_with_training_witnesses(parent, value, labels, rows):
    """Identity checks only; publish semantic disagreements verbatim, not gate."""
    validate(value, witness_publication_schema(labels, parent, rows))
    projected = copy.deepcopy(value)
    accounts = projected.pop("training_evidence_accounts")
    sources = {str(r["id"]): r for r in rows}
    observations, conflicts, unsupported = [], [], []
    accounted = sum(len(members) for cases in accounts.values() for members in cases.values())
    for original, op in zip(value["operations"], projected["operations"], strict=True):
        checks = op.pop("witness_checks")
        skill = op["skill"]
        if skill is None:
            if checks:
                raise ValueError("DELETE has no resulting runtime condition to assess")
            continue
        if set(checks) != set(sources):
            raise ValueError("Witness checks must cover every supplied original source")
        target = skill["guidance"]["relation_if_established"]
        positive_by_h = {h: 0 for h in skill["hypothesis_ids"]}
        for d, entry in checks.items():
            indices = entry["source_condition_evidence"]
            if len(indices) != len(set(indices)):
                raise ValueError("Duplicate original witness coordinates; no deduplication")
            for h in skill["hypothesis_ids"]:
                gold = sources[d]["annotation_sets"][0]["annotations"][h]
                claim = {"skill_id": skill["id"], "hypothesis_id": h, "source_id": int(d),
                         "claimed_condition_status": entry["source_condition_status"], "published_relation": target,
                         "original_Gold_choice": gold["choice"], "brief_boundary_fact": entry["brief_boundary_fact"]}
                observations.append(claim)
                if target is not None and entry["source_condition_status"] == "established":
                    if target != gold["choice"]:
                        conflicts.append(claim)
                    else:
                        positive_by_h[h] += 1
        if target is not None and any(n == 0 for n in positive_by_h.values()):
            unsupported.append(skill["id"])
        assert original["skill"] == skill
    published = apply_differential_publication(parent, projected, labels, [r["id"] for r in rows], guidance_schema=LOCAL_GUIDANCE_SCHEMA)
    return published, projected, {
        "teacher_claims_not_independent_semantic_verification": observations,
        "claimed_established_with_different_original_label": conflicts,
        "nonnull_records_without_claimed_same_label_positive_witness": unsupported,
        "original_Gold_members_explicitly_accounted_once_not_proven_retrieved": accounted,
        "no_semantic_conflict_or_coverage_based_admission_repair_or_bank_choice": True,
    }


class WitnessGroundedStudy(LiteralEvidenceStudy):
    """Not CLI-registered: original native task, table skills, grounded writer."""

    def __init__(self, config_path, *, run_id=None):
        super().__init__(config_path, run_id=run_id)
        if self.cfg.get("teacher_publication_format") != "explicit_witness_accounts_v2":
            raise ValueError("Prospective witness-output policy must be declared explicitly")
        if self.cfg.get("skill_delivery_encoding") != "scoped_lossless_table_v1":
            raise ValueError("Prospective lossless skill delivery must be explicit")

    def make_payload(self, arm, row, bank, model, state):
        messages, schema, plan, trace = super().make_payload(arm, row, bank, model, state)
        messages, delivery = table_skill_messages(messages, trace["task_local_delivery"])
        view = scoped_budget_view(delivery["actual_task_local_projection"])
        delivery["actual_scoped_delivery_tokens"] = self.meter.token_count(text=json.dumps(view, ensure_ascii=False, separators=(",", ":")))
        return messages, schema, plan, {**trace, "task_local_delivery": delivery}

    def validate_library(self, bank):
        for skill in bank:
            validate(skill, skill_record_schema(self.labels, guidance_schema=LOCAL_GUIDANCE_SCHEMA))
            if len(set(skill["hypothesis_ids"])) != len(skill["hypothesis_ids"]) or len(set(skill["guidance"]["source_operations"])) != len(skill["guidance"]["source_operations"]):
                raise ValueError("Duplicate original scope or factual operation")
        projection = task_skill_projection(bank, self.labels)
        master = self.meter.token_count(text=render_library(bank))
        scoped = self.meter.token_count(text=json.dumps(scoped_budget_view(projection), ensure_ascii=False, separators=(",", ":")))
        if max(master, scoped) > self.cfg["library_token_hard_cap"]:
            raise ValueError("Master or actual table projection over declared capacity; no pruning/fallback")
        return {"master_tokens": master, "scoped_delivery_tokens": scoped}

    def update(self, batch):
        tokens = self.validate_library(self.bank)
        packet = bounded_teacher_packet(self.training, batch, self.labels, self.bank, self.state, self.before, self.after, master_tokens=tokens["master_tokens"], cap=self.cfg["library_token_hard_cap"])
        rows = [r for r in self.training if r["id"] in packet["supplied_original_witness_ids"]]
        body = literal_feedback_view(packet, rows)
        body["serialized_parent_scoped_delivery_tokens"] = tokens["scoped_delivery_tokens"]
        body["lawyer_skill_delivery_encoding"] = {
            "format": "scoped_lossless_table_v1", "columns": list(COLUMNS),
            "same_public_scope_and_words_no_semantic_filter_or_verdict": True,
            "semantic_projection_in_observations_is_losslessly_decoded_not_wire_object_spelling": True,
            "training_witness_metadata_never_enters_runtime_table_or_its_token_budget": True,
        }
        value = self.teacher_call(f"task_local_b{batch}", LOCAL_TEACHER_SYSTEM + LITERAL_TEACHER_NOTICE + WITNESS_NOTICE, body, witness_publication_schema(self.labels, self.bank, rows))
        bank, projection, witness_audit = publish_with_training_witnesses(self.bank, value, self.labels, rows)
        capacity = self.validate_library(bank)
        stats = {**publication_statistics(self.bank, projection, bank, capacity["master_tokens"]), "serialized_scoped_delivery_tokens": capacity["scoped_delivery_tokens"]}
        RunStore.immutable_json(self.out / f"update_transactions/b{batch}.json", {
            "at": now(), "batch": batch, "actual_parent": self.bank,
            "actual_teacher_value": value, "publication_input_without_training_only_witness_metadata": projection,
            "teacher_witness_claim_audit_not_admission": witness_audit,
            "publication": bank, "management": stats, "source_case_ids": [r["id"] for r in rows],
            "all_valid_changes_published_without_efficacy_gate": True,
            "actual_current_and_previous_same_parent_window_not_full_cumulative_raw_history": True,
            "no_fixed_skill_count_growth_deletion_or_best_bank_selection": True,
            "new_teacher_invocation_for_this_edit": True,
            "teacher_feedback_view": "literal_evidence_comparisons_v1",
            "teacher_publication_format": "explicit_witness_accounts_v2",
            "skill_delivery_encoding": "scoped_lossless_table_v1",
            "original_annotations_and_actual_answers_not_rewritten": True,
        })
        return bank, stats
