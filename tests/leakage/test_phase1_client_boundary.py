from __future__ import annotations

from pathlib import Path

from legal_skill_guard.environment.client_simulator import Phase1ClientSimulator
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
    simulator = Phase1ClientSimulator.from_template_file(
        {
            "id": "c1",
            "opening": "咨询",
            "facts": [
                {"fact_id": "F1", "client_belief": "客户认知", "gap_type": "disputed"}
            ],
        },
        {"who": {"zh": "谨慎"}, "voice": {"zh": "简短"}},
        model,
        template,
        GenerationConfig(temperature=0, top_p=1, max_tokens=10, seed=42),
    )
    _, input_hash = simulator.respond("发生了什么？", 42)
    serialized = str(model.messages)
    assert "客户认知" in serialized
    assert "court_record" not in serialized
    assert "expected_inquiries" not in serialized
    assert "memo_expectations" not in serialized
    assert len(input_hash) == 64
