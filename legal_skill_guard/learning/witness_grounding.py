"""Unregistered teacher-grounding candidate; the live66-bound Run is unchanged.

Training-only witness statements must cover the supplied source window and all
original Gold members. They are auditable teacher claims, not an independent
semantic verifier, runtime memory, efficacy admission or answer repair.
"""

from __future__ import annotations

import copy
from pathlib import Path

from jsonschema import validate

from legal_skill_guard.experiment.storage import RunStore

from .experiment import ROOT, now, read
from .literal_evidence import LITERAL_TEACHER_NOTICE, LiteralEvidenceStudy, literal_feedback_view
from .publication import apply_differential_publication, differential_schema, publication_statistics
from .task_local import LOCAL_GUIDANCE_SCHEMA, LOCAL_TEACHER_SYSTEM, TaskLocalStudy, bounded_teacher_packet, prepare_task_local_inputs


def fixed_control_slots(cfg):
    """Only86 non-learning controls; every62 main-path native stays new.

    In particular, B1 cold answers and all main before/after/retention/endpoint
    answers cannot be inherited. The source is fixed before observing outcomes.
    """
    training, later = cfg["training_ids"], cfg["expected_later_ids"]
    if (len(training) != 24 or len(set(training)) != 24 or len(later) != 8
            or len(set(later)) != 8 or set(training) & set(later)):
        raise ValueError("Exact distinct24/8 source identities required")
    slots = {(f"batch{b}_before", arm, d) for b in (2, 3, 4)
             for d in training[(b - 1) * 6:b * 6]
             for arm in ("strong_empty", "ordinary_memory", "unconditional_layout")}
    slots |= {("later", arm, d) for d in later
              for arm in ("strong_empty", "ordinary_memory", "unconditional_layout", "static_procedures")}
    if len(slots) != 86 or any(arm == "skill_memory" or stage.startswith("batch1") for stage, arm, _ in slots):
        raise ValueError("References cannot include a learned main answer or initial cold draw")
    return slots


def fixed_control_references(cfg):
    """Read the complete named source, never select a control by its score.

    This is a mandatory declared input policy, not an on-error cache or fallback.
    The existing complete native-wire audit still reconstructs every reference
    with the new learner's current input function before any endpoint grading.
    """
    if (cfg.get("control_reference_policy") != "fixed_complete_literal_controls_v1"
            or cfg.get("teacher_publication_format") != "explicit_witness_coverage_v1"
            or cfg.get("continuation_parent")
            or (cfg.get("planned_new_native_calls"), cfg.get("planned_inherited_native_calls"),
                cfg.get("planned_new_teacher_calls"), cfg.get("planned_inherited_teacher_calls")) != (62, 86, 4, 1)):
        raise ValueError("Explicit62 fresh main/86 fixed controls/4 new editors/1 static reference required")
    source = ROOT / cfg["control_reference_run"]
    source_config = ROOT / cfg["control_reference_config"]
    original = read(source_config)
    progress = read(source / "progress.json")
    if progress["state"] != "completed" or not (source / "completion.json").exists():
        raise ValueError("Fixed control source must be terminal complete literal148/4+1, not live or partial")
    done, launch = read(source / "completion.json"), read(source / "launch.json")
    if ((Path("/proc") / str(launch["pid"])).exists()
            or source.name != original["run_id"] or source.name == cfg["run_id"]
            or (done["new_native_calls"], done["explicitly_inherited_native_calls"],
                done["new_teacher_calls"], done["explicitly_inherited_teacher_calls"],
                done["distinct_native_responses"], done["logical_observations"]) != (148, 0, 4, 1, 148, 166)):
        raise ValueError("Fixed control source must be terminal complete literal148/4+1, not live or partial")
    for key in ("generation", "teacher", "bundled_solver_system", "library_token_hard_cap", "input_packet",
                "grading_only", "preselection", "training_ids", "expected_later_ids", "source_archive",
                "source_archive_sha256", "reference_training_run", "method", "memory_representation",
                "teacher_feedback", "teacher_packet_encoding", "candidate_source_view", "teacher_feedback_view",
                "static_control_policy", "static_public_reference"):
        if cfg[key] != original[key]:
            raise ValueError("Fixed control input condition changed: " + key)
    slots = fixed_control_slots(cfg)
    references = {}
    paths = [source_config, source_config.with_suffix(".frozen.json"), source / "completion.json",
             source / "launch.json", source / "static_procedures.json"]
    native_ids = set()
    for stage, arm, d in sorted(slots):
        path = source / stage / arm / f"{d}.public.json"
        unit = read(path)
        raw_path = Path(unit["raw_artifact"]).resolve()
        if (unit["stage"], unit["arm"], unit["document_id"]) != (stage, arm, d) or not raw_path.is_relative_to(source.resolve()):
            raise ValueError("Control reference source/slot identity changed")
        raw = read(raw_path)
        if len(raw["calls"]) != 1 or raw["response"] != unit["response"] or raw["response"]["raw_id"] in native_ids:
            raise ValueError("Fixed controls require86 distinct actual native responses")
        expected_bank = read(source / "static_procedures.json")["library"] if arm == "static_procedures" else []
        if unit["published_library"] != expected_bank:
            raise ValueError("A main skill bank entered a no-learning control")
        native_ids.add(raw["response"]["raw_id"])
        references[(stage, arm, d)] = (path, unit)
        paths.extend((path, raw_path))
    return references, sorted(set(paths))


def prepare_witness_inputs(cfg):
    """Called only by the prospective explicit CLI registration, not the live Run."""
    if cfg.get("teacher_publication_format") != "explicit_witness_coverage_v1":
        raise ValueError("Unknown teacher publication format")
    selection, paths = prepare_task_local_inputs(cfg)
    if cfg.get("control_reference_run"):
        _, reference_paths = fixed_control_references(cfg)
        paths += reference_paths
    return selection, paths


WITNESS_NOTICE = (
    " For each non-delete edit, make the training-only witness_checks explicit "
    "before distilling its runtime skill. There must be one group for every "
    "published public-hypothesis scope and an assessment of EVERY supplied case, "
    "not just the operation's chosen source_case_ids. Assess the source condition "
    "the proposed rule actually needs, not whether the question has that topic. "
    "For a label-implying rule, when must be a concrete sufficient condition in "
    "the document, not merely a task trigger; an unmet sufficient condition never "
    "implies NM. State established, not_established or unresolved and cite original "
    "source coordinates for the brief public boundary fact. Compare cases whose "
    "original labels differ; do not silently admit a negative into a positive rule. "
    "A sufficient rule need not cover every same-label case. Account for EVERY "
    "original Gold evidence member in gold_member_account, including governing "
    "language, exceptions and independent redundant support, not only a minimal "
    "classification justification. Explain its source function and what a generic "
    "inspection would need to retain. Empty Gold is not independent proof of "
    "absence. These short factual assessments are public evidence statements, "
    "not a request for private reasoning. If no reusable separating condition is "
    "justified, an inspection-only null relation remains available. Do not invent "
    "a condition to please the schema. DELETE has empty witness_checks. All witness "
    "IDs, coordinates and case-specific facts stay in this training-only field; "
    "runtime guidance must not contain case tables, parties, IDs or fingerprints. "
    "Only the unchanged skill records reach the lawyer. No extra model or trial, "
    "legal host adjudicator, score admission, answer completion or fallback exists."
)


def witness_publication_schema(labels, parent, rows):
    """Bind coordinates/Gold-member identities, not the truth of any condition."""
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
    groups = []
    for h in labels:
        cases = {}
        for row in rows:
            gold = row["annotation_sets"][0]["annotations"][h]
            fields = {
                "source_condition_status": {"$ref": "#/$defs/condition_status"},
                "source_condition_evidence": {"$ref": f"#/$defs/source_{row['id']}_coordinates"},
                "brief_boundary_fact": {"type": "string", "minLength": 1, "maxLength": 240},
                "gold_member_account": {
                    "type": "object", "additionalProperties": False,
                    "required": [str(i) for i in gold["spans"]],
                    "properties": {str(i): {"type": "string", "minLength": 1, "maxLength": 160} for i in gold["spans"]},
                },
            }
            cases[str(row["id"])] = {"type": "object", "additionalProperties": False, "required": list(fields), "properties": fields}
        properties = {
            "hypothesis_id": {"type": "string", "enum": [h]},
            "cases": {"type": "object", "additionalProperties": False, "required": list(cases), "properties": cases},
        }
        groups.append({"type": "object", "additionalProperties": False, "required": list(properties), "properties": properties})
    op = schema["properties"]["operations"]["items"]
    existing = op["properties"]
    op["properties"] = {
        "operation": existing["operation"], "target_ids": existing["target_ids"],
        "witness_checks": {"type": "array", "items": {"anyOf": groups}},
        **{k: v for k, v in existing.items() if k not in ("operation", "target_ids")},
    }
    op["required"] = list(op["properties"])
    return schema


def publish_with_training_witnesses(parent, value, labels, rows):
    """Publish every well-formed edit; archive disagreement, never reject on it."""
    validate(value, witness_publication_schema(labels, parent, rows))
    projected = copy.deepcopy(value)
    sources = {str(r["id"]): r for r in rows}
    observations, conflicts, unsupported = [], [], []
    accounted = 0
    for original, op in zip(value["operations"], projected["operations"], strict=True):
        checks = op.pop("witness_checks")
        skill = op["skill"]
        if skill is None:
            if checks:
                raise ValueError("DELETE has no resulting runtime condition to assess")
            continue
        scope = skill["hypothesis_ids"]
        observed = [group["hypothesis_id"] for group in checks]
        if len(observed) != len(set(observed)) or set(observed) != set(scope):
            raise ValueError("Witness groups must match exact published public scope")
        target = skill["guidance"]["relation_if_established"]
        positive_witnesses = 0
        for group in checks:
            h = group["hypothesis_id"]
            for d, entry in group["cases"].items():
                indices = entry["source_condition_evidence"]
                if len(indices) != len(set(indices)):
                    raise ValueError("Duplicate original witness coordinates; no deduplication")
                gold = sources[d]["annotation_sets"][0]["annotations"][h]
                established = entry["source_condition_status"] == "established"
                claim = {"skill_id": skill["id"], "hypothesis_id": h, "source_id": int(d),
                         "claimed_condition_status": entry["source_condition_status"], "published_relation": target,
                         "original_Gold_choice": gold["choice"], "brief_boundary_fact": entry["brief_boundary_fact"]}
                observations.append(claim)
                accounted += len(entry["gold_member_account"])
                if target is not None and established:
                    if target != gold["choice"]:
                        conflicts.append(claim)
                    else:
                        positive_witnesses += 1
        if target is not None and positive_witnesses == 0:
            unsupported.append(skill["id"])
        # The exact proposed runtime record is never changed by these flags.
        assert original["skill"] == skill
    published = apply_differential_publication(parent, projected, labels, [r["id"] for r in rows], guidance_schema=LOCAL_GUIDANCE_SCHEMA)
    return published, projected, {
        "teacher_claims_not_independent_semantic_verification": observations,
        "claimed_established_with_different_original_label": conflicts,
        "nonnull_records_without_claimed_same_label_positive_witness": unsupported,
        "original_Gold_members_explicitly_accounted_not_proven_retrieved": accounted,
        "no_semantic_conflict_or_coverage_based_admission_repair_or_bank_choice": True,
    }


class WitnessGroundedStudy(LiteralEvidenceStudy):
    """Not CLI-registered: same runtime/calls, explicit training witness output."""

    def __init__(self, config_path, *, run_id=None):
        super().__init__(config_path, run_id=run_id)
        if self.cfg.get("teacher_publication_format") != "explicit_witness_coverage_v1":
            raise ValueError("Prospective witness-output policy must be declared explicitly")
        if self.cfg.get("control_reference_run"):
            self.prefix_answers, _ = fixed_control_references(self.cfg)
            self.prefix_slots = set(self.prefix_answers)

    def update(self, batch):
        tokens = self.validate_library(self.bank)
        packet = bounded_teacher_packet(self.training, batch, self.labels, self.bank, self.state, self.before, self.after, master_tokens=tokens["master_tokens"], cap=self.cfg["library_token_hard_cap"])
        rows = [r for r in self.training if r["id"] in packet["supplied_original_witness_ids"]]
        body = literal_feedback_view(packet, rows)
        body["serialized_parent_scoped_delivery_tokens"] = tokens["scoped_delivery_tokens"]
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
            "teacher_publication_format": "explicit_witness_coverage_v1",
            "original_annotations_and_actual_answers_not_rewritten": True,
        })
        return bank, stats
