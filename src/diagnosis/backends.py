"""Backends for the optional language-model step of the diagnosis (#34, docs/DIAGNOSIS.md section 6).

The default is `NullBackend`: nothing is sent anywhere. A model is used only when the environment says so
(`REPRO_RADAR_DIAGNOSIS_BACKEND`), the key is read from the environment by the SDK and never stored, and the answer is
checked before it is shown. **The rule-based report is never replaced**: a model answer is added as a separate, labeled
section, and only if every number in it occurs in the rule-based report character for character and it contains no loaded
word. Otherwise it is dropped and the reason is given.

Nothing here has been run against a real model: the tests use a mock client only.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from src.config import STATUS_FAILED, STATUS_NEEDS_REVIEW
from src.diagnosis.prompts import check_neutral_language, numbers_in, render_prompt

ENV_BACKEND = "REPRO_RADAR_DIAGNOSIS_BACKEND"  # null (default) | anthropic | local
ENV_MODEL = "REPRO_RADAR_DIAGNOSIS_MODEL"
ENV_LOCAL_URL = "REPRO_RADAR_LOCAL_LLM_URL"  # a server with an OpenAI-style /v1/chat/completions (llama.cpp, Ollama)
MAX_TOKENS = 700
LOCAL_TIMEOUT_SECONDS = 120


class BackendUnavailable(Exception):
    """The chosen backend cannot be used (missing setting, no key, server offline, no usable answer)."""


class Backend(Protocol):
    name: str

    def restate(self, system: str, task: str) -> str | None:
        """The model's text for a prompt, or None when this backend produces none."""


class NullBackend:
    """The default: no model, no network."""

    name = "null"

    def restate(self, system: str, task: str) -> str | None:
        return None


class AnthropicBackend:
    """The Claude API through the SDK. The key (`ANTHROPIC_API_KEY`) is read from the environment by the SDK."""

    name = "anthropic"

    def __init__(self, model: str, client: Any | None = None) -> None:
        self.model = model
        self._client = client

    def _get_client(self) -> Any:
        if self._client is None:
            import anthropic

            if not os.environ.get("ANTHROPIC_API_KEY"):
                raise BackendUnavailable("ANTHROPIC_API_KEY is not set")
            self._client = anthropic.Anthropic()
        return self._client

    def restate(self, system: str, task: str) -> str | None:
        client = self._get_client()
        try:
            response = client.messages.create(model=self.model, max_tokens=MAX_TOKENS, system=system,
                                              messages=[{"role": "user", "content": task}])
        except Exception as exc:
            raise BackendUnavailable(f"{type(exc).__name__}: {exc}") from exc
        parts = [getattr(block, "text", "") for block in getattr(response, "content", [])]
        text = "".join(parts).strip()
        if not text:
            raise BackendUnavailable("the model returned no text")
        return text


class LocalBackend:
    """A model served on this machine through an OpenAI-style chat endpoint (llama.cpp server, Ollama, vLLM)."""

    name = "local"

    def __init__(self, base_url: str, model: str, opener: Callable[..., Any] | None = None) -> None:
        self.url = base_url.rstrip("/") + "/v1/chat/completions"
        self.model = model
        self._open = opener or urllib.request.urlopen

    def restate(self, system: str, task: str) -> str | None:
        body = json.dumps({"model": self.model, "max_tokens": MAX_TOKENS,
                           "messages": [{"role": "system", "content": system}, {"role": "user", "content": task}]}).encode()
        request = urllib.request.Request(self.url, data=body, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with self._open(request, timeout=LOCAL_TIMEOUT_SECONDS) as response:
                payload = json.loads(response.read().decode("utf-8"))
            text = payload["choices"][0]["message"]["content"].strip()
        except (urllib.error.URLError, OSError, ValueError, KeyError, IndexError, TypeError) as exc:
            raise BackendUnavailable(f"local model server: {type(exc).__name__}: {exc}") from exc
        if not text:
            raise BackendUnavailable("the local model returned no text")
        return text


def select_backend(env: Mapping[str, str] | None = None) -> Backend:
    """The backend the environment names; `NullBackend` when it names none. Raises BackendUnavailable for a setting that is
    incomplete and ValueError for an unknown backend name."""
    env = os.environ if env is None else env
    name = (env.get(ENV_BACKEND) or "null").strip().lower()
    if name == "null":
        return NullBackend()
    model = env.get(ENV_MODEL)
    if name == "anthropic":
        if not model:
            raise BackendUnavailable(f"{ENV_MODEL} is not set (no model name is assumed)")
        return AnthropicBackend(model)
    if name == "local":
        url = env.get(ENV_LOCAL_URL)
        if not url or not model:
            raise BackendUnavailable(f"{ENV_LOCAL_URL} and {ENV_MODEL} must both be set for the local backend")
        return LocalBackend(url, model)
    raise ValueError(f"unknown backend {name!r}; choose null, anthropic, or local")


@dataclass
class Explained:
    """The rule-based report, always unchanged, and the model's checked restatement when there is one."""

    rule_based: str
    restatement: str | None
    backend: str
    rejected_reason: str | None = None

    def to_markdown(self) -> str:
        text = self.rule_based
        if self.restatement:
            text += (f"\n## Plain-language restatement (written by a language model: `{self.backend}`; "
                     "every number in it occurs in the report above)\n\n" + self.restatement.strip() + "\n")
        elif self.rejected_reason:
            text += f"\n*No model restatement is shown: {self.rejected_reason}*\n"
        return text


def check_restatement(rule_based: str, restatement: str) -> str | None:
    """None if the model text may be shown; otherwise the reason it may not. The numbers of the report are locked."""
    locked = set(numbers_in(rule_based))
    foreign = [n for n in numbers_in(restatement) if n not in locked]
    if foreign:
        return f"the model text contains numbers that are not in the report: {', '.join(foreign)}"
    loaded = check_neutral_language(restatement)
    if loaded:
        return f"the model text contains loaded words: {', '.join(loaded)}"
    return None


def status_for(pilot_success: bool) -> str:
    """The prompt status when no scored status is given: a diagnosis alone never declares a run verified."""
    return STATUS_NEEDS_REVIEW if pilot_success else STATUS_FAILED


def explain(rule_based: str, status: str, backend: Backend, quoted_log_lines: str = "(none)") -> Explained:
    """Ask the backend to restate the rule-based report and keep its answer only if it passes `check_restatement`."""
    if isinstance(backend, NullBackend):
        return Explained(rule_based, None, backend.name)
    system, task = render_prompt(status, rule_based, quoted_log_lines)
    try:
        text = backend.restate(system, task)
    except BackendUnavailable as exc:
        return Explained(rule_based, None, backend.name, f"the backend was unavailable ({exc})")
    if not text:
        return Explained(rule_based, None, backend.name, "the backend returned no text")
    reason = check_restatement(rule_based, text)
    if reason:
        return Explained(rule_based, None, backend.name, reason)
    return Explained(rule_based, text, backend.name)
