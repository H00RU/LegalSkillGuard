"""Small auditable client for a local OpenAI-compatible vLLM server."""

from __future__ import annotations

import fcntl
import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import error, request


@dataclass(frozen=True)
class GenerationConfig:
    temperature: float
    top_p: float
    max_tokens: int
    seed: int
    disable_thinking: bool = True
    reasoning_effort: str | None = None
    response_schema: dict[str, Any] | None = None
    response_schema_name: str = "local_structured_response"


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
        expected_model_root: str | Path | None = None,
        expected_max_model_len: int | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.retries = retries
        self.expected_model_root = (
            str(Path(expected_model_root).resolve())
            if expected_model_root is not None
            else None
        )
        self.expected_max_model_len = expected_max_model_len
        # Research servers are loopback-only. Never route hidden prompts or responses
        # through a workstation-wide HTTP(S) proxy.
        self.opener = request.build_opener(request.ProxyHandler({}))

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        body = json.dumps(payload, ensure_ascii=False).encode() if payload is not None else None
        headers = {"Authorization": f"Bearer {self.api_key}"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        req = request.Request(f"{self.base_url}{path}", data=body, headers=headers, method=method)
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                with self.opener.open(req, timeout=self.timeout_seconds) as response:
                    return json.loads(response.read().decode("utf-8"))
            except (error.URLError, error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt >= self.retries:
                    break
                time.sleep(0.5 * (2**attempt))
        raise RuntimeError(f"Local model request failed: {last_error}") from last_error

    def readiness(self) -> dict[str, Any]:
        try:
            response = self._request("GET", "/models")
        except RuntimeError as exc:
            return {"ready": False, "reason": type(exc.__cause__ or exc).__name__}
        cards = [item for item in response.get("data", []) if item.get("id") == self.model]
        if len(cards) != 1:
            return {
                "ready": False,
                "reason": "model_card_not_unique",
                "matching_model_card_count": len(cards),
            }
        card = cards[0]
        observed_root = card.get("root")
        normalized_root = (
            str(Path(str(observed_root)).resolve())
            if observed_root is not None and self.expected_model_root is not None
            else observed_root
        )
        observed_max_model_len = card.get("max_model_len")
        checks = {
            "model_id_matches": card.get("id") == self.model,
            "model_root_matches": self.expected_model_root is None
            or normalized_root == self.expected_model_root,
            "max_model_len_matches": self.expected_max_model_len is None
            or observed_max_model_len == self.expected_max_model_len,
        }
        failed = [name for name, passed in checks.items() if not passed]
        return {
            "ready": not failed,
            "reason": "model_contract_matches" if not failed else "model_contract_mismatch",
            "model": self.model,
            "observed_model_root": normalized_root,
            "expected_model_root": self.expected_model_root,
            "observed_max_model_len": observed_max_model_len,
            "expected_max_model_len": self.expected_max_model_len,
            "checks": checks,
            "failed_checks": failed,
        }

    def is_ready(self) -> bool:
        return bool(self.readiness()["ready"])

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
        if generation.reasoning_effort is not None:
            payload["reasoning_effort"] = generation.reasoning_effort
        if generation.response_schema is not None:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": generation.response_schema_name,
                    "strict": True,
                    "schema": generation.response_schema,
                },
            }
        response = self._request("POST", "/chat/completions", payload)
        choices = response.get("choices") or []
        if not choices:
            raise RuntimeError(f"Local model returned no choices: {response}")
        # An empty assistant body is a completed, provenance-bearing model output,
        # not a transport failure.  Preserve its finish reason, usage and response
        # id so the calling role can record it and spend that role's bounded repair
        # attempt.  Raising here bypassed every planner/policy/client/memo repair
        # loop and turned one auditable malformed completion into a batch-wide hard
        # failure.  A response without ``choices`` remains a protocol hard error.
        content = choices[0].get("message", {}).get("content") or ""
        usage = response.get("usage") or {}
        return ChatResponse(
            content=content.strip(),
            finish_reason=choices[0].get("finish_reason"),
            prompt_tokens=int(usage.get("prompt_tokens") or 0),
            completion_tokens=int(usage.get("completion_tokens") or 0),
            raw_id=response.get("id"),
        )


class ReplayCachedChatClient:
    """Replay exact generations for identical requests within a paired experiment."""

    def __init__(self, delegate: ChatClient, cache_root: Path) -> None:
        self.delegate = delegate
        self.cache_root = cache_root
        self.cache_root.mkdir(parents=True, exist_ok=True)
        self.model = delegate.model
        self.hits = 0
        self.misses = 0

    def is_ready(self) -> bool:
        return self.delegate.is_ready()

    def generate(
        self, messages: list[dict[str, str]], generation: GenerationConfig
    ) -> ChatResponse:
        request_value = {
            "model": self.model,
            "messages": messages,
            "generation": {
                "temperature": generation.temperature,
                "top_p": generation.top_p,
                "max_tokens": generation.max_tokens,
                "seed": generation.seed,
                "disable_thinking": generation.disable_thinking,
                "reasoning_effort": generation.reasoning_effort,
            },
        }
        # Preserve exact replay keys for all existing unconstrained planner/client/
        # memo calls.  A structured policy request is deliberately a distinct key.
        if generation.response_schema is not None:
            request_value["generation"]["response_schema"] = generation.response_schema
            request_value["generation"]["response_schema_name"] = (
                generation.response_schema_name
            )
        canonical = json.dumps(
            request_value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        key = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        path = self.cache_root / f"{key}.json"
        lock_path = path.with_suffix(".json.lock")
        with lock_path.open("a+", encoding="utf-8") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            if path.is_file():
                value = json.loads(path.read_text(encoding="utf-8"))
                response_value = value.get("response")
                response_canonical = json.dumps(
                    response_value,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                response_sha256 = hashlib.sha256(response_canonical.encode("utf-8")).hexdigest()
                if (
                    value.get("request_sha256") != key
                    or value.get("response_sha256") != response_sha256
                ):
                    raise RuntimeError(f"Replay cache hash mismatch: {path}")
                self.hits += 1
                return ChatResponse(**response_value)
            response = self.delegate.generate(messages, generation)
            response_value = {
                "content": response.content,
                "finish_reason": response.finish_reason,
                "prompt_tokens": response.prompt_tokens,
                "completion_tokens": response.completion_tokens,
                "raw_id": response.raw_id,
            }
            response_canonical = json.dumps(
                response_value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            value = {
                "schema_version": 2,
                "request_sha256": key,
                "response_sha256": hashlib.sha256(response_canonical.encode("utf-8")).hexdigest(),
                "response": response_value,
            }
            temporary = path.with_suffix(".json.tmp")
            temporary.write_text(
                json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            temporary.replace(path)
            self.misses += 1
            return response
