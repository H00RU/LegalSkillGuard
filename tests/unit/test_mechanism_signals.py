from types import SimpleNamespace

from legal_skill_guard.evaluation.semantic import derive_mechanism_signals
from legal_skill_guard.schemas.action import StructuredAction
from legal_skill_guard.schemas.state import FactObservation, StatePatch


def _step(
    turn: int,
    target_id: str,
    response_kind: str,
    *,
    target_kind: str | None = "client_fact",
    selected_fact_ids: list[str] | None = None,
    asked_targets: list[str] | None = None,
    client_fallback: bool = False,
    policy_reason: str = "model_choice",
    policy_health: list[str] | None = None,
    post_skill_health: list[str] | None = None,
) -> SimpleNamespace:
    final = StructuredAction(
        action_type="ask",
        target_type="fact",
        target_id=target_id,
        reason=policy_reason,
        content="请说明相关事实。",
    )
    return SimpleNamespace(
        turn=turn,
        state_before={
            "facts": [
                {
                    "fact_id": target_id,
                    "target_kind": target_kind,
                    "status": "unknown",
                }
            ],
            "asked_targets": list(asked_targets or []),
        },
        proposed_action=final,
        action_decision=SimpleNamespace(final=final, changes=[]),
        client_response_kind=response_kind,
        client_selected_fact_ids=list(selected_fact_ids or []),
        client_safe_fallback=client_fallback,
        policy_health_violations=list(policy_health or []),
        post_skill_health_violations=list(post_skill_health or []),
        verifier_results=[],
    )


def _trajectory(
    steps: list[SimpleNamespace],
    *,
    evidence_target_ids: tuple[str, ...] = (),
    schema_version: int = 15,
) -> SimpleNamespace:
    return SimpleNamespace(
        schema_version=schema_version,
        steps=steps,
        initial_investigation_plan=StatePatch(
            observations=[
                FactObservation(
                    fact_id=fact_id,
                    label=f"证据目标{fact_id}",
                    status="unknown",
                    target_kind="evidence_or_third_party",
                )
                for fact_id in evidence_target_ids
            ]
        ),
    )


def test_mechanism_signals_separate_new_facts_and_clean_evidence_gaps() -> None:
    trajectory = _trajectory(
        [
            _step(
                1,
                "E1",
                "unavailable",
                target_kind="evidence_or_third_party",
            ),
            _step(
                2,
                "E2",
                "unavailable",
                target_kind="evidence_or_third_party",
                client_fallback=True,
            ),
            _step(
                3,
                "C1",
                "new_hidden_fact",
                selected_fact_ids=["F2", "F1"],
            ),
        ],
        evidence_target_ids=("E1", "E2"),
    )

    result = derive_mechanism_signals(trajectory, {"F1", "F2", "F3"})

    assert result.newly_elicited_fact_ids == ["F1", "F2"]
    assert result.newly_elicited_fact_count == 2
    assert result.evidence_or_third_party_target_ids == ["E1", "E2"]
    assert result.evidence_or_third_party_target_count == 2
    assert result.eligible_evidence_inquiry_target_ids == ["E1"]
    assert result.eligible_evidence_inquiry_count == 1
    assert result.identified_evidence_gap_ids == ["E1"]
    assert result.identified_evidence_gap_turns == [1]
    assert result.identified_evidence_gap_count == 1
    assert result.identified_evidence_gap_rate == 1.0
    assert result.true_zero_identified_evidence_gap is False
    assert result.evidence_gap_outcome == "identified"


def test_evidence_gap_true_zero_requires_a_clean_observed_evidence_inquiry() -> None:
    unhealthy = _trajectory(
        [
            _step(
                1,
                "E1",
                "unavailable",
                target_kind="evidence_or_third_party",
                post_skill_health=["unsafe_question"],
            )
        ],
        evidence_target_ids=("E1",),
    )
    result = derive_mechanism_signals(unhealthy)
    assert result.identified_evidence_gap_count == 0
    assert result.eligible_evidence_inquiry_count == 0
    assert result.identified_evidence_gap_rate is None
    assert result.true_zero_identified_evidence_gap is None
    assert result.evidence_gap_outcome == (
        "not_applicable_no_eligible_evidence_inquiries"
    )

    answered = _trajectory(
        [
            _step(
                1,
                "E1",
                "new_hidden_fact",
                target_kind="evidence_or_third_party",
                selected_fact_ids=["F1"],
            )
        ],
        evidence_target_ids=("E1",),
    )
    answered_result = derive_mechanism_signals(answered)
    assert answered_result.eligible_evidence_inquiry_count == 1
    assert answered_result.identified_evidence_gap_count == 0
    assert answered_result.identified_evidence_gap_rate == 0.0
    assert answered_result.true_zero_identified_evidence_gap is True
    assert answered_result.evidence_gap_outcome == "true_zero"

    no_evidence = derive_mechanism_signals(_trajectory([]))
    assert no_evidence.evidence_or_third_party_target_count == 0
    assert no_evidence.identified_evidence_gap_rate is None
    assert no_evidence.true_zero_identified_evidence_gap is None
    assert no_evidence.evidence_gap_outcome == (
        "not_applicable_no_eligible_evidence_inquiries"
    )


def test_withheld_evidence_target_is_neither_g_nor_true_zero() -> None:
    withheld = _trajectory(
        [
            _step(
                1,
                "E1",
                "withheld",
                target_kind="evidence_or_third_party",
            )
        ],
        evidence_target_ids=("E1",),
    )

    result = derive_mechanism_signals(withheld)

    assert result.evidence_or_third_party_target_count == 1
    assert result.eligible_evidence_inquiry_count == 0
    assert result.identified_evidence_gap_count == 0
    assert result.identified_evidence_gap_rate is None
    assert result.true_zero_identified_evidence_gap is None
    assert result.evidence_gap_outcome == (
        "not_applicable_no_eligible_evidence_inquiries"
    )


def test_legacy_trajectory_is_not_silently_reported_as_true_zero() -> None:
    legacy = _trajectory(
        [
            _step(
                1,
                "E1",
                "unavailable",
                target_kind="evidence_or_third_party",
            )
        ],
        evidence_target_ids=("E1",),
        schema_version=14,
    )

    result = derive_mechanism_signals(legacy)

    assert result.target_kind_available is False
    assert result.evidence_or_third_party_target_count is None
    assert result.identified_evidence_gap_rate is None
    assert result.true_zero_identified_evidence_gap is None
    assert result.evidence_gap_outcome == "unavailable_legacy_target_kind"


def test_protocol15_missing_target_kind_fails_closed_for_g() -> None:
    malformed = _trajectory(
        [_step(1, "E1", "unavailable", target_kind=None)],
        evidence_target_ids=("E1",),
    )

    result = derive_mechanism_signals(malformed)

    assert result.target_kind_available is False
    assert result.evidence_or_third_party_target_count is None
    assert result.eligible_evidence_inquiry_count is None
    assert result.identified_evidence_gap_count == 0
    assert result.identified_evidence_gap_rate is None
    assert result.evidence_gap_outcome == (
        "unavailable_invalid_target_kind_provenance"
    )


def test_protocol15_target_kind_mismatch_fails_closed_for_g() -> None:
    malformed = _trajectory(
        [_step(1, "E1", "unavailable", target_kind="client_fact")],
        evidence_target_ids=("E1",),
    )

    result = derive_mechanism_signals(malformed)

    assert result.target_kind_available is False
    assert result.evidence_or_third_party_target_ids == []
    assert result.identified_evidence_gap_ids == []
    assert result.evidence_gap_outcome == (
        "unavailable_invalid_target_kind_provenance"
    )


def test_only_first_effective_inquiry_can_identify_an_evidence_gap() -> None:
    trajectory = _trajectory(
        [
            _step(
                1,
                "E1",
                "opening_repeat",
                target_kind="evidence_or_third_party",
            ),
            _step(
                2,
                "E1",
                "unavailable",
                target_kind="evidence_or_third_party",
                asked_targets=["E1"],
            ),
        ],
        evidence_target_ids=("E1",),
    )

    result = derive_mechanism_signals(trajectory)

    assert result.identified_evidence_gap_ids == []
    assert result.evidence_gap_outcome == "true_zero"
