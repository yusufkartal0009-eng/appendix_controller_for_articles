"""Unit tests for the GitHub backlog provisioning script's command construction."""

import subprocess
from unittest.mock import patch

from scripts import setup_github_backlog as backlog


def _fake_run(*args, **kwargs):
    return subprocess.CompletedProcess(args=args[0], returncode=0, stdout="", stderr="")


def test_backlog_commands_never_use_shell_and_pass_body_via_stdin(monkeypatch):
    hostile_body = 'Body with "quotes", `backticks`, $(whoami) and %USERNAME%'
    monkeypatch.setattr(backlog, "LABELS", [("area:test", "ffffff", "Label $(id)")])
    monkeypatch.setattr(backlog, "MILESTONES", ['M9: "Quoted" milestone'])
    monkeypatch.setattr(
        backlog,
        "ISSUES",
        [{"title": "feat(test): `x`", "milestone": "M9", "labels": ["area:test"], "body": hostile_body}],
    )
    monkeypatch.setattr(backlog.time, "sleep", lambda _seconds: None)

    with patch.object(backlog.subprocess, "run", side_effect=_fake_run) as run:
        backlog.main()

    assert run.call_count > 0
    for call in run.call_args_list:
        cmd = call.args[0]
        assert isinstance(cmd, list), f"expected an argument list, got {cmd!r}"
        assert call.kwargs.get("shell", False) is False

    issue_calls = [c for c in run.call_args_list if c.args[0][:3] == ["gh", "issue", "create"]]
    assert len(issue_calls) == 1
    assert hostile_body not in issue_calls[0].args[0]
    assert issue_calls[0].kwargs["input"] == hostile_body
