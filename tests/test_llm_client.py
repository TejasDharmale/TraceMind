"""Tests for llm_client using a throwaway local HTTP server (no real Ollama)."""
import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from tracemind.llm_client import OllamaError, explain_changes


@pytest.fixture
def fake_ollama():
    """Start a stub Ollama. Set .status and .reply to control its answer."""
    state = {"status": 200, "reply": {"message": {"content": "Prices now round down."}},
             "requests": []}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers["Content-Length"])
            state["requests"].append(json.loads(self.rfile.read(length)))
            body = json.dumps(state["reply"]).encode()
            self.send_response(state["status"])
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    state["host"] = f"127.0.0.1:{server.server_port}"
    yield state
    server.shutdown()
    server.server_close()


def test_returns_the_models_answer_and_sends_the_changes(fake_ollama):
    answer = explain_changes(
        ["final_price[12.34, 15]: 10.49 -> 10.48"],
        model="mistral",
        host=fake_ollama["host"],
    )

    assert answer == "Prices now round down."
    sent = fake_ollama["requests"][0]
    assert sent["model"] == "mistral"
    assert sent["stream"] is False
    assert "10.49 -> 10.48" in sent["messages"][-1]["content"]


def test_strips_think_blocks(fake_ollama):
    fake_ollama["reply"] = {"message": {"content": "<think>hmm</think>\nIt rounds down now."}}

    assert explain_changes("a -> b", host=fake_ollama["host"]) == "It rounds down now."


def test_missing_model_gives_a_helpful_error(fake_ollama):
    fake_ollama["status"] = 404
    fake_ollama["reply"] = {"error": "model 'nope' not found"}

    with pytest.raises(OllamaError, match="ollama pull nope"):
        explain_changes("a -> b", model="nope", host=fake_ollama["host"])


def test_ollama_not_running_raises_ollama_error():
    with socket.socket() as sock:  # grab a port that nothing is listening on
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]

    with pytest.raises(OllamaError, match="Could not reach Ollama"):
        explain_changes("a -> b", host=f"127.0.0.1:{port}", timeout=2)


def test_empty_changes_are_rejected():
    with pytest.raises(ValueError):
        explain_changes([])
