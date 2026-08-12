from pathlib import Path

import yaml

from scripts.generate_phase3_skills import trajectory_summary

ROOT = Path(__file__).resolve().parents[2]


def test_phase2_no_skill_comparator_matches_phase1_runner_schema() -> None:
    config = yaml.safe_load(
        (ROOT / "configs/experiments/phase2_no_skill_comparator.yaml").read_text(encoding="utf-8")
    )
    lawyer = config["generation"]["lawyer"]
    assert {"temperature", "top_p", "max_tokens_action", "max_tokens_memo"} <= set(lawyer)
    assert config["methods"] == ["B1_prompted_multiturn"]
    assert config["data"]["run_partition"] == "pilot_acceptance"


def test_phase3_teacher_summary_bounds_free_text_and_drops_raw_actions() -> None:
    long_text = "x" * 500
    trajectory = {
        "trajectory_id": "trajectory-1",
        "status": "memo_submitted",
        "steps": [
            {
                "turn": 1,
                "state_before": {
                    "facts": [],
                    "unresolved_conflicts": [],
                    "asked_targets": [],
                    "risk_flags": [],
                },
                "proposed_action": {
                    "action_type": "ask",
                    "target_type": "fact",
                    "target_id": "fact-1",
                    "reason": "missing",
                    "constraints": [],
                    "raw_model_output": long_text,
                },
                "action_decision": {
                    "final": {
                        "action_type": "ask",
                        "target_type": "fact",
                        "target_id": "fact-1",
                        "reason": "missing",
                        "constraints": [],
                        "raw_model_output": long_text,
                    },
                    "activated_skill_ids": [],
                },
                "rendered_question": long_text,
                "client_response": long_text,
                "verifier_results": [],
            }
        ],
    }
    summary = trajectory_summary(trajectory, {"final_reward": 0.5})
    step = summary["steps"][0]
    assert len(step["question"]) == 240
    assert len(step["client_response"]) == 240
    assert "raw_model_output" not in step["proposed_action"]
    assert "raw_model_output" not in step["final_action"]
