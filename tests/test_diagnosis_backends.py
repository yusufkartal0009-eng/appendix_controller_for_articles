"""Backends of the optional model step (#34). Mock clients only: nothing here calls a real model or the network."""

import io
import json
import subprocess
import sys
import urllib.error
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.config import STATUS_FAILED, STATUS_NEEDS_REVIEW
from src.diagnosis.backends import (
    ENV_BACKEND,
    ENV_LOCAL_URL,
    ENV_MODEL,
    AnthropicBackend,
    BackendUnavailable,
    LocalBackend,
    NullBackend,
    check_restatement,
    explain,
    select_backend,
    status_for,
)

REPO = Path(__file__).resolve().parent.parent
REPORT = "The run phase ended with status COMPLETED and exit code 0 after 465.777 s. Peak memory 1.15 GiB."


class MockMessages:
    def __init__(self, text=None, error=None):
        self.text, self.error, self.calls = text, error, []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return SimpleNamespace(content=[SimpleNamespace(text=self.text)])


def mock_client(text=None, error=None):
    return SimpleNamespace(messages=MockMessages(text, error))


# ---------------------------------------------------------------- selection


def test_the_default_backend_is_null_and_sends_nothing():
    assert isinstance(select_backend({}), NullBackend)
    assert isinstance(select_backend({ENV_BACKEND: "null"}), NullBackend)
    assert NullBackend().restate("s", "t") is None


def test_selection_reads_the_environment_only_and_needs_complete_settings():
    assert isinstance(select_backend({ENV_BACKEND: "Anthropic", ENV_MODEL: "some-model"}), AnthropicBackend)
    local = select_backend({ENV_BACKEND: "local", ENV_MODEL: "m", ENV_LOCAL_URL: "http://localhost:8080/"})
    assert isinstance(local, LocalBackend) and local.url == "http://localhost:8080/v1/chat/completions"
    with pytest.raises(BackendUnavailable):
        select_backend({ENV_BACKEND: "anthropic"})
    with pytest.raises(BackendUnavailable):
        select_backend({ENV_BACKEND: "local", ENV_MODEL: "m"})
    with pytest.raises(ValueError):
        select_backend({ENV_BACKEND: "carrier-pigeon"})


def test_the_anthropic_backend_refuses_to_start_without_a_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(BackendUnavailable, match="ANTHROPIC_API_KEY"):
        AnthropicBackend("m").restate("s", "t")


def test_the_anthropic_backend_calls_the_client_it_is_given():
    client = mock_client("A short restatement.")
    assert AnthropicBackend("some-model", client).restate("SYS", "TASK") == "A short restatement."
    call = client.messages.calls[0]
    assert call["model"] == "some-model" and call["system"] == "SYS"
    assert call["messages"] == [{"role": "user", "content": "TASK"}]


def test_a_failing_client_becomes_backend_unavailable():
    with pytest.raises(BackendUnavailable):
        AnthropicBackend("m", mock_client(error=RuntimeError("boom"))).restate("s", "t")
    with pytest.raises(BackendUnavailable):
        AnthropicBackend("m", mock_client(text="  ")).restate("s", "t")


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_the_local_backend_posts_to_the_chat_endpoint_and_reads_the_answer():
    seen = {}

    def opener(request, timeout):
        seen["url"], seen["body"] = request.full_url, json.loads(request.data)
        return FakeResponse(json.dumps({"choices": [{"message": {"content": " local text "}}]}).encode())

    backend = LocalBackend("http://localhost:11434", "m", opener=opener)
    assert backend.restate("SYS", "TASK") == "local text"
    assert seen["url"] == "http://localhost:11434/v1/chat/completions"
    assert seen["body"]["messages"][0] == {"role": "system", "content": "SYS"}


def test_an_offline_local_server_is_a_graceful_fallback():
    def offline(request, timeout):
        raise urllib.error.URLError("connection refused")

    result = explain(REPORT, STATUS_NEEDS_REVIEW, LocalBackend("http://localhost:1", "m", opener=offline))
    assert result.restatement is None and "unavailable" in result.rejected_reason
    assert result.to_markdown().startswith(REPORT)


def test_a_malformed_local_answer_is_a_graceful_fallback():
    opener = lambda request, timeout: FakeResponse(b"{not json")
    result = explain(REPORT, STATUS_NEEDS_REVIEW, LocalBackend("http://localhost:1", "m", opener=opener))
    assert result.restatement is None


# ---------------------------------------------------------------- the number lock


def test_a_restatement_with_only_the_numbers_of_the_report_is_shown_after_the_report():
    backend = AnthropicBackend("m", mock_client("The run ended with exit code 0 after 465.777 s."))
    result = explain(REPORT, STATUS_NEEDS_REVIEW, backend)
    markdown = result.to_markdown()
    assert result.restatement and markdown.startswith(REPORT)
    assert markdown.index(REPORT) < markdown.index("Plain-language restatement")


def test_a_restatement_that_changes_a_number_is_dropped_and_the_report_is_unchanged():
    backend = AnthropicBackend("m", mock_client("The run took 466 s and used 1.2 GiB."))
    result = explain(REPORT, STATUS_NEEDS_REVIEW, backend)
    assert result.restatement is None
    assert "numbers that are not in the report: 466, 1.2" in result.rejected_reason
    assert result.rule_based == REPORT and REPORT in result.to_markdown()


def test_a_restatement_with_a_loaded_word_is_dropped():
    assert "loaded words: sloppy" in check_restatement(REPORT, "The authors were sloppy.")
    assert check_restatement(REPORT, "The run ended with exit code 0.") is None


def test_numbers_are_compared_character_for_character():
    assert check_restatement("It took 0.50 s.", "It took 0.5 s.") is not None
    assert check_restatement("It took 0.50 s.", "It took 0.50 s.") is None


def test_the_null_backend_returns_the_report_alone():
    result = explain(REPORT, STATUS_FAILED, NullBackend())
    assert result.to_markdown() == REPORT and result.backend == "null"


def test_the_prompt_sent_to_the_model_locks_the_numbers_and_names_the_status():
    client = mock_client("ok")
    explain(REPORT, STATUS_FAILED, AnthropicBackend("m", client), quoted_log_lines="stderr.log:3: Error")
    call = client.messages.calls[0]
    assert "465.777" in call["system"] and "Status of this run: Failed" in call["messages"][0]["content"]
    assert "stderr.log:3: Error" in call["messages"][0]["content"]


def test_status_without_a_score_is_never_verified():
    assert status_for(False) == STATUS_FAILED and status_for(True) == STATUS_NEEDS_REVIEW


# ---------------------------------------------------------------- the CLI


def test_cli_explain_without_a_backend_prints_the_report_alone():
    folder = (REPO / "data" / "pilot3_runs" / "paper_004").as_posix()
    env = {k: v for k, v in __import__("os").environ.items() if not k.startswith("REPRO_RADAR_")}
    plain = subprocess.run([sys.executable, "cli.py", "diagnose", folder], cwd=REPO, capture_output=True, text=True,
                           check=True, env=env)
    explained = subprocess.run([sys.executable, "cli.py", "diagnose", folder, "--explain"], cwd=REPO, capture_output=True,
                               text=True, check=True, env=env)
    assert explained.stdout == plain.stdout


def test_cli_explain_with_an_incomplete_setting_exits_1():
    folder = (REPO / "data" / "pilot3_runs" / "paper_004").as_posix()
    env = {**__import__("os").environ, ENV_BACKEND: "anthropic"}
    env.pop(ENV_MODEL, None)
    result = subprocess.run([sys.executable, "cli.py", "diagnose", folder, "--explain"], cwd=REPO, capture_output=True,
                            text=True, check=False, env=env)
    assert result.returncode == 1 and ENV_MODEL in result.stderr
