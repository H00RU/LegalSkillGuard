"""Verify the pinned local vLLM model endpoint with one deterministic request."""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def request_json(url: str, payload: dict[str, object] | None = None) -> dict[str, object]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="GET" if payload is None else "POST",
    )
    # The host environment may define a catch-all HTTP proxy that incorrectly
    # captures localhost.  A local model health check must never leave the host.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=30) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000/v1")
    parser.add_argument("--wait-seconds", type=int, default=300)
    parser.add_argument("--output", type=Path, default=ROOT / "reports/artifacts/vllm_smoke.json")
    args = parser.parse_args()
    deadline = time.monotonic() + args.wait_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            models = request_json(f"{args.base_url}/models")
            break
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            last_error = exc
            time.sleep(2)
    else:
        raise SystemExit(f"vLLM did not become ready: {last_error}")

    model_ids = [item["id"] for item in models.get("data", [])]
    import yaml

    roles_path = Path(__file__).resolve().parents[1] / "configs/models/roles.yaml"
    expected = str(
        yaml.safe_load(roles_path.read_text(encoding="utf-8"))["roles"]["lawyer_policy"]["model_id"]
    )
    if expected not in model_ids:
        raise SystemExit(f"unexpected served models: {model_ids}")
    completion = request_json(
        f"{args.base_url}/chat/completions",
        {
            "model": expected,
            "messages": [
                {"role": "system", "content": "只回答指定词语，不要解释。"},
                {"role": "user", "content": "回答：就绪"},
            ],
            "temperature": 0,
            "max_tokens": 32,
            "chat_template_kwargs": {"enable_thinking": False},
        },
    )
    content = completion["choices"][0]["message"]["content"]
    if "就绪" not in content:
        raise SystemExit(f"unexpected completion: {content!r}")
    result = {
        "status": "passed",
        "served_model": expected,
        "base_url": args.base_url,
        "response": content,
        "usage": completion.get("usage"),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
