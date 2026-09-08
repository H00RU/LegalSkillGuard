from __future__ import annotations

from pathlib import Path

from legal_skill_guard.environment.client_response import ClientSimulator
from legal_skill_guard.inference.openai_client import ChatResponse, GenerationConfig


class RecordingClient:
    def __init__(self) -> None:
        self.messages = []

    def generate(self, messages, generation):
        self.messages = messages
        return ChatResponse(
            content="我只知道客户认知。",
            finish_reason="stop",
            prompt_tokens=10,
            completion_tokens=5,
            raw_id="test",
        )


def test_client_prompt_contains_belief_but_never_court_record_or_rubrics(tmp_path: Path) -> None:
    template = tmp_path / "client.txt"
    template.write_text(
        "人格：{persona_who}\n风格：{persona_voice}\n事实：\n{facts_block}",
        encoding="utf-8",
    )
    model = RecordingClient()
    simulator = ClientSimulator.from_template_file(
        {
            "id": "c1",
            "opening": "这是开场咨询",
            "facts": [{"fact_id": "F1", "client_belief": "客户认知", "gap_type": "disputed"}],
        },
        {"who": {"zh": "谨慎"}, "voice": {"zh": "简短"}},
        model,
        template,
        GenerationConfig(temperature=0, top_p=1, max_tokens=10, seed=42),
        max_selection_attempts=2,
    )
    _, input_hash = simulator.respond("发生了什么？", 42)
    serialized = str(model.messages)
    assert "客户认知" in serialized
    assert "court_record" not in serialized
    assert "expected_inquiries" not in serialized
    assert "memo_expectations" not in serialized
    assert len(input_hash) == 64


def test_real_client_selector_template_renders_literal_json() -> None:
    model = RecordingClient()
    simulator = ClientSimulator.from_template_file(
        {
            "id": "c1",
            "opening": "这是开场咨询",
            "facts": [{"fact_id": "F1", "client_belief": "客户认知", "gap_type": "disputed"}],
        },
        {"persona_id": "P_WD", "who": {"zh": "谨慎"}, "voice": {"zh": "简短"}},
        model,
        Path("configs/prompts/client_fact_selector_zh.txt"),
        GenerationConfig(temperature=0, top_p=1, max_tokens=10, seed=42),
        max_selection_attempts=2,
    )
    messages = simulator._messages("发生了什么？")
    assert "fact_ids只能选择一条" in messages[0]["content"]
    assert '"disclosure"' not in messages[0]["content"]
    assert "若所有候选都是not_answer则必须为空" in messages[0]["content"]
    assert "- F1 [客户知道但尚未披露]：客户认知" in messages[0]["content"]
    assert "- O1 [开场已公开]：这是开场咨询" in messages[0]["content"]


def test_provenance_client_role_cannot_enter_runtime_prompt() -> None:
    model = RecordingClient()
    simulator = ClientSimulator.from_template_file(
        {
            "id": "c1",
            "opening": "我在事故中受伤，想咨询赔偿。",
            "client_role": "包含未公开责任事实的编辑标注",
            "facts": [
                {
                    "fact_id": "F1",
                    "client_belief": "肇事人当时正在执行单位任务。",
                    "gap_type": "undisputed",
                }
            ],
        },
        {"persona_id": "P_WD", "who": {"zh": "合作"}, "voice": {"zh": "直接"}},
        model,
        Path("configs/prompts/client_fact_selector_zh.txt"),
        GenerationConfig(temperature=0, top_p=1, max_tokens=10, seed=42),
        max_selection_attempts=2,
    )

    messages = simulator._messages("您事故时是否在执行单位任务？")
    serialized = str(messages)

    assert "包含未公开责任事实的编辑标注" not in serialized
    assert "公开开场的第一人称咨询者" in serialized
