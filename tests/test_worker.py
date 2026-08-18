from __future__ import annotations

from pathlib import Path
from subprocess import CompletedProcess

import pytest

import stock_analysis.worker as worker


def test_claude_cli_preflight_runs_version_check(monkeypatch):
    cli_path = Path("/opt/claude-agent-sdk/_bundled/claude")
    calls: list[tuple[list[str], dict]] = []

    monkeypatch.setattr(worker, "_resolve_claude_cli", lambda: cli_path)
    monkeypatch.setattr(worker.os, "access", lambda _path, _mode: True)

    def fake_run(argv, **kwargs):
        calls.append((argv, kwargs))
        return CompletedProcess(argv, 0, stdout="1.2.3\n", stderr="")

    monkeypatch.setattr(worker.subprocess, "run", fake_run)

    assert worker.preflight_claude_cli() == "1.2.3"
    assert calls == [
        (
            [str(cli_path), "-v"],
            {
                "capture_output": True,
                "text": True,
                "timeout": 10,
                "check": False,
            },
        )
    ]


def test_claude_cli_preflight_fails_closed(monkeypatch):
    monkeypatch.setattr(
        worker, "_resolve_claude_cli", lambda: (_ for _ in ()).throw(FileNotFoundError())
    )

    with pytest.raises(RuntimeError, match="Claude CLI is not available"):
        worker.preflight_claude_cli()
