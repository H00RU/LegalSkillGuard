"""No-retry wire client for the existing local executor and bounded teacher.

Only a sealed preflight allowlist can dispatch generation. GET/tokenization are
recorded separately from model-generation reservations and do not generate text.
"""
from __future__ import annotations

import base64
import hashlib
import json
import time
from dataclasses import asdict
from pathlib import Path
from urllib import error, parse, request

from .checkpoint import immutable_json
from .coverage import digest
from .ledger import PURPOSES, BudgetError, BudgetLedger


class WireError(RuntimeError):
    pass


class ExecutorClient:
    def __init__(self, ledger: BudgetLedger | None, artifacts: Path, config: dict, *, opener=None):
        self.ledger, self.artifacts, self.config = ledger, Path(artifacts), config
        url = parse.urlparse(config["base_url"])
        if (url.scheme, url.hostname, url.port, url.path) != ("http", "127.0.0.1", 8000, "/v1"):
            raise BudgetError("Only the previously authorized loopback executor is allowed")
        if config["model"] != "Qwen/Qwen3-8B" or config["model_retries"] != 0:
            raise BudgetError("Executor identity or no-hidden-retries contract differs")
        self.opener = opener or request.build_opener(request.ProxyHandler({}))

    def _wire(self, method: str, endpoint: str, payload: dict | None = None) -> tuple[dict, bytes]:
        body = json.dumps(payload, ensure_ascii=False).encode() if payload is not None else None
        req = request.Request(self.config["base_url"] + endpoint, data=body,
                              headers={"Content-Type": "application/json"}, method=method)
        with self.opener.open(req, timeout=self.config["timeout_seconds"]) as response:
            raw = response.read()
            return json.loads(raw), raw

    def readiness(self) -> dict:
        data, _ = self._wire("GET", "/models")
        cards = [c for c in data.get("data", []) if c.get("id") == self.config["model"]]
        if len(cards) != 1:
            raise WireError("Loaded executor model card does not match")
        card = cards[0]
        if Path(card["root"]).resolve() != Path(self.config["model_root"]).resolve() or \
                card["max_model_len"] != self.config["context_tokens"]:
            raise WireError("Loaded executor path/context differs from sealed configuration")
        return {"ready": True, "card": card, "generation_requests": 0}

    def tokenize(self, messages: list[dict], *, thinking: bool) -> dict:
        if type(thinking) is not bool:
            raise ValueError("Explicit thinking boolean required")
        # /tokenize lives outside the /v1 namespace.
        endpoint = self.config["base_url"].removesuffix("/v1") + "/tokenize"
        payload = {"model": self.config["model"], "messages": messages,
                   "add_special_tokens": False,
                   "add_generation_prompt": True,
                   "chat_template_kwargs": {"enable_thinking": thinking}}
        req = request.Request(endpoint, data=json.dumps(payload, ensure_ascii=False).encode(),
                              headers={"Content-Type": "application/json"}, method="POST")
        with self.opener.open(req, timeout=self.config["timeout_seconds"]) as response:
            result = json.load(response)
        if type(result.get("count")) is not int or result["count"] != len(result.get("tokens", [])):
            raise WireError("Serving tokenizer returned an invalid count")
        return result

    def validate_scope(self, source: str, purpose: str, thinking: bool):
        if self.ledger is None:
            raise BudgetError("Read-only environment client cannot generate text")
        self.ledger._source(source)
        if purpose not in PURPOSES or purpose == "pilot_teacher_summary" or type(thinking) is not bool:
            raise BudgetError("Executor source/purpose/thinking profile outside preflight policy")

    def payload(self, *, messages, thinking, schema=None):
        cfg = self.config
        payload = {"model": cfg["model"], "messages": messages,
                   "temperature": cfg["temperature"], "top_p": cfg["top_p"],
                   "top_k": cfg["top_k"], "max_tokens": cfg["max_tokens"],
                   "seed": cfg["seed"], "chat_template_kwargs": {"enable_thinking": thinking}}
        if schema is not None:
            payload["response_format"] = {"type": "json_schema", "json_schema": {
                "name": "rr_joint_proposal", "strict": True, "schema": schema}}
        return payload

    def generate(self, call_id: str, *, source: str, purpose: str, messages: list[dict],
                 thinking: bool, schema: dict | None = None) -> dict:
        self.validate_scope(source, purpose, thinking)
        cfg = self.config
        payload = self.payload(messages=messages, thinking=thinking, schema=schema)
        binding = {"thinking": thinking, "payload": payload}
        # Completed-record reuse must precede any context/health request on
        # resume, but cannot precede the ledger's exact input/config hash check.
        with self.ledger.transaction() as db:
            existing = db.execute("SELECT 1 FROM calls WHERE id=?", (call_id,)).fetchone()
        if existing:
            prior = self.ledger.reserve(call_id, role="executor", purpose=purpose,
                                        source=source, request=binding)
            return {**prior["result"], "cache_hit": True}
        # Deterministic tokenization does not consume a generation reservation.
        tokenization = self.tokenize(messages, thinking=thinking)
        if tokenization["count"] + cfg["max_tokens"] > cfg["context_tokens"]:
            raise WireError("Full public input plus reserved output exceeds context; no truncation")
        reserved = self.ledger.reserve(call_id, role="executor", purpose=purpose,
                                       source=source, request=binding)
        if not reserved["dispatch"]:
            return {**reserved["result"], "cache_hit": True}
        path = self.artifacts / "calls" / digest(call_id)
        immutable_json(path / "request.json", {"id": call_id, "source": source, "purpose": purpose,
                       "request_hash": reserved["request_hash"], "payload": payload,
                       "tokenization": tokenization, "generation_call_already_reserved": True})
        # Preserve the literal body: schema property order controls xgrammar.
        wire_body = json.dumps(payload, ensure_ascii=False).encode()
        immutable_json(path / "wire_request.json", {"body_b64": base64.b64encode(wire_body).decode(),
                       "body_sha256": hashlib.sha256(wire_body).hexdigest(), "method": "POST",
                       "endpoint": self.config['base_url'] + '/chat/completions'})
        started = time.monotonic()
        try:
            value, raw = self._wire("POST", "/chat/completions", payload)
            immutable_json(path / "wire_response.json", {"body_b64": base64.b64encode(raw).decode(),
                           "elapsed_seconds": time.monotonic() - started})
            choices = value.get("choices") or []
            if not choices:
                raise WireError("Executor returned no choices")
            msg = choices[0].get("message", {})
            usage = value.get("usage")
            if not isinstance(usage, dict):
                raise WireError("Missing executor token accounting")
            content = msg.get("content") or ""
            result = {"content": content, "reasoning_content": msg.get("reasoning_content"),
                      "finish_reason": choices[0].get("finish_reason"), "raw_id": value.get("id"),
                      "usage": usage, "thinking_requested": thinking,
                      "serving_template_tokens_sha256": digest(tokenization["tokens"]),
                      "serving_template_suffix_tokens": tokenization["tokens"][-24:],
                      "elapsed_seconds": time.monotonic() - started,
                      "incremental_api_cash_usd": 0, "gpu_cost_usd": None,
                      "billing_basis": "existing_local_service_no_per_request_API_invoice",
                      "request_hash": reserved["request_hash"], "artifact_directory": str(path)}
            immutable_json(path / "result.json", result)
            self.ledger.finish(call_id, status="completed", result=result)
            return {**result, "cache_hit": False}
        except Exception as exc:
            diagnostic = {"error_type": type(exc).__name__, "error": str(exc),
                          "elapsed_seconds": time.monotonic() - started,
                          "usage": None, "incremental_api_cash_usd": 0,
                          "gpu_cost_usd": None, "reserved_and_charged": True}
            if isinstance(exc, error.HTTPError):
                diagnostic["http_response_body_b64"] = base64.b64encode(exc.read()).decode()
            immutable_json(path / "failure.json", diagnostic)
            self.ledger.finish(call_id, status="failed", result=diagnostic)
            raise WireError(f"Charged executor request failed: {call_id}: {type(exc).__name__}") from exc


class TeacherClient:
    """The existing Codex teacher adapter, with zero retries and the same ledger."""
    def __init__(self, ledger: BudgetLedger, artifacts: Path, config: dict, *, adapter=None):
        from legal_skill_guard.inference.codex_cli_client import CodexCLIClient
        if config["retries"] != 0:
            raise BudgetError("Teacher hidden retries are forbidden")
        self.ledger, self.artifacts, self.config = ledger, Path(artifacts), config
        self.adapter = adapter or CodexCLIClient(
            model=config["model"], reasoning_effort=config["reasoning_effort"],
            timeout_seconds=config["timeout_seconds"], retries=0, executable=config["executable"],
            cache_root=Path(artifacts) / "teacher_adapter_cache")

    def summarize(self, call_id: str, *, source_ids: list[str], system_prompt: str,
                  user_prompt: str, output_schema: dict) -> dict:
        if not source_ids or len(source_ids) > 16 or len(set(source_ids)) != len(source_ids):
            raise BudgetError("Teacher summaries use one bounded training batch")
        for source in source_ids:
            self.ledger._source(source)
        kwargs = {"purpose": self.summary_purpose, "system_prompt": system_prompt,
                  "user_prompt": user_prompt, "output_schema": output_schema}
        request_value = {"source_ids": source_ids, "config": self.config, **kwargs}
        reservation = self.ledger.reserve(call_id, role="teacher", purpose=self.summary_purpose,
                                          source=source_ids[0], request=request_value)
        if not reservation["dispatch"]:
            return {**reservation["result"], "ledger_cache_hit": True}
        path = self.artifacts / "calls" / digest(call_id)
        immutable_json(path / "request.json", request_value)
        start = time.monotonic()
        try:
            response = self.adapter.generate_json(**kwargs)
            result = {**asdict(response), "elapsed_seconds": time.monotonic() - start,
                      "source_ids": source_ids, "billing_basis": "existing_authorized_teacher_adapter",
                      "actual_cash_invoice_available": False}
            immutable_json(path / "result.json", result)
            self.ledger.finish(call_id, status="completed", result=result)
            return result
        except Exception as exc:
            failure = {"error_type": type(exc).__name__, "error": str(exc),
                       "elapsed_seconds": time.monotonic() - start, "reserved_and_charged": True}
            immutable_json(path / "failure.json", failure)
            self.ledger.finish(call_id, status="failed", result=failure)
            raise
    summary_purpose = "pilot_teacher_summary"

