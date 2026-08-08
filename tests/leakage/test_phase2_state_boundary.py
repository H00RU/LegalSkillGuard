from legal_skill_guard.data_visibility import assert_online_payload_safe
from legal_skill_guard.schemas.action import StructuredAction
from legal_skill_guard.schemas.state import ConsultationState


def test_phase2_state_and_action_contain_no_benchmark_hidden_fields() -> None:
    state = ConsultationState(session_id="safe")
    action = StructuredAction(action_type="ask", target_type="fact", target_id="event_time")
    assert_online_payload_safe({"state": state.model_dump(), "action": action.model_dump()})
