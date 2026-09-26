import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from legal_skill_guard.inference.openai_client import ChatClient, GenerationConfig


class ModelsHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        body = json.dumps({"data": [{"id": "local-model"}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:
        return


class EmptyCompletionHandler(BaseHTTPRequestHandler):
    last_payload = None

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        type(self).last_payload = json.loads(self.rfile.read(length))
        body = json.dumps(
            {
                "id": "empty-but-auditable",
                "choices": [
                    {"finish_reason": "stop", "message": {"content": ""}}
                ],
                "usage": {"prompt_tokens": 17, "completion_tokens": 0},
            }
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:
        return


def test_loopback_client_bypasses_environment_proxy(monkeypatch) -> None:
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:1")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:1")
    monkeypatch.setenv("ALL_PROXY", "http://127.0.0.1:1")
    monkeypatch.delenv("NO_PROXY", raising=False)
    server = ThreadingHTTPServer(("127.0.0.1", 0), ModelsHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        client = ChatClient(f"http://127.0.0.1:{server.server_port}/v1", "local-model", retries=0)
        assert client.is_ready()
    finally:
        server.shutdown()
        thread.join()
        server.server_close()
        os.environ.pop("NO_PROXY", None)


def test_empty_completion_is_preserved_for_role_level_repair() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), EmptyCompletionHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        client = ChatClient(
            f"http://127.0.0.1:{server.server_port}/v1",
            "local-model",
            retries=0,
        )
        response = client.generate(
            [{"role": "user", "content": "return structured output"}],
            GenerationConfig(
                temperature=0.0,
                top_p=1.0,
                max_tokens=32,
                seed=0,
                reasoning_effort="medium",
            ),
        )
        assert response.content == ""
        assert response.finish_reason == "stop"
        assert response.prompt_tokens == 17
        assert response.completion_tokens == 0
        assert response.raw_id == "empty-but-auditable"
        assert EmptyCompletionHandler.last_payload["reasoning_effort"] == "medium"
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def test_readiness_binds_live_model_root_and_context(tmp_path) -> None:
    expected_root = tmp_path / "frozen-model"
    expected_root.mkdir()
    client = ChatClient(
        "http://127.0.0.1:8000/v1",
        "local-model",
        retries=0,
        expected_model_root=expected_root,
        expected_max_model_len=16384,
    )
    client._request = lambda method, path: {  # type: ignore[method-assign]
        "data": [
            {
                "id": "local-model",
                "root": str(expected_root),
                "max_model_len": 16384,
            }
        ]
    }

    readiness = client.readiness()

    assert readiness["ready"] is True
    assert readiness["checks"] == {
        "model_id_matches": True,
        "model_root_matches": True,
        "max_model_len_matches": True,
    }


def test_readiness_rejects_same_name_with_wrong_snapshot(tmp_path) -> None:
    client = ChatClient(
        "http://127.0.0.1:8000/v1",
        "local-model",
        retries=0,
        expected_model_root=tmp_path / "expected",
        expected_max_model_len=16384,
    )
    client._request = lambda method, path: {  # type: ignore[method-assign]
        "data": [
            {
                "id": "local-model",
                "root": str(tmp_path / "old-snapshot"),
                "max_model_len": 8192,
            }
        ]
    }

    readiness = client.readiness()

    assert readiness["ready"] is False
    assert readiness["failed_checks"] == [
        "model_root_matches",
        "max_model_len_matches",
    ]
