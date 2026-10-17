"""Actual-request recording, restored from successful ADD event 71935."""

import json
from pathlib import Path
from urllib import request

from .openai_client import ChatClient

ROOT = Path(__file__).resolve().parents[2]


class WireClient(ChatClient):
    def __init__(self, config: dict):
        super().__init__(
            base_url=config["base_url"],
            model=config["model"],
            retries=0,
            timeout_seconds=config["timeout_seconds"],
            expected_model_root=ROOT / config["model_root"],
            expected_max_model_len=config["context_tokens"],
        )
        self.disable_thinking = config.get("disable_thinking", False)
        if type(self.disable_thinking) is not bool:
            raise ValueError("disable_thinking must be an explicit boolean")
        self.native = []

    def generate(self, messages, generation):
        if generation.disable_thinking != self.disable_thinking:
            raise ValueError("Generation and serving-tokenizer thinking profiles differ")
        return super().generate(messages, generation)

    def token_count(self, *, messages=None, text=None):
        """Count with the actual serving tokenizer, not a replacement model.

        The on-disk tokenizer was lost. The same live server retains it. This is
        a deterministic tokenization request, not a generation or a fallback.
        """
        if (messages is None) == (text is None):
            raise ValueError("Exactly one tokenization input required")
        payload = {"model": self.model, "add_special_tokens": False}
        if messages is not None:
            payload.update(
                messages=messages,
                add_generation_prompt=True,
                chat_template_kwargs={"enable_thinking": not self.disable_thinking},
            )
        else:
            payload["prompt"] = text
        req = request.Request(
            self.base_url.removesuffix("/v1") + "/tokenize",
            data=json.dumps(payload, ensure_ascii=False).encode(),
            headers={"Content-Type": "application/json", "Authorization": "Bearer " + self.api_key},
            method="POST",
        )
        with self.opener.open(req, timeout=self.timeout_seconds) as response:
            value = json.load(response)
        if (
            type(value["count"]) is not int
            or value["count"] != len(value["tokens"])
            or value["max_model_len"] != self.expected_max_model_len
        ):
            raise ValueError("Serving tokenizer contract mismatch")
        return value["count"]

    def _request(self, method, path, payload=None):
        entry = {"request": payload}
        if method == "POST":
            self.native.append(entry)
        try:
            entry["response"] = super()._request(method, path, payload)
            return entry["response"]
        except Exception as exc:
            entry["error"] = repr(exc)
            raise
