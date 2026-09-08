#!/usr/bin/env python3
"""Audit whether grouped training rollouts contain usable policy contrasts.

This is a training-only diagnostic.  It deliberately does not call the semantic
judge or skill teacher and does not approximate a paper reward.  Instead it reports
the narrower prerequisite for TF-GRPO-style learning: group members must reach an
executable shared visible state, choose different actions there, and the positive
continuation must actually elicit more unique hidden facts.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from itertools import permutations
from pathlib import Path

from legal_skill_guard.evaluation.semantic import derive_mechanism_signals
from legal_skill_guard.experiment.executor import (
    _causal_state_signature,
    _learnable_action_signature,
    trajectory_learning_signature,
)
from legal_skill_guard.schemas.experiment import ResearchTrajectory
from legal_skill_guard.utils.hashing import canonical_json_sha256, sha256_file


def _elicited_fact_ids(trajectory: ResearchTrajectory) -> set[str]:
    return {
        fact_id
        for step in trajectory.steps
        if step.client_response_kind == "new_hidden_fact"
        for fact_id in step.client_selected_fact_ids
    }


def _first_shared_state_fork(
    positive: ResearchTrajectory, negative: ResearchTrajectory
) -> tuple[int, str] | None:
    for positive_step, negative_step in zip(positive.steps, negative.steps, strict=False):
        if positive_step.turn != negative_step.turn:
            return None
        if _causal_state_signature(positive_step) != _causal_state_signature(negative_step):
            return None
        if _learnable_action_signature(positive_step) == _learnable_action_signature(negative_step):
            continue
        positive_type = positive_step.proposed_action.action_type
        negative_type = negative_step.proposed_action.action_type
        if negative_type in {"final", "abstain"} and positive_type not in {
            "final",
            "abstain",
        }:
            kind = "early_terminal_to_inquiry"
        elif positive_type in {"final", "abstain"} and negative_type not in {
            "final",
            "abstain",
        }:
            kind = "inquiry_to_early_terminal"
        else:
            kind = "different_inquiry_policy"
        return positive_step.turn, kind
    return None


def analyze(
    root: Path,
    *,
    case_ids: set[str] | None = None,
    samples_per_group: int | None = None,
    partitions: set[str] | None = None,
) -> dict[str, object]:
    paths = sorted((root / "trajectories").rglob("*.json"))
    loaded = [
        (path, ResearchTrajectory.model_validate_json(path.read_text(encoding="utf-8")))
        for path in paths
    ]
    selected = [
        (path, trajectory)
        for path, trajectory in loaded
        if (case_ids is None or trajectory.case_id in case_ids)
        and (partitions is None or trajectory.partition in partitions)
        and (samples_per_group is None or trajectory.sample_index < samples_per_group)
    ]
    paths = [path for path, _ in selected]
    trajectories = [trajectory for _, trajectory in selected]
    mechanism_signals = {
        trajectory.trajectory_id: derive_mechanism_signals(trajectory)
        for trajectory in trajectories
    }
    groups: dict[str, list[ResearchTrajectory]] = defaultdict(list)
    for trajectory in trajectories:
        groups[trajectory.group_id or trajectory.trajectory_id].append(trajectory)

    response_kinds: Counter[str] = Counter()
    policy_repairs = 0
    policy_fallback_steps = 0
    client_fallback_steps = 0
    questions = 0
    new_fact_events = 0
    for trajectory in trajectories:
        for step in trajectory.steps:
            questions += step.rendered_question is not None
            policy_repairs += max(0, len(step.policy_attempts) - 1)
            policy_fallback_steps += bool(step.action_decision.changes)
            client_fallback_steps += step.client_safe_fallback
            if step.client_response_kind:
                response_kinds[step.client_response_kind] += 1
            if step.client_response_kind == "new_hidden_fact":
                new_fact_events += len(step.client_selected_fact_ids)

    identical_groups = 0
    shared_state_fork_groups = 0
    fact_gain_fork_groups = 0
    direct_information_fork_groups = 0
    fork_kinds: Counter[str] = Counter()
    direct_fork_kinds: Counter[str] = Counter()
    source_cases: set[str] = set()
    source_domains: set[str] = set()
    direct_source_cases: set[str] = set()
    direct_source_domains: set[str] = set()
    details: list[dict[str, object]] = []
    direct_details: list[dict[str, object]] = []
    for group_id, members in sorted(groups.items()):
        signatures = {trajectory_learning_signature(item) for item in members}
        if len(signatures) == 1:
            identical_groups += 1
        any_fork = False
        best: tuple[int, int, str, str, int, str] | None = None
        best_direct: tuple[int, int, int, str, str, int, str] | None = None
        for positive, negative in permutations(members, 2):
            positive_fact_ids = _elicited_fact_ids(positive)
            negative_fact_ids = _elicited_fact_ids(negative)
            positive_count = len(positive_fact_ids)
            negative_count = len(negative_fact_ids)
            fork = _first_shared_state_fork(positive, negative)
            if fork is None:
                continue
            any_fork = True
            turn, kind = fork
            if positive_count > negative_count:
                candidate = (
                    positive_count - negative_count,
                    -turn,
                    positive.trajectory_id,
                    negative.trajectory_id,
                    turn,
                    kind,
                )
                if best is None or candidate > best:
                    best = candidate
            positive_step = next(
                (step for step in positive.steps if step.turn == turn), None
            )
            negative_step = next(
                (step for step in negative.steps if step.turn == turn), None
            )
            state_before = positive_step.state_before if positive_step is not None else {}
            negative_zero_information = bool(
                negative_step is not None
                and (
                    (
                        negative_step.client_response_kind
                        in {"unavailable", "opening_repeat", "repeated_hidden_fact"}
                        and negative_step.turn
                        not in set(
                            mechanism_signals[
                                negative.trajectory_id
                            ].identified_evidence_gap_turns
                        )
                    )
                    or (
                        negative_step.action_decision.final.action_type
                        in {"final", "abstain"}
                        and negative_step.client_response_kind is None
                    )
                )
                and not negative_step.client_selected_fact_ids
            )
            # Mirror the structural part of production selection.  The positive
            # branch must obtain information at the actual same-state action fork,
            # the negative branch must obtain none, and the positive trajectory
            # may be caught later but must not finish with less unique coverage.
            direct_information = bool(
                positive_step is not None
                and positive_fact_ids.issuperset(negative_fact_ids)
                and int(state_before.get("high_critical_unknown_count") or 0) > 0
                and int(state_before.get("unavailable_turn_count") or 0) == 0
                and positive_step.client_response_kind == "new_hidden_fact"
                and positive_step.client_selected_fact_ids
                and negative_zero_information
                and (
                    not (positive_fact_ids - negative_fact_ids)
                    or (positive_fact_ids - negative_fact_ids).issubset(
                        set(positive_step.client_selected_fact_ids)
                    )
                )
            )
            if direct_information:
                direct_candidate = (
                    len(positive_step.client_selected_fact_ids),
                    len(positive_fact_ids - negative_fact_ids),
                    -turn,
                    positive.trajectory_id,
                    negative.trajectory_id,
                    turn,
                    kind,
                )
                if best_direct is None or direct_candidate > best_direct:
                    best_direct = direct_candidate
        shared_state_fork_groups += any_fork
        exemplar = members[0]
        if best is not None:
            fact_gain_fork_groups += 1
            fact_gain, _, positive_id, negative_id, turn, kind = best
            source_cases.add(exemplar.case_id)
            source_domains.add(exemplar.domain)
            fork_kinds[kind] += 1
            details.append(
                {
                    "group_id": group_id,
                    "case_id": exemplar.case_id,
                    "domain": exemplar.domain,
                    "persona": exemplar.persona,
                    "positive_trajectory_id": positive_id,
                    "negative_trajectory_id": negative_id,
                    "divergence_turn": turn,
                    "unique_fact_gain": fact_gain,
                    "fork_kind": kind,
                }
            )
        if best_direct is not None:
            direct_information_fork_groups += 1
            (
                immediate_gain,
                eventual_gain,
                _,
                direct_positive_id,
                direct_negative_id,
                direct_turn,
                direct_kind,
            ) = best_direct
            direct_source_cases.add(exemplar.case_id)
            direct_source_domains.add(exemplar.domain)
            direct_fork_kinds[direct_kind] += 1
            direct_details.append(
                {
                    "group_id": group_id,
                    "case_id": exemplar.case_id,
                    "domain": exemplar.domain,
                    "persona": exemplar.persona,
                    "positive_trajectory_id": direct_positive_id,
                    "negative_trajectory_id": direct_negative_id,
                    "divergence_turn": direct_turn,
                    "immediate_fact_gain": immediate_gain,
                    "eventual_unique_fact_gain": eventual_gain,
                    "fork_kind": direct_kind,
                    "qualification_context": {
                        "high_critical_unknown_count": "gt_0",
                        "unavailable_turn_count": "eq_0",
                        "divergent_inquiry_response": "new_hidden_fact",
                    },
                }
            )

    artifact_hashes = {str(path.relative_to(root)): sha256_file(path) for path in paths}
    group_count = len(groups)
    target_kind_ready = [
        item for item in mechanism_signals.values() if item.target_kind_available
    ]
    classified_evidence_targets = sum(
        int(item.evidence_or_third_party_target_count or 0)
        for item in target_kind_ready
    )
    eligible_evidence_denominator = sum(
        int(item.eligible_evidence_inquiry_count or 0)
        for item in target_kind_ready
    )
    identified_evidence_gaps = sum(
        item.identified_evidence_gap_count for item in target_kind_ready
    )
    newly_elicited_facts = sum(
        item.newly_elicited_fact_count for item in mechanism_signals.values()
    )
    ordinary_unavailable_turns = max(
        int(response_kinds["unavailable"]) - identified_evidence_gaps,
        0,
    )
    return {
        "schema_version": 3,
        "run_id": root.name,
        "scope": "training_only_structural_sampling_diagnostic",
        "case_filter": sorted(case_ids) if case_ids is not None else None,
        "partition_filter": sorted(partitions) if partitions is not None else None,
        "samples_per_group_filter": samples_per_group,
        "semantic_judge_called": False,
        "skill_teacher_called": False,
        "trajectory_count": len(trajectories),
        "group_count": group_count,
        "group_sizes": dict(sorted(Counter(map(len, groups.values())).items())),
        "identical_learning_trace_groups": identical_groups,
        "identical_learning_trace_rate": round(identical_groups / group_count, 6)
        if group_count
        else None,
        "shared_state_policy_fork_groups": shared_state_fork_groups,
        "shared_state_policy_fork_rate": round(shared_state_fork_groups / group_count, 6)
        if group_count
        else None,
        "shared_state_fact_gain_fork_groups": fact_gain_fork_groups,
        "shared_state_fact_gain_fork_rate": round(fact_gain_fork_groups / group_count, 6)
        if group_count
        else None,
        "fact_gain_source_cases": sorted(source_cases),
        "fact_gain_source_case_count": len(source_cases),
        "fact_gain_source_domains": sorted(source_domains),
        "fact_gain_source_domain_count": len(source_domains),
        "fork_kinds": dict(sorted(fork_kinds.items())),
        "direct_information_fork_groups": direct_information_fork_groups,
        "direct_information_fork_rate": round(
            direct_information_fork_groups / group_count, 6
        )
        if group_count
        else None,
        "direct_information_source_cases": sorted(direct_source_cases),
        "direct_information_source_case_count": len(direct_source_cases),
        "direct_information_source_domains": sorted(direct_source_domains),
        "direct_information_source_domain_count": len(direct_source_domains),
        "direct_information_fork_kinds": dict(sorted(direct_fork_kinds.items())),
        "statuses": dict(sorted(Counter(item.status for item in trajectories).items())),
        "questions": questions,
        "new_hidden_fact_events": new_fact_events,
        "client_response_kinds": dict(sorted(response_kinds.items())),
        "mechanism_signals": {
            "definition": (
                "F=new_hidden_fact benchmark IDs; E=clean first ask/clarify/verify "
                "of an evidence_or_third_party target with a non-withheld outcome; "
                "G=E returning unavailable. G is not an ordinary zero-information "
                "branch."
            ),
            "newly_elicited_fact_count": newly_elicited_facts,
            "classified_evidence_or_third_party_target_count": (
                classified_evidence_targets if target_kind_ready else None
            ),
            "eligible_evidence_inquiry_count": (
                eligible_evidence_denominator if target_kind_ready else None
            ),
            "identified_evidence_gap_count": identified_evidence_gaps,
            "f_or_g_signal_count": newly_elicited_facts + identified_evidence_gaps,
            "f_or_g_signal_per_question": (
                round(
                    (newly_elicited_facts + identified_evidence_gaps) / questions,
                    6,
                )
                if questions
                else None
            ),
            "identified_evidence_gap_rate": (
                round(identified_evidence_gaps / eligible_evidence_denominator, 6)
                if eligible_evidence_denominator
                else None
            ),
            "ordinary_unavailable_turns_excluding_identified_evidence_gaps": (
                ordinary_unavailable_turns
            ),
            "target_kind_available_trajectories": len(target_kind_ready),
            "target_kind_unavailable_legacy_trajectories": (
                len(mechanism_signals) - len(target_kind_ready)
            ),
            "trajectories_with_identified_evidence_gaps": sum(
                item.evidence_gap_outcome == "identified"
                for item in target_kind_ready
            ),
            "true_zero_trajectories": sum(
                item.evidence_gap_outcome == "true_zero"
                for item in target_kind_ready
            ),
            "not_applicable_no_eligible_evidence_inquiry_trajectories": sum(
                item.evidence_gap_outcome
                == "not_applicable_no_eligible_evidence_inquiries"
                for item in target_kind_ready
            ),
            "identified_evidence_gap_ids_by_trajectory": {
                trajectory_id: item.identified_evidence_gap_ids
                for trajectory_id, item in sorted(mechanism_signals.items())
                if item.identified_evidence_gap_ids
            },
            "true_zero_trajectory_ids": sorted(
                trajectory_id
                for trajectory_id, item in mechanism_signals.items()
                if item.evidence_gap_outcome == "true_zero"
            ),
            "rate_note": (
                "The denominator is the sum of clean, first, non-withheld E "
                "inquiries over protocol-15 trajectories; null means no reliable/"
                "nonzero E denominator, not a measured zero."
            ),
        },
        "policy_repairs": policy_repairs,
        "policy_fallback_steps": policy_fallback_steps,
        "client_fallback_steps": client_fallback_steps,
        "planning_safe_partial_trajectories": sum(
            item.planning_safe_partial for item in trajectories
        ),
        "memo_safe_fallback_trajectories": sum(item.memo_safe_fallback for item in trajectories),
        "trajectory_set_sha256": canonical_json_sha256(artifact_hashes),
        "fact_gain_forks": details,
        "direct_information_forks": direct_details,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_root", type=Path)
    parser.add_argument("--case-id", action="append", dest="case_ids")
    parser.add_argument("--partition", action="append", dest="partitions")
    parser.add_argument("--samples-per-group", type=int)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.samples_per_group is not None and args.samples_per_group < 1:
        raise SystemExit("samples-per-group must be positive")
    report = analyze(
        args.run_root,
        case_ids=set(args.case_ids) if args.case_ids else None,
        samples_per_group=args.samples_per_group,
        partitions=set(args.partitions) if args.partitions else None,
    )
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
