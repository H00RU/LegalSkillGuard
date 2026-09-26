from legal_skill_guard.agent.state_manager import StateManager
from legal_skill_guard.schemas.state import FactObservation, StatePatch


def test_state_conflict_is_preserved_not_overwritten() -> None:
    manager = StateManager()
    state = manager.initial("s1", "开场", max_turns=6, persona="P_WD")
    state = manager.merge(
        state,
        StatePatch(
            observations=[
                FactObservation(
                    fact_id="termination_date",
                    label="解除日期",
                    status="client_claimed",
                    value="1月1日",
                    criticality="high",
                )
            ]
        ),
        1,
    )
    state = manager.merge(
        state,
        StatePatch(
            observations=[
                FactObservation(
                    fact_id="termination_date",
                    label="解除日期",
                    status="disputed",
                    value="2月1日",
                    criticality="high",
                )
            ]
        ),
        2,
    )
    fact = next(item for item in state.facts if item.fact_id == "termination_date")
    assert fact.status == "disputed"
    assert fact.value == "1月1日"
    assert state.unresolved_conflicts[0].new_value == "2月1日"


def test_more_detailed_claim_refines_without_false_conflict() -> None:
    manager = StateManager()
    state = manager.initial("s-refine", "开场", max_turns=6)
    for turn, value in [(1, "判决后"), (2, "判决后不久完成股权转让")]:
        state = manager.merge(
            state,
            StatePatch(
                observations=[
                    FactObservation(
                        fact_id="transfer_time",
                        label="股权转让时间",
                        status="client_claimed",
                        value=value,
                        criticality="high",
                    )
                ]
            ),
            turn,
        )
    fact = next(item for item in state.facts if item.fact_id == "transfer_time")
    assert fact.status == "client_claimed"
    assert fact.value == "判决后不久完成股权转让"
    assert not state.unresolved_conflicts


def test_evidence_label_upgrades_claim_to_corroborated() -> None:
    manager = StateManager()
    state = manager.initial("s-evidence", "开场", max_turns=6)
    state = manager.merge(
        state,
        StatePatch(
            observations=[
                FactObservation(
                    fact_id="notice_date",
                    label="收到通知日期",
                    status="client_claimed",
                    value="9月2日",
                    evidence_labels=["书面答复"],
                    criticality="high",
                )
            ]
        ),
        1,
    )
    fact = next(item for item in state.facts if item.fact_id == "notice_date")
    assert fact.status == "corroborated"
    assert fact.evidence_ids


def test_public_opening_anchor_is_provenance_not_substantive_evidence() -> None:
    manager = StateManager()
    state = manager.initial("opening-agenda-anchor", "客户提到房屋买卖合同争议。", max_turns=6)
    state = manager.merge(
        state,
        StatePatch(
            observations=[
                FactObservation(
                    fact_id="opening_agenda_contract_time",
                    label="房屋买卖合同签署时间",
                    status="unknown",
                    value=None,
                    evidence_labels=["public_opening_anchor:房屋买卖合同"],
                    criticality="medium",
                    target_kind="client_fact",
                )
            ]
        ),
        0,
    )

    fact = next(
        item for item in state.facts if item.fact_id == "opening_agenda_contract_time"
    )
    assert fact.status == "unknown"
    assert fact.evidence_ids == []
    assert state.evidence == []
    assert state.actionable_unresolved_fact_count == 1


def test_state_unknown_and_not_available_are_distinct() -> None:
    manager = StateManager()
    state = manager.initial("s2", "开场", max_turns=6)
    patch = StatePatch(
        observations=[
            FactObservation(
                fact_id="contract", label="书面合同", status="not_available", criticality="high"
            )
        ]
    )
    state = manager.merge(state, patch, 1)
    fact = next(item for item in state.facts if item.fact_id == "contract")
    assert fact.status == "not_available"


def test_withheld_interaction_preserves_unresolved_target_and_retry_eligibility() -> None:
    manager = StateManager()
    state = manager.initial("withheld", "存在自动续费争议。", max_turns=6)
    state = manager.merge(
        state,
        StatePatch(
            observations=[
                FactObservation(
                    fact_id="renewal_notice",
                    label="平台是否发送续费提醒",
                    status="unknown",
                    criticality="high",
                )
            ]
        ),
        0,
    )

    state = manager.mark_interaction(
        state,
        turn=1,
        action_type="ask",
        target_id="renewal_notice",
        question="你们为什么隐瞒提醒？",
        target_not_available=True,
        target_answered=True,
        client_response="这个问题我现在还不想细说。",
        response_kind="withheld",
        disclosed_fact_ids=["F1"],
    )

    target = next(item for item in state.facts if item.fact_id == "renewal_notice")
    assert target.status == "unknown"
    assert target.value is None
    assert state.asked_targets == []
    assert state.high_critical_unknown_count == 1
    assert state.actionable_unresolved_fact_count == 1
    assert state.interactions[-1].response_kind == "withheld"
    assert state.interactions[-1].new_information is False
    assert state.interactions[-1].disclosed_fact_ids == []
    assert state.interactions[-1].covered_target_ids == []

    state.candidate_action = {
        "action_type": "ask",
        "target_id": "renewal_notice",
        "content": "我解释用途后，您是否记得平台发过提醒？",
    }
    assert state.candidate_target_repeated is False


def test_route_contract_failure_cannot_close_or_consume_target() -> None:
    manager = StateManager()
    state = manager.initial("route-failure", "存在变更登记争议。", max_turns=6)
    state = manager.merge(
        state,
        StatePatch(
            observations=[
                FactObservation(
                    fact_id="formal_acceptance",
                    label="变更登记申请是否被正式受理",
                    status="unknown",
                    criticality="high",
                )
            ]
        ),
        0,
    )

    state = manager.mark_interaction(
        state,
        turn=1,
        action_type="ask",
        target_id="formal_acceptance",
        question="市监局是否正式受理变更申请？",
        # StateManager fails closed even if a caller accidentally supplies
        # substantive outcome flags alongside the protocol-failure provenance.
        target_not_available=True,
        target_answered=True,
        client_response="现有信息里没有这项具体情况，我需要再核实。",
        response_kind="contract_fallback",
        disclosed_fact_ids=["F1"],
    )

    target = next(item for item in state.facts if item.fact_id == "formal_acceptance")
    assert target.status == "unknown"
    assert target.value is None
    assert state.asked_targets == []
    assert state.interactions[-1].response_kind == "contract_fallback"
    assert state.interactions[-1].new_information is False
    assert state.interactions[-1].disclosed_fact_ids == []
    assert state.interactions[-1].covered_target_ids == []


def test_opening_sentences_are_visible_substantive_claims_without_semantic_labels() -> None:
    state = StateManager().initial(
        "opening-claims",
        "我与对方签了合同。货物已经交付；对方尚未付款！",
        max_turns=6,
    )
    claims = [item for item in state.facts if item.fact_id.startswith("opening_claim_")]
    assert [item.value for item in claims] == [
        "我与对方签了合同",
        "货物已经交付",
        "对方尚未付款",
    ]
    assert all(item.status == "client_claimed" for item in claims)
    assert state.substantive_fact_count == 3


def test_one_visible_answer_updates_only_the_target_actually_asked() -> None:
    manager = StateManager()
    state = manager.initial("coverage", "劳动合同到期后继续工作。", max_turns=6)
    state = manager.merge(
        state,
        StatePatch(
            observations=[
                FactObservation(
                    fact_id="renewal_discussion",
                    label="双方是否讨论续签",
                    status="unknown",
                ),
                FactObservation(
                    fact_id="employee_consent",
                    label="员工是否同意续签",
                    status="unknown",
                ),
                FactObservation(
                    fact_id="release_terms",
                    label="解除协议是否涵盖二倍工资",
                    status="unknown",
                ),
            ]
        ),
        0,
    )
    answer = "公司多次通过微信通知续签，但员工主动拒绝。"
    state = manager.mark_interaction(
        state,
        turn=1,
        action_type="ask",
        target_id="renewal_discussion",
        question="双方是否讨论过续签？",
        target_answered=True,
        client_response=answer,
        response_kind="new_hidden_fact",
        disclosed_fact_ids=["F2"],
    )
    facts = {item.fact_id: item for item in state.facts}
    assert facts["renewal_discussion"].status == "client_claimed"
    assert facts["employee_consent"].status == "unknown"
    assert facts["renewal_discussion"].value == answer
    assert facts["employee_consent"].value is None
    assert facts["release_terms"].status == "unknown"
    assert state.asked_targets == ["renewal_discussion"]
    assert state.interactions[-1].covered_target_ids == ["renewal_discussion"]
