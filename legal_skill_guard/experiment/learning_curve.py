"""Pure, paired prequential learning-curve statistics for training sentinels.

The module deliberately performs no rollout, persistence, candidate admission, or
configuration lookup.  A caller supplies already-scored current-library and
empty-library trajectories.  This keeps the descriptive learning curve separate
from the candidate lifecycle.  It verifies matched initial infrastructure while
leaving stepwise sole-intervention auditing to the executor's pre-scoring gate.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from collections.abc import Mapping, Sequence, Set
from typing import Any, Final

from legal_skill_guard.evaluation.semantic import TrajectoryEvaluation
from legal_skill_guard.evaluation.statistics import paired_bootstrap_interval
from legal_skill_guard.schemas.experiment import ResearchTrajectory
from legal_skill_guard.utils.hashing import canonical_json_sha256

# Keep this definition outside executor.py so the executor can import the pure
# statistic without creating a circular dependency.  These are the six frozen
# development-curve endpoints already used by the experiment.
DEVELOPMENT_CURVE_METRICS: Final[tuple[tuple[str, str], ...]] = (
    ("official_metrics", "resolution"),
    ("official_metrics", "elicitation"),
    ("official_metrics", "fidelity"),
    ("safety_metrics", "critical_fact_recall"),
    ("safety_metrics", "repeated_question_rate"),
    ("operational_metrics", "policy_fallback_rate"),
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
CURRENT_LIBRARY_METHOD: Final[str] = "legal_skill_guard"
TRAINING_SENTINEL_METHODS: Final[frozenset[str]] = frozenset(
    {"training_policy_sample", "candidate_without"}
)
IDENTITY_BASELINE_METHODS: Final[frozenset[str]] = frozenset(
    {*TRAINING_SENTINEL_METHODS, EMPTY_LIBRARY_METHOD, CURRENT_LIBRARY_METHOD}
)
METHOD_COMPATIBLE_PAIRS: Final[frozenset[tuple[str, str]]] = frozenset(
    {
        ("training_policy_sample", "training_policy_sample"),
        ("candidate_without", "candidate_without"),
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
    "initial_investigation_plan",
    "planning_attempts",
    "planning_safe_partial",
    "initial_visible_state_coverage_attempts",
    "initial_visible_state_covered_target_ids",
    "initial_visible_state_coverage_token_usage",
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
        if any(step.action_decision.activated_skill_ids for step in trajectory.steps):
            raise ValueError(f"{arm} used the retired runtime skill executor")
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
        if _json_value(getattr(empty_trajectory, field))
        != _json_value(getattr(current_trajectory, field))
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
        field: float(getattr(getattr(evaluation, section), field))
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
    identity or pre-policy infrastructure drift.
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
            "method_pairs": sorted(
                {
                    (
                        str(current_trajectory.method),
                        str(empty_trajectory.method),
                    )
                    for _, current_trajectory, _, empty_trajectory, _ in paired
                }
            ),
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
