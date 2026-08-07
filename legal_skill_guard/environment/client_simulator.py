"""Frozen Phase 1 LLM client simulator with a strict hidden-input boundary."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from legal_skill_guard.inference.openai_client import (
    ChatClient,
    ChatResponse,
    GenerationConfig,
)
from legal_skill_guard.utils.hashing import canonical_json_sha256


def localized(value: object, language: str = "zh") -> str:
    if isinstance(value, dict):
        return str(value.get(language) or value.get("zh") or value.get("en") or "")
    return str(value or "")


@dataclass
class Phase1ClientSimulator:
    case_view: dict
    persona: dict
    model: ChatClient
    prompt_template: str
    generation: GenerationConfig
    history: list[tuple[str, str]] = field(default_factory=list)

    @classmethod
    def from_template_file(
        cls,
        case_view: dict,
        persona: dict,
        model: ChatClient,
        template_path: Path,
        generation: GenerationConfig,
    ) -> Phase1ClientSimulator:
        return cls(
            case_view=case_view,
            persona=persona,
            model=model,
            prompt_template=template_path.read_text(encoding="utf-8").strip(),
            generation=generation,
        )

    def _messages(self, lawyer_question: str) -> list[dict[str, str]]:
        facts_block = "\n".join(
            f"- {fact['client_belief']}" for fact in self.case_view.get("facts", [])
        )
        system = self.prompt_template.format(
            persona_who=localized(self.persona.get("who")),
            persona_voice=localized(self.persona.get("voice")),
            facts_block=facts_block,
        )
        messages = [{"role": "system", "content": system}]
        for previous_question, previous_answer in self.history:
            messages.append({"role": "user", "content": previous_question})
            messages.append({"role": "assistant", "content": previous_answer})
        messages.append({"role": "user", "content": lawyer_question})
        return messages

    def respond(self, lawyer_question: str, seed: int) -> tuple[ChatResponse, str]:
        messages = self._messages(lawyer_question)
        response = self.model.generate(
            messages,
            GenerationConfig(
                temperature=self.generation.temperature,
                top_p=self.generation.top_p,
                max_tokens=self.generation.max_tokens,
                seed=seed,
                disable_thinking=self.generation.disable_thinking,
            ),
        )
        self.history.append((lawyer_question, response.content))
        return response, canonical_json_sha256(messages)
