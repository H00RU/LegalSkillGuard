from legal_skill_guard.schemas.trajectory import (
    Action,
    Message,
    TokenUsage,
    Trajectory,
    TrajectoryStep,
)
from scripts.analyze_phase1_run import summarize
from scripts.compare_phase1_runs import normalized_trajectory


def sample_trajectory() -> Trajectory:
    action = Action(
        tool="talk_to_client",
        content="是否签订合同？",
        parse_mode="json",
        raw_model_output='{"tool":"talk_to_client","message":"是否签订合同？"}',
    )
    return Trajectory(
        trajectory_id="t1",
        run_id="a",
        method="B1_prompted_multiturn",
        case_id="C1",
        jurisdiction="CN",
        persona="P_WD",
        seed=1,
        model_id="model",
        model_revision="revision",
        status="memo_submitted",
        opening="开场",
        max_turns=1,
        steps=[
            TrajectoryStep(
                turn=1,
                visible_input=[Message(role="user", content="开场")],
                proposed_action=action,
                action_after_skills=action,
                rendered_question="是否签订合同？",
                client_response="签了。",
                latency_ms=2,
                token_usage=TokenUsage(prompt=10, completion=5),
            )
        ],
        memo="案情概要\n关键事实\n法律问题\n风险评估\n下一步建议",
        elapsed_seconds=0.1,
        created_at="2026-01-01T00:00:00Z",
    )


def test_summary_computes_phase1_custom_metrics() -> None:
    result = summarize([sample_trajectory()])
    assert result["five_section_memo_rate"] == 1.0
    assert result["structured_action_parse_rate"] == 1.0
    assert result["mean_total_tokens"] == 15.0
    assert result["exact_duplicate_question_rate"] == 0.0


def test_normalization_only_removes_runtime_fields() -> None:
    value = sample_trajectory().model_dump(mode="json")
    normalized = normalized_trajectory(value)
    assert "run_id" not in normalized
    assert "created_at" not in normalized
    assert "elapsed_seconds" not in normalized
    assert "latency_ms" not in normalized["steps"][0]
    assert normalized["memo"] == value["memo"]
