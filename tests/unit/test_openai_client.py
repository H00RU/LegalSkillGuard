import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from legal_skill_guard.inference.openai_client import ChatClient


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


def test_loopback_client_bypasses_environment_proxy(monkeypatch) -> None:
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:1")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:1")
    monkeypatch.setenv("ALL_PROXY", "http://127.0.0.1:1")
    monkeypatch.delenv("NO_PROXY", raising=False)
    server = ThreadingHTTPServer(("127.0.0.1", 0), ModelsHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        client = ChatClient(
            f"http://127.0.0.1:{server.server_port}/v1", "local-model", retries=0
        )
        assert client.is_ready()
    finally:
        server.shutdown()
        thread.join()
        server.server_close()
        os.environ.pop("NO_PROXY", None)
