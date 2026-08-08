from legal_skill_guard.agent.state_manager import StateManager
from legal_skill_guard.schemas.state import FactObservation, StatePatch


def test_state_conflict_is_preserved_not_overwritten() -> None:
    manager = StateManager()
    state = manager.initial("s1", "开场", persona="P_WD")
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
                    status="client_claimed",
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


def test_state_unknown_and_not_available_are_distinct() -> None:
    manager = StateManager()
    state = manager.initial("s2", "开场")
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
