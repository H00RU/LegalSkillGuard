"""Cached, schema-validated client for a local OpenAI-compatible judge."""

from __future__ import annotations

import fcntl
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib import error, request

from jsonschema import Draft202012Validator, ValidationError

from legal_skill_guard.utils.hashing import canonical_json_sha256


class StructuredModelInvocationError(RuntimeError):
    """The local judge failed without producing a schema-valid response."""


@dataclass(frozen=True)
class StructuredModelResponse:
    value: dict[str, Any]
    model: str
    request_sha256: str
    response_sha256: str
    cache_hit: bool
    invocation: dict[str, Any]


RequestRunner = Callable[[str, str, dict[str, Any] | None, float], Any]


class StructuredOpenAIClient:
    """Call one frozen local model with deterministic JSON-schema decoding."""

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        model_revision: str | None = None,
        cache_root: Path,
        reasoning_effort: str = "high",
        max_completion_tokens: int = 4096,
        timeout_seconds: float = 600.0,
        retries: int = 1,
        request_runner: RequestRunner | None = None,
        expected_model_root: str | Path | None = None,
        expected_max_model_len: int | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.model_revision = model_revision
        self.cache_root = cache_root
        self.reasoning_effort = reasoning_effort
        self.max_completion_tokens = max_completion_tokens
        self.timeout_seconds = timeout_seconds
        self.retries = retries
        self.expected_model_root = (
            str(Path(expected_model_root).resolve())
            if expected_model_root is not None
            else None
        )
        self.expected_max_model_len = expected_max_model_len
        self.opener = request.build_opener(request.ProxyHandler({}))
        self.request_runner = request_runner or self._http_request

    def _http_request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None,
        timeout_seconds: float,
    ) -> Any:
        body = json.dumps(payload, ensure_ascii=False).encode() if payload is not None else None
        headers = {"Authorization": "Bearer local-research"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        req = request.Request(f"{self.base_url}{path}", data=body, headers=headers, method=method)
        with self.opener.open(req, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))

    def preflight(self) -> dict[str, Any]:
        try:
            response = self.request_runner("GET", "/models", None, min(self.timeout_seconds, 30))
        except (
            OSError,
            TimeoutError,
            error.URLError,
            error.HTTPError,
            json.JSONDecodeError,
        ) as exc:
            return {"ready": False, "reason": type(exc).__name__}
        cards = [item for item in response.get("data", []) if item.get("id") == self.model]
        available = [str(item.get("id")) for item in response.get("data", [])]
        if len(cards) != 1:
            return {
                "ready": False,
                "reason": "model_card_not_unique",
                "model": self.model,
                "model_revision": self.model_revision,
                "base_url": self.base_url,
                "available_models": available,
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
            "model_revision": self.model_revision,
            "base_url": self.base_url,
            "available_models": available,
            "observed_model_root": normalized_root,
            "expected_model_root": self.expected_model_root,
            "observed_max_model_len": observed_max_model_len,
            "expected_max_model_len": self.expected_max_model_len,
            "checks": checks,
            "failed_checks": failed,
        }

    def generate_json(
        self,
        *,
        purpose: str,
        system_prompt: str,
        user_prompt: str,
        output_schema: dict[str, Any],
    ) -> StructuredModelResponse:
        Draft202012Validator.check_schema(output_schema)
        request_value = {
            "adapter_schema_version": 2,
            "purpose": purpose,
            "model": self.model,
            "model_revision": self.model_revision,
            "reasoning_effort": self.reasoning_effort,
            "max_completion_tokens": self.max_completion_tokens,
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "output_schema": output_schema,
        }
        request_sha256 = canonical_json_sha256(request_value)
        cache_path = self.cache_root / purpose / f"{request_sha256}.json"
        if cache_path.is_file():
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            value = cached["value"]
            Draft202012Validator(output_schema).validate(value)
            if canonical_json_sha256(value) != cached["response_sha256"]:
                raise StructuredModelInvocationError(
                    f"Local structured cache hash mismatch: {cache_path}"
                )
            return StructuredModelResponse(
                value=value,
                model=self.model,
                request_sha256=request_sha256,
                response_sha256=cached["response_sha256"],
                cache_hit=True,
                invocation=cached["invocation"],
            )

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt.strip()},
                {"role": "user", "content": user_prompt.strip()},
            ],
            "temperature": 0.0,
            "top_p": 1.0,
            "seed": 0,
            "max_completion_tokens": self.max_completion_tokens,
            "reasoning_effort": self.reasoning_effort,
            "include_reasoning": False,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "legal_skill_guard_response",
                    "strict": True,
                    "schema": output_schema,
                },
            },
        }
        last_error = "unknown_failure"
        for attempt in range(self.retries + 1):
            started = datetime.now(UTC)
            response: dict[str, Any] | None = None
            choice: dict[str, Any] | None = None
            content = ""
            try:
                response = self.request_runner(
                    "POST", "/chat/completions", payload, self.timeout_seconds
                )
                choices = response.get("choices") or []
                if not choices:
                    raise StructuredModelInvocationError("local judge returned no choices")
                choice = choices[0]
                if choice.get("finish_reason") != "stop":
                    raise StructuredModelInvocationError(
                        f"local judge finish_reason={choice.get('finish_reason')!r}"
                    )
                content = choice.get("message", {}).get("content") or ""
                value = json.loads(content)
                if not isinstance(value, dict):
                    raise StructuredModelInvocationError(
                        "local judge structured output is not a JSON object"
                    )
                Draft202012Validator(output_schema).validate(value)
            except (
                OSError,
                TimeoutError,
                error.URLError,
                error.HTTPError,
                json.JSONDecodeError,
                ValidationError,
                StructuredModelInvocationError,
            ) as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                self._write_failure_artifact(
                    purpose=purpose,
                    request_sha256=request_sha256,
                    attempt=attempt + 1,
                    started=started,
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                    response=response,
                    choice=choice,
                    content=content,
                )
                if attempt < self.retries:
                    time.sleep(1.0 * (2**attempt))
                continue
            finished = datetime.now(UTC)
            response_sha256 = canonical_json_sha256(value)
            invocation = {
                "attempt": attempt + 1,
                "started_at": started.isoformat(),
                "finished_at": finished.isoformat(),
                "elapsed_seconds": round((finished - started).total_seconds(), 3),
                "finish_reason": choice.get("finish_reason"),
                "usage": response.get("usage") or {},
                "response_id": response.get("id"),
            }
            lock_path = cache_path.with_suffix(cache_path.suffix + ".lock")
            lock_path.parent.mkdir(parents=True, exist_ok=True)
            with lock_path.open("a+", encoding="utf-8") as lock:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
                if cache_path.is_file():
                    cached = json.loads(cache_path.read_text(encoding="utf-8"))
                    cached_value = cached["value"]
                    Draft202012Validator(output_schema).validate(cached_value)
                    if canonical_json_sha256(cached_value) != cached["response_sha256"]:
                        raise StructuredModelInvocationError(
                            f"Local structured cache hash mismatch: {cache_path}"
                        )
                    return StructuredModelResponse(
                        value=cached_value,
                        model=self.model,
                        request_sha256=request_sha256,
                        response_sha256=cached["response_sha256"],
                        cache_hit=True,
                        invocation=cached["invocation"],
                    )
                self._atomic_json(
                    cache_path,
                    {
                        "schema_version": 1,
                        "request_sha256": request_sha256,
                        "response_sha256": response_sha256,
                        "model": self.model,
                        "model_revision": self.model_revision,
                        "purpose": purpose,
                        "value": value,
                        "invocation": invocation,
                    },
                )
            return StructuredModelResponse(
                value=value,
                model=self.model,
                request_sha256=request_sha256,
                response_sha256=response_sha256,
                cache_hit=False,
                invocation=invocation,
            )
        raise StructuredModelInvocationError(
            f"Structured local call failed for {purpose} after {self.retries + 1} attempts: "
            f"{last_error}"
        )

    def _write_failure_artifact(
        self,
        *,
        purpose: str,
        request_sha256: str,
        attempt: int,
        started: datetime,
        error_type: str,
        error_message: str,
        response: dict[str, Any] | None,
        choice: dict[str, Any] | None,
        content: str,
    ) -> None:
        """Persist bounded local-judge failure evidence without copying prompts."""

        finished = datetime.now(UTC)
        safe_purpose = "".join(
            character if character.isalnum() or character in {"-", "_"} else "_"
            for character in purpose
        )
        path = (
            self.cache_root
            / "_failures"
            / safe_purpose
            / f"{request_sha256}.attempt-{attempt}.json"
        )
        self._atomic_json(
            path,
            {
                "schema_version": 1,
                "model": self.model,
                "purpose": purpose,
                "request_sha256": request_sha256,
                "attempt": attempt,
                "started_at": started.isoformat(),
                "finished_at": finished.isoformat(),
                "elapsed_seconds": round((finished - started).total_seconds(), 3),
                "error_type": error_type,
                "error_message": error_message[:1000],
                "response_id": response.get("id") if isinstance(response, dict) else None,
                "finish_reason": choice.get("finish_reason") if isinstance(choice, dict) else None,
                "content_tail": content[-4000:],
                "usage": response.get("usage") if isinstance(response, dict) else None,
            },
        )

    @staticmethod
    def _atomic_json(path: Path, value: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        temporary.replace(path)
