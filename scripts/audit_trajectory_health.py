#!/usr/bin/env python3
"""Audit process-health invariants over persisted research trajectories."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

from legal_skill_guard.agent.memo_health import memo_health_violations
from legal_skill_guard.agent.stateful_policy import action_question_quality_violations
from legal_skill_guard.environment.client_response import (
    disclosed_fact_indices,
    opening_fact_candidates,
    response_violations,
)
from legal_skill_guard.evaluation.semantic import POLICY_FALLBACK_REASONS
from legal_skill_guard.schemas.action import StructuredAction
from legal_skill_guard.schemas.state import NON_SUBSTANTIVE_FACT_IDS

ROOT = Path(__file__).resolve().parents[1]
SOURCE_MANIFEST = ROOT / "data/manifests/dlawbench_source.json"


def load_client_beliefs() -> dict[str, list[str]]:
    """Load pinned beliefs for offline grounding audit; never used by online agents."""

    sources: list[Path] = []
    if SOURCE_MANIFEST.is_file():
        manifest = json.loads(SOURCE_MANIFEST.read_text(encoding="utf-8"))
        sources.append(
            ROOT / manifest["snapshot"] / "data/case_backgrounds/cases_cn.jsonl"
        )
    sources.append(ROOT / "data/training/legal_skill_guard_dlawbench_style_cn.jsonl")
    beliefs: dict[str, list[str]] = {}
    for source in sources:
        if not source.is_file():
            continue
        for line in source.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            beliefs[str(record["id"])] = [
                str(fact["client_belief"]) for fact in record.get("facts", [])
            ]
    return beliefs


CLIENT_BELIEFS = load_client_beliefs()
REPEATED_RESPONSE_MARKERS = ("已经说明", "已经说过", "刚才说过")
UNAVAILABLE_RESPONSE_MARKERS = ("不知道", "不清楚", "不太确定", "没有这项具体情况")


def normalized(value: str) -> str:
    return re.sub(r"[\W_]+", "", value).lower()


def audit(paths: list[Path]) -> dict[str, object]:
    metrics: Counter[str] = Counter()
    examples: dict[str, list[dict[str, object]]] = {}

    def record(metric: str, path: Path, turn: int, value: object) -> None:
        metrics[metric] += 1
        if len(examples.setdefault(metric, [])) < 10:
            examples[metric].append({"trajectory": str(path), "turn": turn, "value": value})

    for path in paths:
        trajectory = json.loads(path.read_text(encoding="utf-8"))
        metrics["trajectories"] += 1
        if trajectory.get("planning_safe_partial"):
            metrics["planner_safe_partial_trajectories"] += 1
        if trajectory.get("opening_agenda_safe_partial"):
            metrics["opening_agenda_safe_partial_trajectories"] += 1
        hidden_beliefs = CLIENT_BELIEFS.get(str(trajectory.get("case_id") or ""))
        opening_facts = opening_fact_candidates(str(trajectory.get("opening") or ""))
        opening_beliefs = {
            str(item["fact_id"]): str(item["client_belief"]) for item in opening_facts
        }
        grounding_history: list[tuple[str, str]] = []
        disclosed_hidden_ids: set[str] = set()
        visible_text = (
            trajectory.get("opening", "")
            + "\n"
            + "\n".join(str(step.get("client_response") or "") for step in trajectory["steps"])
        )
        memo_issues = memo_health_violations(trajectory.get("memo", ""), visible_text)
        for issue in memo_issues:
            record(f"memo_{issue}", path, 0, trajectory.get("memo", ""))
        if trajectory.get("memo_safe_fallback"):
            metrics["memo_safe_fallback_trajectories"] += 1
        metrics["memo_attempts"] += len(trajectory.get("memo_attempts", []))
        seen_questions: set[str] = set()
        for step in trajectory["steps"]:
            metrics["steps"] += 1
            turn = int(step["turn"])
            attempts = step.get("policy_attempts", [])
            metrics["policy_attempts"] += len(attempts)
            metrics["policy_repair_attempts"] += max(0, len(attempts) - 1)
            proposed_reason = step.get("proposed_action", {}).get("reason")
            final_reason = step.get("action_decision", {}).get("final", {}).get("reason")
            post_skill_fallback = any(
                change.get("source") == "post_skill_health_gate"
                and isinstance(change.get("after"), dict)
                and change["after"].get("reason") in POLICY_FALLBACK_REASONS
                for change in step.get("action_decision", {}).get("changes", [])
            )
            if (
                proposed_reason in POLICY_FALLBACK_REASONS
                or final_reason in POLICY_FALLBACK_REASONS
                or post_skill_fallback
            ):
                metrics["policy_safe_fallback_steps"] += 1
            for change in step.get("action_decision", {}).get("changes", []):
                if change.get("skill_id") == "system.question_quality_guard":
                    metrics["question_quality_guard_steps"] += 1
            for observation in step.get("state_patch", {}).get("observations", []):
                if observation.get("fact_id") in NON_SUBSTANTIVE_FACT_IDS:
                    record("management_fact_patches", path, turn, observation.get("fact_id"))
            question = step.get("rendered_question")
            if question:
                metrics["questions"] += 1
                question_key = normalized(question)
                if question_key in seen_questions:
                    record("exact_repeated_questions", path, turn, question)
                seen_questions.add(question_key)
                if re.search(r"[a-z]+_[a-z_]+", question):
                    record("snake_case_questions", path, turn, question)
                if question.startswith("请补充一个尚未说明"):
                    record("generic_fallback_questions", path, turn, question)
                quality = action_question_quality_violations(
                    StructuredAction(action_type="ask", content=question)
                )
                for issue in quality:
                    record(issue, path, turn, question)
            client_response = step.get("client_response")
            if client_response is not None:
                metrics["client_selection_attempts"] += len(
                    step.get("client_selection_attempts", [])
                )
                if step.get("client_safe_fallback"):
                    metrics["client_safe_fallback_steps"] += 1
                selected_ids = [str(item) for item in step.get("client_selected_fact_ids", [])]
                opening_ids = [
                    str(item) for item in step.get("client_opening_reference_ids", [])
                ]
                response_kind = step.get("client_response_kind")
                route_valid = step.get("client_route_decision_valid")
                if route_valid is None:
                    route_valid = step.get("client_relevance_passed")
                protocol12 = int(trajectory.get("schema_version") or 0) >= 12
                if len(selected_ids) > 1:
                    record(
                        "client_multiple_selected_facts",
                        path,
                        turn,
                        step.get("client_selected_fact_ids"),
                    )
                if response_kind in {
                    "new_hidden_fact",
                    "repeated_hidden_fact",
                    "opening_repeat",
                    "withheld",
                } and route_valid is not True:
                    record(
                        "client_selected_fact_without_valid_route",
                        path,
                        turn,
                        {
                            "selected": (selected_ids or opening_ids or [None])[0],
                            "route_valid": route_valid,
                        },
                    )
                if protocol12:
                    expected_shape = {
                        "new_hidden_fact": (1, 0),
                        "repeated_hidden_fact": (1, 0),
                        "opening_repeat": (0, 1),
                        "withheld": (0, 0),
                        "unavailable": (0, 0),
                        "contract_fallback": (0, 0),
                    }.get(str(response_kind or ""))
                    if expected_shape != (len(selected_ids), len(opening_ids)):
                        record(
                            "client_response_provenance_mismatch",
                            path,
                            turn,
                            {
                                "kind": response_kind,
                                "hidden": selected_ids,
                                "opening": opening_ids,
                            },
                        )
                    if any(item.startswith("O") for item in selected_ids):
                        record(
                            "public_opening_recorded_as_hidden_disclosure",
                            path,
                            turn,
                            selected_ids,
                        )
                    if response_kind in {"opening_repeat", "repeated_hidden_fact"}:
                        record(
                            "client_semantic_repetition_no_new_information",
                            path,
                            turn,
                            {
                                "selected": (selected_ids or opening_ids or [None])[0],
                                "question": question,
                            },
                        )
                    if (
                        response_kind == "repeated_hidden_fact"
                        and selected_ids
                        and selected_ids[0] not in disclosed_hidden_ids
                    ):
                        record(
                            "client_undisclosed_fact_marked_repeated",
                            path,
                            turn,
                            selected_ids[0],
                        )
                    if response_kind == "opening_repeat" and opening_ids:
                        belief = opening_beliefs.get(opening_ids[0], "")
                        if not belief or belief not in client_response:
                            record(
                                "client_response_not_grounded_in_opening_belief",
                                path,
                                turn,
                                {"selected": opening_ids[0], "response": client_response},
                            )
                    if response_kind == "new_hidden_fact" and selected_ids:
                        if selected_ids[0] in disclosed_hidden_ids:
                            record(
                                "client_repeated_fact_marked_new",
                                path,
                                turn,
                                selected_ids[0],
                            )
                        if hidden_beliefs:
                            try:
                                belief = hidden_beliefs[int(selected_ids[0][1:]) - 1]
                            except (ValueError, IndexError):
                                belief = ""
                            if not belief or belief not in client_response:
                                record(
                                    "client_response_not_grounded_in_selected_belief",
                                    path,
                                    turn,
                                    {"selected": selected_ids[0], "response": client_response},
                                )
                        disclosed_hidden_ids.add(selected_ids[0])
                    if response_kind == "withheld":
                        final_action = step.get("action_decision", {}).get("final", {})
                        target_id = str(final_action.get("target_id") or "")
                        state_after = step.get("state_after", {})
                        after_facts = {
                            str(item.get("fact_id") or ""): item
                            for item in state_after.get("facts", [])
                            if isinstance(item, dict)
                        }
                        after_asked = {
                            str(item) for item in state_after.get("asked_targets", [])
                        }
                        if not target_id or target_id not in after_facts:
                            record(
                                "client_withheld_target_missing_from_state",
                                path,
                                turn,
                                target_id,
                            )
                        else:
                            after_target = after_facts[target_id]
                            if after_target.get("status") != "unknown":
                                record(
                                    "client_withheld_target_state_changed",
                                    path,
                                    turn,
                                    {
                                        "target_id": target_id,
                                        "status": after_target.get("status"),
                                    },
                                )
                            if target_id in after_asked:
                                record(
                                    "client_withheld_target_marked_asked",
                                    path,
                                    turn,
                                    target_id,
                                )
                        matching_interactions = [
                            item
                            for item in state_after.get("interactions", [])
                            if isinstance(item, dict)
                            and item.get("turn") == turn
                            and item.get("target_id") == target_id
                        ]
                        persisted_interaction = (
                            matching_interactions[-1]
                            if matching_interactions
                            else None
                        )
                        if (
                            persisted_interaction is None
                            or persisted_interaction.get("response_kind") != "withheld"
                            or bool(persisted_interaction.get("new_information"))
                            or bool(persisted_interaction.get("disclosed_fact_ids"))
                        ):
                            record(
                                "client_withheld_interaction_provenance_mismatch",
                                path,
                                turn,
                                persisted_interaction,
                            )
                    if (response_kind == "contract_fallback") != bool(
                        step.get("client_safe_fallback")
                    ):
                        record(
                            "client_fallback_provenance_mismatch",
                            path,
                            turn,
                            response_kind,
                        )
                elif selected_ids and (
                    selected_ids[0] in opening_beliefs or hidden_beliefs is not None
                ):
                    selected_id = str(selected_ids[0])
                    combined_records = [
                        *opening_facts,
                        *(
                            [
                                {"fact_id": f"F{index}", "client_belief": belief}
                                for index, belief in enumerate(hidden_beliefs, start=1)
                            ]
                            if hidden_beliefs is not None
                            else []
                        ),
                    ]
                    selected_index = next(
                        (
                            index
                            for index, item in enumerate(combined_records)
                            if str(item["fact_id"]) == selected_id
                        ),
                        -1,
                    )
                    if selected_index >= 0:
                        beliefs = [str(item["client_belief"]) for item in combined_records]
                        disclosed_before = disclosed_fact_indices(
                            combined_records,
                            grounding_history,
                        )
                        grounded = beliefs[selected_index] in client_response
                        repeated = selected_index in disclosed_before and any(
                            marker in client_response for marker in REPEATED_RESPONSE_MARKERS
                        )
                        if repeated:
                            record(
                                "client_semantic_repetition_no_new_information",
                                path,
                                turn,
                                {"selected": selected_id, "question": question},
                            )
                        if not grounded and not repeated:
                            record(
                                "client_response_not_grounded_in_selected_belief",
                                path,
                                turn,
                                {
                                    "selected": selected_id,
                                    "response": client_response,
                                },
                            )
                    else:
                        record(
                            "client_invalid_selected_fact_id",
                            path,
                            turn,
                            selected_ids[0],
                        )
                elif not protocol12 and (
                    hidden_beliefs is not None
                    and not selected_ids
                    and not any(
                        marker in client_response for marker in UNAVAILABLE_RESPONSE_MARKERS
                    )
                ):
                    record(
                        "client_ungrounded_empty_selection_response",
                        path,
                        turn,
                        client_response,
                    )
                grounding_history.append((str(question or ""), str(client_response)))
                if re.search(r"[a-z]+_[a-z_]+", client_response):
                    record("snake_case_client_responses", path, turn, client_response)
                for issue in response_violations(client_response):
                    record(f"client_{issue}", path, turn, client_response)
            for result in step.get("verifier_results", []):
                if not result["passed"]:
                    record("verifier_failures", path, turn, result["validator_id"])
                    if result["severity"] == "severe":
                        record("severe_verifier_failures", path, turn, result["validator_id"])
    hard_metrics = (
        "management_fact_patches",
        "exact_repeated_questions",
        "snake_case_questions",
        "snake_case_client_responses",
        "client_multiple_selected_facts",
        "public_opening_recorded_as_hidden_disclosure",
        "generic_fallback_questions",
        "generic_or_abstract_question",
        "excessive_phrase_repetition",
        "question_requests_legal_judgment_from_client",
        "multiple_primary_questions",
        "verifier_failures",
        "severe_verifier_failures",
    )
    hard_failures = {key: metrics[key] for key in hard_metrics if metrics[key]}
    hard_failures.update(
        {
            key: value
            for key, value in metrics.items()
            if key.startswith("client_")
            and key
            not in {
                "client_selection_attempts",
                "client_safe_fallback_steps",
                # This remains in metrics/examples and in reward penalties, but it is
                # learnable policy quality rather than a corrupt execution trace.
                "client_semantic_repetition_no_new_information",
            }
            and value
        }
    )
    hard_failures.update(
        {
            key: value
            for key, value in metrics.items()
            if key.startswith("memo_")
            and key not in {"memo_attempts", "memo_safe_fallback_trajectories"}
            and value
        }
    )
    return {
        "schema_version": 2,
        "metrics": dict(sorted(metrics.items())),
        "hard_failures": hard_failures,
        "healthy": not hard_failures,
        "examples": examples,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trajectory_root", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    paths = sorted(args.trajectory_root.glob("*/*.json"))
    if not paths:
        paths = sorted(args.trajectory_root.glob("*.json"))
    if not paths:
        raise RuntimeError(f"No trajectory JSON files found under {args.trajectory_root}")
    result = audit(paths)
    serialized = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized, encoding="utf-8")
    print(serialized, end="")
    if not result["healthy"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
