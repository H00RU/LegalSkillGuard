from pathlib import Path

import pytest

from legal_skill_guard.evolution.acceptance import (
    AcceptanceThresholds,
    PairOutcome,
    decide_skill,
    global_regression_passes,
)
from legal_skill_guard.evolution.advantage import (
    ScoredMember,
    compute_advantages,
    select_contrasts,
)
from legal_skill_guard.evolution.diagnosis import parse_diagnosis
from legal_skill_guard.evolution.reward import (
    RewardComponents,
    proposed_final_was_redirected,
    trajectory_reward,
)
from legal_skill_guard.skills.registry import SkillRegistry


def test_reward_applies_safety_caps_and_leak_zero() -> None:
    risky = trajectory_reward(
        RewardComponents(
            elicitation=1,
            resolution=1,
            fidelity=1,
            turns=2,
            repeated_question_rate=0,
            premature_final=True,
        )
    )
    assert risky.final_reward == 0.35
    leaked = trajectory_reward(
        RewardComponents(
            elicitation=1,
            resolution=1,
            fidelity=1,
            turns=1,
            repeated_question_rate=0,
            hidden_field_leak=True,
        )
    )
    assert leaked.final_reward == 0


def test_premature_final_uses_proposed_action_before_skill_rewrite() -> None:
    step = {
        "proposed_action": {"action_type": "final"},
        "action_decision": {"final": {"action_type": "clarify"}},
        "stop_gate_verdict": "REDIRECT",
    }
    assert proposed_final_was_redirected(step)


def test_advantage_skips_low_variance_and_selects_contrasts() -> None:
    flat = compute_advantages(
        "flat",
        [ScoredMember(trajectory_id=f"t{i}", reward=0.5) for i in range(4)],
    )
    assert not flat.informative
    assert flat.skip_reason == "low_variance_group"
    varied = compute_advantages(
        "varied",
        [
            ScoredMember(trajectory_id="low", reward=0.1, turns=2),
            ScoredMember(trajectory_id="middle", reward=0.4, turns=1),
            ScoredMember(trajectory_id="unsafe", reward=0.6, premature_final=True),
            ScoredMember(trajectory_id="high", reward=0.9, turns=4),
        ],
    )
    selection = select_contrasts(varied)
    assert selection.highest_id == "high"
    assert selection.lowest_id == "low"
    assert selection.safety_failure_id == "unsafe"


def outcomes(
    count: int,
    delta: float,
    *,
    harmful: int = 0,
    severe: bool = False,
    unsupported: float = 0,
) -> list[PairOutcome]:
    values = []
    for index in range(count):
        pair_delta = -0.01 if index < harmful else delta
        values.append(
            PairOutcome(
                pair_id=str(index),
                triggered=True,
                reward_without=0.4,
                reward_with=0.4 + pair_delta,
                severe_risk_with=severe and index == 0,
                unsupported_claim_delta=unsupported,
            )
        )
    return values


def test_all_four_acceptance_paths() -> None:
    limits = AcceptanceThresholds(minimum_triggered_pairs=10)
    assert decide_skill(outcomes(5, 0.1), limits).decision == "DEFER"
    assert decide_skill(outcomes(10, -0.01), limits).decision == "REJECT"
    assert decide_skill(outcomes(10, 0.1, harmful=2), limits).decision == "REPAIR"
    assert decide_skill(outcomes(10, 0.1), limits).decision == "ACCEPT"
    assert decide_skill(outcomes(10, 0.1, severe=True), limits).decision == "REJECT"
    assert decide_skill(outcomes(10, 0.1, unsupported=0.01), limits).decision == "REPAIR"


def test_global_regression_gate() -> None:
    assert global_regression_passes(0.5, 0.49)
    assert not global_regression_passes(0.5, 0.48)


def test_invalid_teacher_output_becomes_noop() -> None:
    diagnosis, mode = parse_diagnosis("not json", "group-1")
    assert diagnosis.proposed_change == "NOOP"
    assert mode == "fallback_noop"


def test_registry_freeze_is_immutable_and_can_rollback(tmp_path: Path) -> None:
    repository_root = Path(__file__).resolve().parents[2]
    registry = SkillRegistry(tmp_path / "versions")
    first = registry.freeze(
        "v0.1.0",
        repository_root / "skills/seed",
        parent_version=None,
        evidence={"tests": "pass"},
    )
    assert len(first["skills"]) == 10
    registry.activate("v0.1.0")
    second = registry.freeze(
        "v0.2.0",
        repository_root / "skills/seed",
        parent_version="v0.1.0",
        evidence={"audit": "pass"},
    )
    registry.activate("v0.2.0")
    if not global_regression_passes(0.5, 0.47):
        rollback_pointer = registry.rollback()
    assert rollback_pointer["version"] == "v0.1.0"
    assert registry.current() == "v0.1.0"
    assert second["parent_version"] == "v0.1.0"
    with pytest.raises(FileExistsError):
        registry.freeze(
            "v0.2.0",
            repository_root / "skills/seed",
            parent_version="v0.1.0",
            evidence={"audit": "different"},
        )
