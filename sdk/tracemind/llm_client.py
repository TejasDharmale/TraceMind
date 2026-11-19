"""Ask a local Ollama model to explain behaviour changes between app versions.

Uses only the standard library (urllib), so TraceMind keeps zero dependencies.
Nothing leaves your machine: Ollama runs locally.

Settings (environment variables, until config.py exists):
    TRACEMIND_LLM_MODEL   model name, default "mistral"
    OLLAMA_HOST           Ollama address, default "http://localhost:11434"
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Sequence

DEFAULT_MODEL = "mistral"
DEFAULT_HOST = "http://localhost:11434"
DEFAULT_TIMEOUT = 120.0  # local models can be slow on a laptop
MAX_PROMPT_CHARS = 6000  # keep prompts compact and fast

SYSTEM_PROMPT = (
    "You help developers understand how a software change affected behaviour. "
    "You are given a list of function calls whose results differ between two "
    "app versions. Explain in plain language what changed and why it might "
    "matter to users or the business. Be concise. Use only the facts given; "
    "if something is unclear, say so instead of guessing."
)


class OllamaError(Exception):
    """Ollama could not be reached or did not return a usable answer."""


def _base_url(host: str | None) -> str:
    host = host or os.environ.get("OLLAMA_HOST") or DEFAULT_HOST
    if "://" not in host:
        host = f"http://{host}"
    return host.rstrip("/")


def _format_changes(changes: str | Sequence[str]) -> str:
    if isinstance(changes, str):
        text = changes.strip()
    else:
        text = "\n".join(f"- {line}" for line in changes if str(line).strip())
    if len(text) > MAX_PROMPT_CHARS:
        text = f"{text[:MAX_PROMPT_CHARS]}\n...[truncated]"
    return text


def _strip_thinking(text: str) -> str:
    """Remove <think>...</think> blocks that reasoning models add."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)


def _http_error_message(error: urllib.error.HTTPError, model: str) -> str:
    try:
        detail = json.loads(error.read().decode("utf-8")).get("error", "")
    except Exception:
        detail = ""
    if error.code == 404:
        return f"Ollama says model '{model}' is not installed. Run: ollama pull {model}"
    return f"Ollama returned HTTP {error.code}. {detail}".strip()


def explain_changes(
    changes: str | Sequence[str],
    *,
    model: str | None = None,
    host: str | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> str:
    """Return a plain language explanation of ``changes``.

    ``changes`` is one string, or a list of lines such as
    ``"final_price[12.34, 15]: 10.49 -> 10.48"``.

    Raises ``OllamaError`` if Ollama is not running, the model is missing,
    the request times out, or the reply is unusable. Callers should treat
    the explanation as optional and keep going without it.
    """
    text = _format_changes(changes)
    if not text:
        raise ValueError("no changes to explain")

    model = model or os.environ.get("TRACEMIND_LLM_MODEL") or DEFAULT_MODEL
    base = _base_url(host)
    payload = {
        "model": model,
        "stream": False,
        "options": {"temperature": 0.2},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Changes between the two versions:\n{text}"},
        ],
    }
    request = urllib.request.Request(
        f"{base}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        raise OllamaError(_http_error_message(error, model)) from error
    except urllib.error.URLError as error:
        raise OllamaError(
            f"Could not reach Ollama at {base}. Is it running? ({error.reason})"
        ) from error
    except TimeoutError as error:
        raise OllamaError(f"Ollama did not answer within {timeout:g} seconds") from error
    except json.JSONDecodeError as error:
        raise OllamaError("Ollama sent a reply that is not valid JSON") from error

    try:
        answer = _strip_thinking(body["message"]["content"]).strip()
    except (KeyError, TypeError) as error:
        raise OllamaError("Ollama's reply had an unexpected shape") from error
    if not answer:
        raise OllamaError("Ollama returned an empty answer")
    return answer
