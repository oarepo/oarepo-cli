# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Tests for `repository run`.

Delegation, argument wiring, and error/exit-code handling are covered here
by mocking `discover_context()`/`ServerRunner` (mirroring
test_repository_local.py's approach for the other "thin CLI wrapper over a
service" repository subcommands) -- the real `os.execve`/`os.execvpe`
process-replacement mechanics, argv/env construction, and signal-handoff
behavior are already covered thoroughly, against real (isolated-subprocess)
child processes, by test_server_runner.py.
`test_run_real_exec_replaces_process` additionally drives the full CLI ->
discover_context -> ServerRunner -> exec stack once, end to end, in its own
isolated subprocess (since a real exec would otherwise replace the pytest
worker itself), against a tiny fake `invenio-cli` binary.
"""

from __future__ import annotations

import stat
import subprocess
import sys
from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest
from typer.testing import CliRunner

from oarepo_cli.cli.main import app
from oarepo_cli.core.errors import ConfigurationError, ProcessExecutionError

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path


@pytest.fixture
def mock_context(monkeypatch: pytest.MonkeyPatch) -> Mock:
    """Mock discover_context() so no real project is needed."""
    context = Mock()
    monkeypatch.setattr("oarepo_cli.cli.repository.discover_context", lambda: context)
    return context


def _fake_server_runner(calls: list[dict[str, object]]) -> type:
    class FakeServerRunner:
        def __init__(self, context: object, *, quiet: bool = False) -> None:
            calls.append({"context": context, "quiet": quiet})

        def run(
            self,
            *,
            no_services: bool = False,
            no_celery: bool = False,
            extra_args: Sequence[str] = (),
        ) -> None:
            calls.append(
                {
                    "method": "run",
                    "no_services": no_services,
                    "no_celery": no_celery,
                    "extra_args": list(extra_args),
                }
            )

    return FakeServerRunner


def test_run_delegates_to_server_runner(
    mock_context: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`repository run` constructs a ServerRunner and calls run() with defaults."""
    calls: list[dict[str, object]] = []
    monkeypatch.setattr("oarepo_cli.cli.repository.ServerRunner", _fake_server_runner(calls))

    runner = CliRunner()
    result = runner.invoke(app, ["repository", "run"])

    assert result.exit_code == 0, result.output
    assert calls[0] == {"context": mock_context, "quiet": False}
    assert calls[1] == {
        "method": "run",
        "no_services": False,
        "no_celery": False,
        "extra_args": [],
    }


def test_run_passes_no_services_and_no_celery(
    mock_context: Mock,  # noqa: ARG001 -- fixture used for its discover_context patch
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--no-services/--no-celery are forwarded to ServerRunner.run()."""
    calls: list[dict[str, object]] = []
    monkeypatch.setattr("oarepo_cli.cli.repository.ServerRunner", _fake_server_runner(calls))

    runner = CliRunner()
    result = runner.invoke(app, ["repository", "run", "--no-services", "--no-celery"])

    assert result.exit_code == 0, result.output
    assert calls[1]["no_services"] is True
    assert calls[1]["no_celery"] is True


def test_run_passes_quiet_to_server_runner_constructor(
    mock_context: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--quiet is consumed as the quiet= kwarg on the ServerRunner constructor."""
    calls: list[dict[str, object]] = []
    monkeypatch.setattr("oarepo_cli.cli.repository.ServerRunner", _fake_server_runner(calls))

    runner = CliRunner()
    result = runner.invoke(app, ["repository", "run", "--quiet"])

    assert result.exit_code == 0, result.output
    assert calls[0] == {"context": mock_context, "quiet": True}


def test_run_forwards_extra_args(
    mock_context: Mock,  # noqa: ARG001 -- fixture used for its discover_context patch
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unrecognized args/options (e.g. -p 5001) are forwarded to ServerRunner.run() as
    extra_args, mirroring repository_runner.sh's run_server()'s extra_options."""
    calls: list[dict[str, object]] = []
    monkeypatch.setattr("oarepo_cli.cli.repository.ServerRunner", _fake_server_runner(calls))

    runner = CliRunner()
    result = runner.invoke(app, ["repository", "run", "--no-celery", "-p", "5001", "--debugger"])

    assert result.exit_code == 0, result.output
    assert calls[1]["no_celery"] is True
    assert calls[1]["extra_args"] == ["-p", "5001", "--debugger"]


def test_run_reports_context_discovery_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """A context-discovery failure (e.g. no pyproject.toml) is reported cleanly, exit code 1."""

    def raise_config_error() -> None:
        raise ConfigurationError("pyproject.toml not found")

    monkeypatch.setattr("oarepo_cli.cli.repository.discover_context", raise_config_error)

    runner = CliRunner()
    result = runner.invoke(app, ["repository", "run"])

    assert result.exit_code == 1


def test_run_reports_server_runner_error_and_exits_1(
    mock_context: Mock,  # noqa: ARG001 -- fixture used for its discover_context patch
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A ProcessExecutionError raised while starting Docker services is reported cleanly."""

    class RaisingServerRunner:
        def __init__(self, context: object, *, quiet: bool = False) -> None:
            pass

        def run(self, **_kwargs: object) -> None:
            raise ProcessExecutionError(
                message="docker compose up failed",
                command=["docker", "compose", "up"],
                returncode=1,
                stdout=None,
                stderr=None,
            )

    monkeypatch.setattr("oarepo_cli.cli.repository.ServerRunner", RaisingServerRunner)

    runner = CliRunner()
    result = runner.invoke(app, ["repository", "run"])

    assert result.exit_code == 1
    assert "Failed to start server" in result.output


def test_run_help_shows_oarepo_clis_own_help(mock_context: Mock) -> None:  # noqa: ARG001
    """--help shows oarepo-cli's own help (--no-services/--no-celery/--quiet), unlike the
    services subcommands, which forward --help to invenio-cli's own help instead."""
    runner = CliRunner()
    result = runner.invoke(app, ["repository", "run", "--help"])

    assert result.exit_code == 0, result.output
    assert "--no-services" in result.output
    assert "--no-celery" in result.output
    assert "--quiet" in result.output


FAKE_INVENIO_CLI_SCRIPT = """#!/bin/sh
echo "CWD:$(pwd)"
echo "ARGV:$@"
echo "CERT:$INVENIO_SITE_CERT_PATH"
exit 42
"""


def _make_executable(path: Path, content: str) -> None:
    path.write_text(content)
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def test_run_real_exec_replaces_process(tmp_path: Path) -> None:
    """End-to-end: `oarepo-cli repository run` really discovers the project, starts no
    services (--no-services), and execve()s into invenio-cli -- driven via the real CLI
    entry point, in its own isolated subprocess (a real exec would otherwise replace the
    pytest worker), against a tiny fake invenio-cli substituted in for this one process."""
    project_root = tmp_path / "repo"
    project_root.mkdir()
    (project_root / "pyproject.toml").write_text(
        '[project]\nname = "myrepo"\nrequires-python = ">=3.14,<3.15"\n'
        'dependencies = ["oarepo>=14.0.0,<15.0.0"]\n'
    )

    fake_invenio_cli = tmp_path / "fake-invenio-cli"
    _make_executable(fake_invenio_cli, FAKE_INVENIO_CLI_SCRIPT)

    driver = f"""
import sys
import oarepo_cli.services.invenio_cli as invenio_cli_module

invenio_cli_module._invenio_cli_path = lambda: {str(fake_invenio_cli)!r}

from oarepo_cli.cli.main import app

sys.argv = ["oarepo-cli", "repository", "run", "--no-services", "--", "--debugger"]
app()
"""
    result = subprocess.run(
        [sys.executable, "-c", driver],
        cwd=project_root,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 42, result.stderr
    assert f"CWD:{project_root}" in result.stdout
    assert "ARGV:run --debugger" in result.stdout
    assert f"CERT:{project_root / 'docker' / 'development.crt'}" in result.stdout
