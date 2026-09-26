"""Pure, paired prequential learning-curve statistics for training sentinels.

The module deliberately performs no rollout, persistence, candidate admission, or
configuration lookup.  A caller supplies already-scored current-library and
empty-library trajectories.  This keeps the descriptive learning curve separate
from the candidate lifecycle.  It verifies matched initial infrastructure while
leaving stepwise sole-intervention auditing to the executor's pre-scoring gate.
"""

from __future__ import annotations

import math
import statistics
from collections import defaultdict
from collections.abc import Mapping, Sequence, Set
from typing import Any, Final

from legal_skill_guard.evaluation.semantic import TrajectoryEvaluation
from legal_skill_guard.evaluation.statistics import paired_bootstrap_interval
from legal_skill_guard.schemas.experiment import ResearchTrajectory
from legal_skill_guard.utils.hashing import canonical_json_sha256

# Keep this definition outside executor.py so the executor can import the pure
# statistic without creating a circular dependency.  Keep the full policy-safety
# panel beside the effectiveness endpoints so a gain cannot hide premature
# stopping, unsupported advice, belief laundering, or simulator/runtime fallback.
DEVELOPMENT_CURVE_METRICS: Final[tuple[tuple[str, str], ...]] = (
    ("official_metrics", "resolution"),
    ("official_metrics", "elicitation"),
    ("official_metrics", "fidelity"),
    ("safety_metrics", "critical_fact_recall"),
    ("safety_metrics", "premature_final_rate"),
    ("safety_metrics", "unsupported_claim_rate"),
    ("safety_metrics", "belief_as_fact_rate"),
    ("safety_metrics", "hidden_field_leak"),
    ("safety_metrics", "repeated_question_rate"),
    ("operational_metrics", "policy_fallback_rate"),
    ("operational_metrics", "client_fallback_rate"),
)

PREQUENTIAL_CURVE_METRICS: Final[tuple[str, ...]] = (
    *(field for _, field in DEVELOPMENT_CURVE_METRICS),
    "reward",
    "question_turns",
    "unique_disclosed_facts",
    "unique_disclosed_facts_per_question",
    "identified_evidence_gaps",
)

EMPTY_LIBRARY_METHOD: Final[str] = "control_no_library"
CURRENT_LIBRARY_METHOD: Final[str] = "legal_skill_evolve"
TRAINING_SENTINEL_METHODS: Final[frozenset[str]] = frozenset(
    {"training_policy_sample"}
)
IDENTITY_BASELINE_METHODS: Final[frozenset[str]] = frozenset(
    {*TRAINING_SENTINEL_METHODS, EMPTY_LIBRARY_METHOD, CURRENT_LIBRARY_METHOD}
)
METHOD_COMPATIBLE_PAIRS: Final[frozenset[tuple[str, str]]] = frozenset(
    {
        ("training_policy_sample", "training_policy_sample"),
        (CURRENT_LIBRARY_METHOD, EMPTY_LIBRARY_METHOD),
    }
)

# These values must be identical before a pair can enter the learning-curve
# statistic.  Outcome fields (steps, memo, status, elapsed time) are intentionally
# excluded: this module does not replace the executor's stepwise intervention
# isolation gate.
_INITIAL_INFRASTRUCTURE_IDENTITY_FIELDS: Final[tuple[str, ...]] = (
    "run_id",
    "group_id",
    "case_id",
    "domain",
    "jurisdiction",
    "persona",
    "seed",
    "sample_index",
    "model_id",
    "model_revision",
    "opening",
    "max_turns",
    "opening_inquiry_agenda",
)

_JUDGE_IDENTITY_FIELDS: Final[tuple[str, ...]] = (
    "schema_version",
    "judge_model",
    "judge_qualification_contract_sha256",
)


def _pair_key(trajectory: ResearchTrajectory) -> tuple[str, str, int, int]:
    """Return the matched policy-stream cell represented by one trajectory."""

    return (
        str(trajectory.case_id),
        str(trajectory.persona),
        int(trajectory.seed),
        int(trajectory.sample_index),
    )


def _json_value(value: Any) -> Any:
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return model_dump(mode="json")
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    return value


def _evaluation_for(
    trajectory: ResearchTrajectory,
    evaluations: Mapping[str, TrajectoryEvaluation],
    *,
    arm: str,
) -> TrajectoryEvaluation:
    try:
        evaluation = evaluations[str(trajectory.trajectory_id)]
    except KeyError as error:
        raise ValueError(
            f"{arm} evaluation missing for trajectory {trajectory.trajectory_id}"
        ) from error
    if str(evaluation.trajectory_id) != str(trajectory.trajectory_id):
        raise ValueError(f"{arm} evaluation trajectory_id does not match its map key")
    if str(evaluation.case_id) != str(trajectory.case_id):
        raise ValueError(f"{arm} evaluation case_id does not match its trajectory")
    return evaluation


def _exposed_skill_ids(trajectory: ResearchTrajectory) -> set[str]:
    return {str(skill_id) for skill_id in trajectory.exposed_skill_ids}


def _validate_arm(
    trajectories: Sequence[ResearchTrajectory],
    evaluations: Mapping[str, TrajectoryEvaluation],
    *,
    arm: str,
    permitted_methods: set[str],
    expected_partition: str,
    expected_library_version: str,
    permitted_skill_ids: set[str],
) -> dict[tuple[str, str, int, int], tuple[ResearchTrajectory, TrajectoryEvaluation]]:
    if not trajectories:
        raise ValueError(f"{arm} requires at least one trajectory")
    trajectory_ids = [str(item.trajectory_id) for item in trajectories]
    if len(trajectory_ids) != len(set(trajectory_ids)):
        raise ValueError(f"{arm} contains duplicate trajectory_id values")

    indexed: dict[
        tuple[str, str, int, int], tuple[ResearchTrajectory, TrajectoryEvaluation]
    ] = {}
    for trajectory in trajectories:
        if not str(trajectory.group_id or ""):
            raise ValueError(f"{arm} trajectory lacks an auditable group_id")
        if str(trajectory.status) == "error":
            raise ValueError(f"{arm} contains an error trajectory: {trajectory.trajectory_id}")
        if str(trajectory.method) not in permitted_methods:
            raise ValueError(
                f"{arm} method is not permitted: {trajectory.method}; "
                f"expected one of {sorted(permitted_methods)}"
            )
        if str(trajectory.partition) != expected_partition:
            raise ValueError(f"{arm} trajectory used an unexpected partition")
        if str(trajectory.skill_library_version) != expected_library_version:
            raise ValueError(f"{arm} trajectory used an unexpected skill library version")

        exposed = _exposed_skill_ids(trajectory)
        unexpected = exposed - permitted_skill_ids
        if unexpected:
            raise ValueError(
                f"{arm} trajectory exposed skills outside the declared library: "
                f"{sorted(unexpected)}"
            )
        for step in trajectory.steps:
            selected = list(step.action_decision.activated_skill_ids)
            retrieved = set(step.action_decision.retrieved_skill_ids)
            if (
                len(selected) > 2
                or len(selected) != len(set(selected))
                or any(skill_id not in retrieved for skill_id in selected)
            ):
                raise ValueError(
                    f"{arm} contains invalid legacy skill-activation metadata"
                )
            if any(
                isinstance(item, dict) and item.get("skill_id")
                for item in getattr(step.action_decision, "changes", [])
            ):
                raise ValueError(f"{arm} used the retired runtime skill action rewriter")
        key = _pair_key(trajectory)
        if key in indexed:
            raise ValueError(f"{arm} contains a duplicate matched identity: {key}")
        indexed[key] = (
            trajectory,
            _evaluation_for(trajectory, evaluations, arm=arm),
        )
    return indexed


def _validate_initial_infrastructure_pair(
    empty_trajectory: ResearchTrajectory,
    empty_evaluation: TrajectoryEvaluation,
    current_trajectory: ResearchTrajectory,
    current_evaluation: TrajectoryEvaluation,
) -> None:
    if str(empty_trajectory.trajectory_id) == str(current_trajectory.trajectory_id):
        raise ValueError("paired rollout arms must have distinct trajectory_id values")
    method_pair = (str(current_trajectory.method), str(empty_trajectory.method))
    if method_pair not in METHOD_COMPATIBLE_PAIRS:
        raise ValueError(
            "current/empty method pair is not compatible with a shared policy stream: "
            f"{method_pair}"
        )
    drift = [
        field
        for field in _INITIAL_INFRASTRUCTURE_IDENTITY_FIELDS
        if _json_value(getattr(empty_trajectory, field, None))
        != _json_value(getattr(current_trajectory, field, None))
    ]
    if drift:
        raise ValueError(
            "current/empty trajectories violate initial infrastructure identity; drift: "
            + ", ".join(drift)
        )
    judge_drift = [
        field
        for field in _JUDGE_IDENTITY_FIELDS
        if _json_value(getattr(empty_evaluation, field))
        != _json_value(getattr(current_evaluation, field))
    ]
    if judge_drift:
        raise ValueError(
            "current/empty evaluations use incompatible judges; identity drift: "
            + ", ".join(judge_drift)
        )


def _metric_values(
    trajectory: ResearchTrajectory, evaluation: TrajectoryEvaluation
) -> dict[str, float]:
    question_turns = sum(bool(step.rendered_question) for step in trajectory.steps)
    unique_disclosed_facts = evaluation.mechanism_signals.newly_elicited_fact_count
    values = {
        field: float(getattr(getattr(evaluation, section), field, 0.0))
        for section, field in DEVELOPMENT_CURVE_METRICS
    }
    values.update(
        {
            "reward": float(evaluation.reward.final_reward),
            "question_turns": float(question_turns),
            "unique_disclosed_facts": float(unique_disclosed_facts),
            "unique_disclosed_facts_per_question": (
                float(unique_disclosed_facts) / question_turns if question_turns else 0.0
            ),
            "identified_evidence_gaps": float(
                evaluation.mechanism_signals.identified_evidence_gap_count
            ),
        }
    )
    return values


def _rounded_values(values: Mapping[str, float]) -> dict[str, float]:
    return {name: round(float(values[name]), 6) for name in PREQUENTIAL_CURVE_METRICS}


def _teacher_visible_process_trace(
    trajectory: ResearchTrajectory,
    evaluation: TrajectoryEvaluation,
) -> dict[str, Any]:
    """Project the actual visible question/outcome process for later reflection.

    The projection contains only dialogue content already observed in a training
    rollout and aggregate disclosed-fact counts already available to the teacher.
    It deliberately excludes undisclosed case facts and evaluator reasoning.
    """

    turns: list[dict[str, Any]] = []
    for step in trajectory.steps:
        question = str(getattr(step, "rendered_question", "") or "")
        if not question:
            continue
        action_decision = getattr(step, "action_decision", None)
        action = getattr(action_decision, "final", None) or getattr(
            step, "proposed_action", None
        )
        response_kind = str(getattr(step, "client_response_kind", "") or "none")
        disclosed = (
            sorted(str(item) for item in getattr(step, "client_selected_fact_ids", []) or [])
            if response_kind == "new_hidden_fact"
            else []
        )
        turns.append(
            {
                "turn": int(getattr(step, "turn", len(turns) + 1)),
                "target_kind": str(getattr(action, "target_type", "") or ""),
                "target_description": str(
                    getattr(action, "expected_information", "") or ""
                ),
                "question": question,
                "client_response": str(getattr(step, "client_response", "") or ""),
                "response_kind": response_kind,
                "new_disclosed_fact_count": len(disclosed),
            }
        )
    facts = int(evaluation.mechanism_signals.newly_elicited_fact_count)
    questions = len(turns)
    return {
        "trajectory_id": str(trajectory.trajectory_id),
        "question_count": questions,
        "new_fact_count": facts,
        "facts_per_question": round(facts / questions, 6) if questions else 0.0,
        "turns": turns,
        "undisclosed_hidden_facts_included": False,
    }


def build_prequential_sentinel_report(
    *,
    sentinel_id: str,
    current_trajectories: Sequence[ResearchTrajectory],
    current_evaluations: Mapping[str, TrajectoryEvaluation],
    current_partition: str,
    current_library_version: str,
    current_skill_ids: Set[str],
    empty_partition: str,
    empty_library_version: str,
    empty_trajectories: Sequence[ResearchTrajectory] | None = None,
    empty_evaluations: Mapping[str, TrajectoryEvaluation] | None = None,
    identity_baseline: bool = False,
    bootstrap_samples: int = 10_000,
    confidence_level: float = 0.95,
    bootstrap_seed: int = 42,
) -> dict[str, Any]:
    """Build one auditable current-library minus empty-library curve point.

    ``identity_baseline`` is reserved for an actually empty current library.  It
    reuses each current observation as its own empty-library baseline, yielding an
    explicit zero point without an unnecessary second rollout.  A non-empty curve
    point requires two distinct, method-compatible arms and fails closed on any
    identity or undeclared infrastructure drift. The global playbook is a declared
    policy-context intervention only; the shared opening agenda remains skill-blind.
    Exact prompt-memory delivery is enforced by the executor's isolation artifact.
    """

    if not sentinel_id.strip():
        raise ValueError("sentinel_id must be non-empty")
    if not current_partition.strip() or not empty_partition.strip():
        raise ValueError("current_partition and empty_partition must be non-empty")
    declared_skill_ids = {str(item) for item in current_skill_ids}
    if "" in declared_skill_ids:
        raise ValueError("current_skill_ids cannot contain an empty identifier")

    if identity_baseline:
        if empty_trajectories is not None or empty_evaluations is not None:
            raise ValueError("identity baseline must not receive duplicate empty-library data")
        if current_library_version != empty_library_version or declared_skill_ids:
            raise ValueError("identity baseline is valid only when the current library is empty")
        current_methods = {str(item.method) for item in current_trajectories}
        if not current_methods <= IDENTITY_BASELINE_METHODS:
            raise ValueError("identity baseline uses a method incompatible with an empty library")
        current = _validate_arm(
            current_trajectories,
            current_evaluations,
            arm="identity_empty_library",
            permitted_methods=set(IDENTITY_BASELINE_METHODS),
            expected_partition=current_partition,
            expected_library_version=current_library_version,
            permitted_skill_ids=set(),
        )
        paired = [(key, *value, *value) for key, value in sorted(current.items())]
    else:
        if empty_trajectories is None or empty_evaluations is None:
            raise ValueError("a non-identity sentinel requires both empty-library inputs")
        if current_library_version == empty_library_version:
            raise ValueError("non-identity sentinel requires distinct library versions")
        if not declared_skill_ids:
            raise ValueError("non-identity sentinel requires at least one current skill id")
        current = _validate_arm(
            current_trajectories,
            current_evaluations,
            arm="current_library",
            permitted_methods={CURRENT_LIBRARY_METHOD, *TRAINING_SENTINEL_METHODS},
            expected_partition=current_partition,
            expected_library_version=current_library_version,
            permitted_skill_ids=declared_skill_ids,
        )
        empty = _validate_arm(
            empty_trajectories,
            empty_evaluations,
            arm="empty_library",
            permitted_methods={EMPTY_LIBRARY_METHOD, *TRAINING_SENTINEL_METHODS},
            expected_partition=empty_partition,
            expected_library_version=empty_library_version,
            permitted_skill_ids=set(),
        )
        if set(current) != set(empty):
            missing_current = sorted(set(empty) - set(current))
            missing_empty = sorted(set(current) - set(empty))
            raise ValueError(
                "current/empty sentinel matrices are not paired exactly; "
                f"missing_current={missing_current}, missing_empty={missing_empty}"
            )
        paired = []
        for key in sorted(current):
            current_trajectory, current_evaluation = current[key]
            empty_trajectory, empty_evaluation = empty[key]
            _validate_initial_infrastructure_pair(
                empty_trajectory,
                empty_evaluation,
                current_trajectory,
                current_evaluation,
            )
            paired.append(
                (
                    key,
                    current_trajectory,
                    current_evaluation,
                    empty_trajectory,
                    empty_evaluation,
                )
            )

    pair_records: list[dict[str, Any]] = []
    records_by_case: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for (
        (case_id, persona, seed, sample_index),
        current_trajectory,
        current_evaluation,
        empty_trajectory,
        empty_evaluation,
    ) in paired:
        current_values = _metric_values(current_trajectory, current_evaluation)
        empty_values = _metric_values(empty_trajectory, empty_evaluation)
        deltas = {
            name: current_values[name] - empty_values[name]
            for name in PREQUENTIAL_CURVE_METRICS
        }
        record = {
            "pair_id": "pair_"
            + canonical_json_sha256(
                {
                    "sentinel_id": sentinel_id,
                    "case_id": case_id,
                    "persona": persona,
                    "seed": seed,
                    "sample_index": sample_index,
                    "empty_trajectory_id": empty_trajectory.trajectory_id,
                    "current_trajectory_id": current_trajectory.trajectory_id,
                }
            )[:24],
            "case_id": case_id,
            "persona": persona,
            "seed": seed,
            "sample_index": sample_index,
            "empty_trajectory_id": str(empty_trajectory.trajectory_id),
            "current_trajectory_id": str(current_trajectory.trajectory_id),
            "empty_library": _rounded_values(empty_values),
            "current_library": _rounded_values(current_values),
            "paired_delta": _rounded_values(deltas),
        }
        pair_records.append(record)
        records_by_case[case_id].append(record)

    case_records: list[dict[str, Any]] = []
    for case_id in sorted(records_by_case):
        records = records_by_case[case_id]
        case_records.append(
            {
                "case_id": case_id,
                "pair_count": len(records),
                "pair_ids": [str(item["pair_id"]) for item in records],
                "empty_library_mean": {
                    name: round(
                        statistics.fmean(float(item["empty_library"][name]) for item in records),
                        6,
                    )
                    for name in PREQUENTIAL_CURVE_METRICS
                },
                "current_library_mean": {
                    name: round(
                        statistics.fmean(
                            float(item["current_library"][name]) for item in records
                        ),
                        6,
                    )
                    for name in PREQUENTIAL_CURVE_METRICS
                },
                "paired_delta_mean": {
                    name: round(
                        statistics.fmean(float(item["paired_delta"][name]) for item in records),
                        6,
                    )
                    for name in PREQUENTIAL_CURVE_METRICS
                },
            }
        )

    metric_summaries: dict[str, Any] = {}
    for name in PREQUENTIAL_CURVE_METRICS:
        pair_deltas = [float(item["paired_delta"][name]) for item in pair_records]
        case_deltas = [float(item["paired_delta_mean"][name]) for item in case_records]
        estimate = paired_bootstrap_interval(
            case_deltas,
            samples=bootstrap_samples,
            confidence_level=confidence_level,
            seed=bootstrap_seed,
        )
        metric_summaries[name] = {
            "empty_library_mean": round(
                statistics.fmean(float(item["empty_library"][name]) for item in pair_records),
                6,
            ),
            "current_library_mean": round(
                statistics.fmean(float(item["current_library"][name]) for item in pair_records),
                6,
            ),
            "pair_mean_delta": round(statistics.fmean(pair_deltas), 6),
            "pair_median_delta": round(statistics.median(pair_deltas), 6),
            "case_cluster_estimate": estimate.model_dump(mode="json"),
        }

    return {
        "report_type": "prequential_current_library_vs_empty_library",
        "sentinel_id": sentinel_id,
        "direction": "current_library_minus_empty_library",
        "identity_baseline": identity_baseline,
        "current_library_version": current_library_version,
        "empty_library_version": empty_library_version,
        "partition_mapping": {
            "current": current_partition,
            "empty": empty_partition,
        },
        "current_skill_ids": sorted(declared_skill_ids),
        "pair_count": len(pair_records),
        "case_cluster_count": len(case_records),
        "bootstrap": {
            "unit": "case_id",
            "samples": bootstrap_samples,
            "confidence_level": confidence_level,
            "seed": bootstrap_seed,
        },
        "initial_infrastructure_identity": {
            "passed": True,
            "scope": "matched_identity_and_pre_dialogue_infrastructure_only",
            "method_pairs": [
                list(pair)
                for pair in sorted(
                    {
                        (
                            str(current_trajectory.method),
                            str(empty_trajectory.method),
                        )
                        for _, current_trajectory, _, empty_trajectory, _ in paired
                    }
                )
            ],
            "matched_identity_fields": list(_INITIAL_INFRASTRUCTURE_IDENTITY_FIELDS),
            "judge_identity_fields": list(_JUDGE_IDENTITY_FIELDS),
            "baseline_has_no_skill_exposure": True,
            "current_exposures_restricted_to_declared_library": True,
            "stepwise_intervention_isolation": (
                "identity_by_construction"
                if identity_baseline
                else "required_prompt_memory_pre_scoring_gate_not_verified_here"
            ),
        },
        "metrics": metric_summaries,
        "cases": case_records,
        "pairs": pair_records,
    }


def build_parent_cohort_sentinel_report(
    *,
    sentinel_id: str,
    current_trajectories: Sequence[ResearchTrajectory],
    current_evaluations: Mapping[str, TrajectoryEvaluation],
    current_partition: str,
    current_library_version: str,
    current_skill_ids: Set[str],
    parent_trajectories: Sequence[ResearchTrajectory],
    parent_evaluations: Mapping[str, TrajectoryEvaluation],
    parent_partition: str,
    parent_library_version: str,
    parent_skill_ids: Set[str],
    new_skill_increment_ids: Set[str],
    bootstrap_samples: int = 10_000,
    confidence_level: float = 0.95,
    bootstrap_seed: int = 42,
) -> dict[str, Any]:
    """Build one paired current-library minus exact-parent curve point.

    Unlike :func:`build_prequential_sentinel_report`, the baseline is allowed to
    contain prompt skills.  A document increment may either create a new stable
    skill ID or update the document stored under an existing stable ID.  This
    metric-only function therefore validates the identifier-level invariants
    (no parent removal, every created ID declared, every declared ID present).
    The executor separately binds the declared cohort to exact document hashes,
    version increments and unchanged-parent bytes before calling this function.

    ``new_skill_increment_ids`` is retained as a persisted schema field for
    existing run compatibility; its current semantics are "created or updated
    skill-document IDs", not only the set difference of identifiers.
    """

    if not sentinel_id.strip():
        raise ValueError("sentinel_id must be non-empty")
    if not current_partition.strip() or not parent_partition.strip():
        raise ValueError("current_partition and parent_partition must be non-empty")
    if current_partition == parent_partition:
        raise ValueError("parent-cohort sentinel requires distinct partitions")
    if current_library_version == parent_library_version:
        raise ValueError("parent-cohort sentinel requires distinct library versions")

    current_ids = {str(item) for item in current_skill_ids}
    parent_ids = {str(item) for item in parent_skill_ids}
    cohort_ids = {str(item) for item in new_skill_increment_ids}
    if "" in current_ids | parent_ids | cohort_ids:
        raise ValueError("parent-cohort skill identifiers must be non-empty")
    if not cohort_ids:
        raise ValueError("parent-increment sentinel requires a non-empty skill increment")
    created_ids = current_ids - parent_ids
    if (
        not parent_ids <= current_ids
        or not created_ids <= cohort_ids
        or not cohort_ids <= current_ids
    ):
        raise ValueError(
            "current library must retain its exact parent and contain every declared "
            "created-or-updated document increment"
        )

    current = _validate_arm(
        current_trajectories,
        current_evaluations,
        arm="accumulated_current_library",
        permitted_methods={CURRENT_LIBRARY_METHOD, *TRAINING_SENTINEL_METHODS},
        expected_partition=current_partition,
        expected_library_version=current_library_version,
        permitted_skill_ids=current_ids,
    )
    parent = _validate_arm(
        parent_trajectories,
        parent_evaluations,
        arm="exact_parent_library",
        permitted_methods={CURRENT_LIBRARY_METHOD, *TRAINING_SENTINEL_METHODS},
        expected_partition=parent_partition,
        expected_library_version=parent_library_version,
        permitted_skill_ids=parent_ids,
    )
    if set(current) != set(parent):
        missing_current = sorted(set(parent) - set(current))
        missing_parent = sorted(set(current) - set(parent))
        raise ValueError(
            "current/parent sentinel matrices are not paired exactly; "
            f"missing_current={missing_current}, missing_parent={missing_parent}"
        )

    paired: list[
        tuple[
            tuple[str, str, int, int],
            ResearchTrajectory,
            TrajectoryEvaluation,
            ResearchTrajectory,
            TrajectoryEvaluation,
        ]
    ] = []
    for key in sorted(current):
        current_trajectory, current_evaluation = current[key]
        parent_trajectory, parent_evaluation = parent[key]
        _validate_initial_infrastructure_pair(
            parent_trajectory,
            parent_evaluation,
            current_trajectory,
            current_evaluation,
        )
        paired.append(
            (
                key,
                current_trajectory,
                current_evaluation,
                parent_trajectory,
                parent_evaluation,
            )
        )

    pair_records: list[dict[str, Any]] = []
    records_by_case: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for (
        (case_id, persona, seed, sample_index),
        current_trajectory,
        current_evaluation,
        parent_trajectory,
        parent_evaluation,
    ) in paired:
        current_values = _metric_values(current_trajectory, current_evaluation)
        parent_values = _metric_values(parent_trajectory, parent_evaluation)
        deltas = {
            name: current_values[name] - parent_values[name]
            for name in PREQUENTIAL_CURVE_METRICS
        }
        record = {
            "pair_id": "pair_"
            + canonical_json_sha256(
                {
                    "sentinel_id": sentinel_id,
                    "case_id": case_id,
                    "persona": persona,
                    "seed": seed,
                    "sample_index": sample_index,
                    "parent_trajectory_id": parent_trajectory.trajectory_id,
                    "current_trajectory_id": current_trajectory.trajectory_id,
                }
            )[:24],
            "case_id": case_id,
            "persona": persona,
            "seed": seed,
            "sample_index": sample_index,
            "parent_trajectory_id": str(parent_trajectory.trajectory_id),
            "current_trajectory_id": str(current_trajectory.trajectory_id),
            "parent_library": _rounded_values(parent_values),
            "current_library": _rounded_values(current_values),
            "paired_delta": _rounded_values(deltas),
            "parent_process": _teacher_visible_process_trace(
                parent_trajectory, parent_evaluation
            ),
            "current_process": _teacher_visible_process_trace(
                current_trajectory, current_evaluation
            ),
        }
        pair_records.append(record)
        records_by_case[case_id].append(record)

    case_records: list[dict[str, Any]] = []
    for case_id in sorted(records_by_case):
        records = records_by_case[case_id]
        case_records.append(
            {
                "case_id": case_id,
                "pair_count": len(records),
                "pair_ids": [str(item["pair_id"]) for item in records],
                "parent_library_mean": {
                    name: round(
                        statistics.fmean(
                            float(item["parent_library"][name]) for item in records
                        ),
                        6,
                    )
                    for name in PREQUENTIAL_CURVE_METRICS
                },
                "current_library_mean": {
                    name: round(
                        statistics.fmean(
                            float(item["current_library"][name]) for item in records
                        ),
                        6,
                    )
                    for name in PREQUENTIAL_CURVE_METRICS
                },
                "paired_delta_mean": {
                    name: round(
                        statistics.fmean(float(item["paired_delta"][name]) for item in records),
                        6,
                    )
                    for name in PREQUENTIAL_CURVE_METRICS
                },
            }
        )

    metric_summaries: dict[str, Any] = {}
    for name in PREQUENTIAL_CURVE_METRICS:
        pair_deltas = [float(item["paired_delta"][name]) for item in pair_records]
        case_deltas = [float(item["paired_delta_mean"][name]) for item in case_records]
        estimate = paired_bootstrap_interval(
            case_deltas,
            samples=bootstrap_samples,
            confidence_level=confidence_level,
            seed=bootstrap_seed,
        )
        metric_summaries[name] = {
            "parent_library_mean": round(
                statistics.fmean(
                    float(item["parent_library"][name]) for item in pair_records
                ),
                6,
            ),
            "current_library_mean": round(
                statistics.fmean(
                    float(item["current_library"][name]) for item in pair_records
                ),
                6,
            ),
            "pair_mean_delta": round(statistics.fmean(pair_deltas), 6),
            "pair_median_delta": round(statistics.median(pair_deltas), 6),
            "case_cluster_estimate": estimate.model_dump(mode="json"),
        }

    return {
        "report_type": "prequential_new_skill_increment_vs_exact_parent_library",
        "sentinel_id": sentinel_id,
        "direction": COHORT_PARENT_EFFECT_DIRECTION,
        "identity_baseline": False,
        "current_library_version": current_library_version,
        "parent_library_version": parent_library_version,
        "current_skill_ids": sorted(current_ids),
        "parent_skill_ids": sorted(parent_ids),
        "new_skill_increment_ids": sorted(cohort_ids),
        "partition_mapping": {
            "current": current_partition,
            "parent": parent_partition,
        },
        "pair_count": len(pair_records),
        "case_cluster_count": len(case_records),
        "bootstrap": {
            "unit": "case_id",
            "samples": bootstrap_samples,
            "confidence_level": confidence_level,
            "seed": bootstrap_seed,
        },
        "initial_infrastructure_identity": {
            "passed": True,
            "scope": "matched_identity_and_pre_dialogue_infrastructure_only",
            "method_pairs": [
                list(pair)
                for pair in sorted(
                    {
                        (
                            str(current_trajectory.method),
                            str(parent_trajectory.method),
                        )
                        for _, current_trajectory, _, parent_trajectory, _ in paired
                    }
                )
            ],
            "matched_identity_fields": list(_INITIAL_INFRASTRUCTURE_IDENTITY_FIELDS),
            "judge_identity_fields": list(_JUDGE_IDENTITY_FIELDS),
            "parent_exposures_restricted_to_declared_library": True,
            "current_exposures_restricted_to_declared_library": True,
            "stepwise_intervention_isolation": (
                "required_prompt_memory_pre_scoring_gate_not_verified_here"
            ),
        },
        "metrics": metric_summaries,
        "cases": case_records,
        "pairs": pair_records,
    }


def build_current_library_identity_report(
    *,
    sentinel_id: str,
    trajectories: Sequence[ResearchTrajectory],
    evaluations: Mapping[str, TrajectoryEvaluation],
    partition: str,
    library_version: str,
    skill_ids: Set[str],
    bootstrap_samples: int = 10_000,
    confidence_level: float = 0.95,
    bootstrap_seed: int = 42,
) -> dict[str, Any]:
    """Record a zero-cost identity point when no cohort awaits validation.

    This is not an empty-library efficacy comparison.  The current retained
    library is its own exact parent, so every observed sample-0 cell is reused
    only to record an explicit zero delta.  No duplicate rollout, candidate
    decision, or whole-library stop rule is involved.
    """

    if not sentinel_id.strip() or not partition.strip() or not library_version.strip():
        raise ValueError("retained-library identity fields must be non-empty")
    declared_ids = {str(item) for item in skill_ids}
    if "" in declared_ids:
        raise ValueError("retained-library identity skill identifiers must be non-empty")
    current = _validate_arm(
        trajectories,
        evaluations,
        arm="current_library_identity",
        permitted_methods={CURRENT_LIBRARY_METHOD, *TRAINING_SENTINEL_METHODS},
        expected_partition=partition,
        expected_library_version=library_version,
        permitted_skill_ids=declared_ids,
    )

    pair_records: list[dict[str, Any]] = []
    records_by_case: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for (case_id, persona, seed, sample_index), (trajectory, evaluation) in sorted(
        current.items()
    ):
        values = _metric_values(trajectory, evaluation)
        zeros = {name: 0.0 for name in PREQUENTIAL_CURVE_METRICS}
        record = {
            "pair_id": "pair_"
            + canonical_json_sha256(
                {
                    "sentinel_id": sentinel_id,
                    "case_id": case_id,
                    "persona": persona,
                    "seed": seed,
                    "sample_index": sample_index,
                    "identity_trajectory_id": trajectory.trajectory_id,
                    "library_version": library_version,
                }
            )[:24],
            "case_id": case_id,
            "persona": persona,
            "seed": seed,
            "sample_index": sample_index,
            "parent_trajectory_id": str(trajectory.trajectory_id),
            "current_trajectory_id": str(trajectory.trajectory_id),
            "parent_library": _rounded_values(values),
            "current_library": _rounded_values(values),
            "paired_delta": _rounded_values(zeros),
        }
        pair_records.append(record)
        records_by_case[case_id].append(record)

    case_records: list[dict[str, Any]] = []
    for case_id in sorted(records_by_case):
        records = records_by_case[case_id]
        means = {
            name: round(
                statistics.fmean(
                    float(item["current_library"][name]) for item in records
                ),
                6,
            )
            for name in PREQUENTIAL_CURVE_METRICS
        }
        case_records.append(
            {
                "case_id": case_id,
                "pair_count": len(records),
                "pair_ids": [str(item["pair_id"]) for item in records],
                "parent_library_mean": means,
                "current_library_mean": means,
                "paired_delta_mean": {
                    name: 0.0 for name in PREQUENTIAL_CURVE_METRICS
                },
            }
        )

    metric_summaries: dict[str, Any] = {}
    zero_case_deltas = [0.0 for _ in case_records]
    for name in PREQUENTIAL_CURVE_METRICS:
        current_mean = round(
            statistics.fmean(
                float(item["current_library"][name]) for item in pair_records
            ),
            6,
        )
        estimate = paired_bootstrap_interval(
            zero_case_deltas,
            samples=bootstrap_samples,
            confidence_level=confidence_level,
            seed=bootstrap_seed,
        )
        metric_summaries[name] = {
            "parent_library_mean": current_mean,
            "current_library_mean": current_mean,
            "pair_mean_delta": 0.0,
            "pair_median_delta": 0.0,
            "case_cluster_estimate": estimate.model_dump(mode="json"),
        }

    return {
        "report_type": "prequential_current_library_identity",
        "sentinel_id": sentinel_id,
        "direction": COHORT_PARENT_EFFECT_DIRECTION,
        "identity_baseline": True,
        "no_pending_cohort": True,
        "current_library_version": library_version,
        "parent_library_version": library_version,
        "current_skill_ids": sorted(declared_ids),
        "parent_skill_ids": sorted(declared_ids),
        "new_skill_increment_ids": [],
        "partition_mapping": {"current": partition, "parent": partition},
        "pair_count": len(pair_records),
        "case_cluster_count": len(case_records),
        "bootstrap": {
            "unit": "case_id",
            "samples": bootstrap_samples,
            "confidence_level": confidence_level,
            "seed": bootstrap_seed,
        },
        "initial_infrastructure_identity": {
            "passed": True,
            "scope": "same_observation_exact_current_library_identity",
            "method_pairs": [
                list(pair)
                for pair in sorted(
                    {(str(item.method), str(item.method)) for item in trajectories}
                )
            ],
            "matched_identity_fields": list(_INITIAL_INFRASTRUCTURE_IDENTITY_FIELDS),
            "judge_identity_fields": list(_JUDGE_IDENTITY_FIELDS),
            "parent_and_current_skill_documents_identical": True,
            "stepwise_intervention_isolation": "identity_by_construction",
        },
        "metrics": metric_summaries,
        "cases": case_records,
        "pairs": pair_records,
    }


COHORT_PARETO_DISPOSITION_SCHEMA: Final[int] = 1
COHORT_PARETO_DECISION_RULE: Final[str] = "case_cluster_pareto_noninferiority"
COHORT_PARENT_EFFECT_DIRECTION: Final[str] = (
    "current_library_minus_parent_library"
)
COHORT_ENDPOINT_DIRECTIONS: Final[frozenset[str]] = frozenset({"higher", "lower"})


def _strict_positive_int(value: Any, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field} must be a positive integer")
    return value


def _strict_finite_float(value: Any, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a finite number")
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError(f"{field} must be a finite number")
    return parsed


def _cohort_curve(report: Mapping[str, Any]) -> Mapping[str, Any]:
    """Resolve either a curve or an executor-style object containing ``curve``."""

    nested = report.get("curve")
    if nested is None:
        return report
    if not isinstance(nested, Mapping):
        raise ValueError("cohort Pareto report curve must be an object")
    return nested


def cohort_pareto_disposition(
    report: Mapping[str, Any],
    *,
    gate_config: Mapping[str, Any],
) -> dict[str, Any]:
    """Describe a skill increment against its paired parent library.

    The input uses the existing prequential curve shape: deltas follow the
    curve's declared direction and every endpoint contains a case-cluster
    bootstrap estimate.  ``gate_config`` is deliberately strict and must be
    frozen before outcomes are observed::

        {
          "schema_version": 1,
          "decision_rule": "case_cluster_pareto_noninferiority",
          "effect_direction": "current_library_minus_parent_library",
          "primary_endpoint": "unique_disclosed_facts_per_question",
          "protected_endpoints": ["unique_disclosed_facts"],
          "endpoint_rules": {
            "unique_disclosed_facts_per_question": {
              "direction": "higher", "margin": 0.0
            },
            "unique_disclosed_facts": {"direction": "higher", "margin": 0.0}
          }
        }

    For a higher-is-better endpoint the raw interval is already oriented; for a
    lower-is-better endpoint it is sign-flipped.  An endpoint passes only when
    its entire interval is no worse than ``-margin``.  It is harmful only when
    its entire interval is below that boundary, and otherwise is inconclusive.
    The increment is a Pareto pass only when every declared endpoint passes; harm
    takes precedence over inconclusive.  The function performs no rollout,
    persistence, registry mutation, or candidate-level attribution.
    """

    expected_config_fields = {
        "schema_version",
        "decision_rule",
        "effect_direction",
        "primary_endpoint",
        "protected_endpoints",
        "endpoint_rules",
    }
    if set(gate_config) != expected_config_fields:
        raise ValueError("cohort Pareto gate configuration fields drifted")
    schema_version = gate_config.get("schema_version")
    if (
        isinstance(schema_version, bool)
        or schema_version != COHORT_PARETO_DISPOSITION_SCHEMA
    ):
        raise ValueError("unsupported cohort Pareto gate schema")
    if gate_config.get("decision_rule") != COHORT_PARETO_DECISION_RULE:
        raise ValueError("unsupported cohort Pareto decision rule")

    effect_direction = gate_config.get("effect_direction")
    if effect_direction != COHORT_PARENT_EFFECT_DIRECTION:
        raise ValueError(
            "cohort Pareto gate must compare the current library with its parent library"
        )
    primary_endpoint = gate_config.get("primary_endpoint")
    if not isinstance(primary_endpoint, str) or not primary_endpoint.strip():
        raise ValueError("cohort Pareto primary_endpoint must be non-empty")
    protected_value = gate_config.get("protected_endpoints")
    if not isinstance(protected_value, Sequence) or isinstance(protected_value, (str, bytes)):
        raise ValueError("cohort Pareto protected_endpoints must be a sequence")
    protected_endpoints = list(protected_value)
    if (
        any(
            not isinstance(item, str) or not item.strip()
            for item in protected_endpoints
        )
        or primary_endpoint in protected_endpoints
        or len(protected_endpoints) != len(set(protected_endpoints))
    ):
        raise ValueError("cohort Pareto endpoints must be non-empty and unique by role")
    endpoint_names = [primary_endpoint, *protected_endpoints]

    rules_value = gate_config.get("endpoint_rules")
    if not isinstance(rules_value, Mapping) or set(rules_value) != set(endpoint_names):
        raise ValueError("cohort Pareto endpoint rules do not match declared endpoints")
    rules: dict[str, dict[str, Any]] = {}
    for endpoint in endpoint_names:
        rule = rules_value[endpoint]
        if not isinstance(rule, Mapping) or set(rule) != {"direction", "margin"}:
            raise ValueError(f"cohort Pareto endpoint rule fields drifted: {endpoint}")
        direction = rule.get("direction")
        if direction not in COHORT_ENDPOINT_DIRECTIONS:
            raise ValueError(f"cohort Pareto endpoint direction is invalid: {endpoint}")
        margin = _strict_finite_float(
            rule.get("margin"), field=f"cohort Pareto margin for {endpoint}"
        )
        if margin < 0:
            raise ValueError(f"cohort Pareto margin must be non-negative: {endpoint}")
        rules[endpoint] = {"direction": str(direction), "margin": margin}

    curve = _cohort_curve(report)
    if curve.get("direction") != effect_direction:
        raise ValueError("cohort Pareto curve effect direction does not match its gate")
    pair_count = _strict_positive_int(
        curve.get("pair_count"), field="cohort Pareto pair_count"
    )
    case_cluster_count = _strict_positive_int(
        curve.get("case_cluster_count"), field="cohort Pareto case_cluster_count"
    )
    if pair_count < case_cluster_count:
        raise ValueError("cohort Pareto pair_count cannot be smaller than case clusters")

    bootstrap = curve.get("bootstrap")
    if not isinstance(bootstrap, Mapping) or set(bootstrap) != {
        "unit",
        "samples",
        "confidence_level",
        "seed",
    }:
        raise ValueError("cohort Pareto bootstrap contract is invalid")
    if bootstrap.get("unit") != "case_id":
        raise ValueError("cohort Pareto disposition requires case_id bootstrap")
    bootstrap_samples = _strict_positive_int(
        bootstrap.get("samples"), field="cohort Pareto bootstrap samples"
    )
    bootstrap_seed = bootstrap.get("seed")
    if isinstance(bootstrap_seed, bool) or not isinstance(bootstrap_seed, int):
        raise ValueError("cohort Pareto bootstrap seed must be an integer")
    confidence_level = _strict_finite_float(
        bootstrap.get("confidence_level"),
        field="cohort Pareto bootstrap confidence_level",
    )
    if not 0.0 < confidence_level < 1.0:
        raise ValueError("cohort Pareto bootstrap confidence_level must be between zero and one")

    cases = curve.get("cases")
    pairs = curve.get("pairs")
    if not isinstance(cases, list) or len(cases) != case_cluster_count:
        raise ValueError("cohort Pareto case records do not match case_cluster_count")
    if not isinstance(pairs, list) or len(pairs) != pair_count:
        raise ValueError("cohort Pareto pair records do not match pair_count")
    case_ids: list[str] = []
    declared_pairs = 0
    for item in cases:
        if not isinstance(item, Mapping):
            raise ValueError("cohort Pareto case record must be an object")
        case_id = item.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            raise ValueError("cohort Pareto case record lacks case_id")
        case_ids.append(case_id)
        declared_pairs += _strict_positive_int(
            item.get("pair_count"), field=f"cohort Pareto case pair_count for {case_id}"
        )
    if len(case_ids) != len(set(case_ids)) or declared_pairs != pair_count:
        raise ValueError("cohort Pareto case records do not bind the paired matrix")
    pair_ids: list[str] = []
    paired_case_ids: set[str] = set()
    observed_pair_counts: dict[str, int] = defaultdict(int)
    for item in pairs:
        if not isinstance(item, Mapping):
            raise ValueError("cohort Pareto pair record must be an object")
        pair_id = item.get("pair_id")
        case_id = item.get("case_id")
        if not isinstance(pair_id, str) or not pair_id:
            raise ValueError("cohort Pareto pair record lacks pair_id")
        if not isinstance(case_id, str) or not case_id:
            raise ValueError("cohort Pareto pair record lacks case_id")
        pair_ids.append(pair_id)
        paired_case_ids.add(case_id)
        observed_pair_counts[case_id] += 1
    declared_pair_counts = {
        str(item["case_id"]): int(item["pair_count"])
        for item in cases
    }
    if (
        len(pair_ids) != len(set(pair_ids))
        or paired_case_ids != set(case_ids)
        or observed_pair_counts != declared_pair_counts
    ):
        raise ValueError("cohort Pareto pair records do not bind the declared cases")

    metrics = curve.get("metrics")
    if not isinstance(metrics, Mapping):
        raise ValueError("cohort Pareto curve metrics are missing")
    endpoint_dispositions: dict[str, dict[str, Any]] = {}
    for endpoint in endpoint_names:
        metric = metrics.get(endpoint)
        estimate = metric.get("case_cluster_estimate") if isinstance(metric, Mapping) else None
        if not isinstance(estimate, Mapping):
            raise ValueError(f"cohort Pareto endpoint estimate is missing: {endpoint}")
        required_estimate_fields = {
            "pairs",
            "mean_delta",
            "median_delta",
            "lower",
            "upper",
            "confidence_level",
            "bootstrap_samples",
            "seed",
        }
        if set(estimate) != required_estimate_fields:
            raise ValueError(f"cohort Pareto endpoint estimate fields drifted: {endpoint}")
        estimate_pairs = _strict_positive_int(
            estimate.get("pairs"), field=f"cohort Pareto estimate pairs for {endpoint}"
        )
        estimate_samples = _strict_positive_int(
            estimate.get("bootstrap_samples"),
            field=f"cohort Pareto estimate bootstrap samples for {endpoint}",
        )
        estimate_seed = estimate.get("seed")
        if isinstance(estimate_seed, bool) or not isinstance(estimate_seed, int):
            raise ValueError(f"cohort Pareto estimate seed must be an integer: {endpoint}")
        numeric = {
            field: _strict_finite_float(
                estimate.get(field), field=f"cohort Pareto {field} for {endpoint}"
            )
            for field in (
                "mean_delta",
                "median_delta",
                "lower",
                "upper",
                "confidence_level",
            )
        }
        if (
            estimate_pairs != case_cluster_count
            or estimate_samples != bootstrap_samples
            or estimate_seed != bootstrap_seed
            or numeric["confidence_level"] != confidence_level
        ):
            raise ValueError(f"cohort Pareto case-bootstrap binding drifted: {endpoint}")
        if numeric["lower"] > numeric["upper"]:
            raise ValueError(f"cohort Pareto interval is reversed: {endpoint}")

        direction = rules[endpoint]["direction"]
        if direction == "higher":
            oriented_mean = numeric["mean_delta"]
            oriented_median = numeric["median_delta"]
            oriented_lower = numeric["lower"]
            oriented_upper = numeric["upper"]
        else:
            oriented_mean = -numeric["mean_delta"]
            oriented_median = -numeric["median_delta"]
            oriented_lower = -numeric["upper"]
            oriented_upper = -numeric["lower"]
        margin = float(rules[endpoint]["margin"])
        threshold = -margin
        endpoint_decision = (
            "pass"
            if oriented_lower >= threshold
            else "harm"
            if oriented_upper < threshold
            else "inconclusive"
        )
        endpoint_dispositions[endpoint] = {
            "role": "primary" if endpoint == primary_endpoint else "protected",
            "direction": direction,
            "noninferiority_margin": margin,
            "noninferiority_threshold": threshold,
            "raw_estimate": {
                "mean_delta": numeric["mean_delta"],
                "median_delta": numeric["median_delta"],
                "lower": numeric["lower"],
                "upper": numeric["upper"],
            },
            "oriented_estimate": {
                "mean_delta": 0.0 if oriented_mean == 0 else oriented_mean,
                "median_delta": 0.0 if oriented_median == 0 else oriented_median,
                "lower": 0.0 if oriented_lower == 0 else oriented_lower,
                "upper": 0.0 if oriented_upper == 0 else oriented_upper,
            },
            "decision": endpoint_decision,
        }

    harmed = [
        endpoint
        for endpoint in endpoint_names
        if endpoint_dispositions[endpoint]["decision"] == "harm"
    ]
    inconclusive = [
        endpoint
        for endpoint in endpoint_names
        if endpoint_dispositions[endpoint]["decision"] == "inconclusive"
    ]
    decision = "harm" if harmed else "inconclusive" if inconclusive else "pass"
    return {
        "schema_version": COHORT_PARETO_DISPOSITION_SCHEMA,
        "scope": "new_skill_increment_against_parent_library",
        "decision_rule": COHORT_PARETO_DECISION_RULE,
        "effect_direction": effect_direction,
        "bootstrap_unit": "case_id",
        "interval_scope": "per_endpoint_case_cluster_bootstrap",
        "simultaneous_familywise_control": False,
        "candidate_level_effect_claim": False,
        "primary_endpoint": primary_endpoint,
        "protected_endpoints": protected_endpoints,
        "gate_config_sha256": canonical_json_sha256(_json_value(dict(gate_config))),
        "endpoint_dispositions": endpoint_dispositions,
        "harmed_endpoints": harmed,
        "inconclusive_endpoints": inconclusive,
        "decision": decision,
        "interval_noninferiority_passed": decision == "pass",
    }
