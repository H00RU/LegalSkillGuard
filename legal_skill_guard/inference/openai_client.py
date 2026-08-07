"""Small auditable client for a local OpenAI-compatible vLLM server."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any
from urllib import error, request


@dataclass(frozen=True)
class GenerationConfig:
    temperature: float
    top_p: float
    max_tokens: int
    seed: int
    disable_thinking: bool = True


@dataclass(frozen=True)
class ChatResponse:
    content: str
    finish_reason: str | None
    prompt_tokens: int
    completion_tokens: int
    raw_id: str | None


class ChatClient:
    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str = "local-research",
        timeout_seconds: float = 600.0,
        retries: int = 2,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.retries = retries

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        body = json.dumps(payload, ensure_ascii=False).encode() if payload is not None else None
        headers = {"Authorization": f"Bearer {self.api_key}"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        req = request.Request(f"{self.base_url}{path}", data=body, headers=headers, method=method)
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                with request.urlopen(req, timeout=self.timeout_seconds) as response:
                    return json.loads(response.read().decode("utf-8"))
            except (error.URLError, error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt >= self.retries:
                    break
                time.sleep(0.5 * (2**attempt))
        raise RuntimeError(f"Local model request failed: {last_error}") from last_error

    def is_ready(self) -> bool:
        try:
            response = self._request("GET", "/models")
        except RuntimeError:
            return False
        return any(item.get("id") == self.model for item in response.get("data", []))

    def generate(
        self, messages: list[dict[str, str]], generation: GenerationConfig
    ) -> ChatResponse:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": generation.temperature,
            "top_p": generation.top_p,
            "max_tokens": generation.max_tokens,
            "seed": generation.seed,
        }
        if generation.disable_thinking:
            payload["chat_template_kwargs"] = {"enable_thinking": False}
        response = self._request("POST", "/chat/completions", payload)
        choices = response.get("choices") or []
        if not choices:
            raise RuntimeError(f"Local model returned no choices: {response}")
        content = choices[0].get("message", {}).get("content") or ""
        if not content.strip():
            raise RuntimeError(f"Local model returned empty content: {response.get('id')}")
        usage = response.get("usage") or {}
        return ChatResponse(
            content=content.strip(),
            finish_reason=choices[0].get("finish_reason"),
            prompt_tokens=int(usage.get("prompt_tokens") or 0),
            completion_tokens=int(usage.get("completion_tokens") or 0),
            raw_id=response.get("id"),
        )
