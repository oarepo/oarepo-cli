# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Tests for repository shell-related commands.

This file tests repository commands that exec into shells or delegate to Invenio tooling:
- `repository cli` - execs invenio-cli with arbitrary args
- `repository invenio` - execs the bare invenio binary with arbitrary args
- `repository shell` - starts services (by default) then execs a shell

Delegation, argument wiring, and error/exit-code handling are covered here
by mocking `discover_context()` and the specific service function/module
each subcommand delegates to.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from typer.testing import CliRunner

from oarepo_cli.cli.main import app
from oarepo_cli.core.errors import ConfigurationError, ProcessExecutionError


@pytest.fixture
def mock_context(monkeypatch: pytest.MonkeyPatch) -> Mock:
    """Mock discover_context() so no real project is needed."""
    context = Mock()
    monkeypatch.setattr("oarepo_cli.cli.repository.discover_context", lambda: context)
    return context


# --- repository cli ---------------------------------------------------


def test_cli_delegates_to_exec_invenio_cli(
    mock_context: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`repository cli <args>` execs invenio-cli with the given args verbatim."""
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        "oarepo_cli.cli.repository.invenio_cli.exec_invenio_cli",
        lambda context, args, **_kwargs: calls.append({"context": context, "args": list(args)}),
    )

    runner = CliRunner()
    result = runner.invoke(app, ["repository", "cli", "services", "status"])

    assert result.exit_code == 0, result.output
    assert calls == [{"context": mock_context, "args": ["services", "status"]}]


def test_cli_help_forwarded_to_invenio_cli(
    mock_context: Mock,  # noqa: ARG001 -- fixture used for its discover_context patch
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--help is forwarded to invenio-cli rather than intercepted by Typer/Click."""
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        "oarepo_cli.cli.repository.invenio_cli.exec_invenio_cli",
        lambda _context, args, **_kwargs: calls.append({"args": list(args)}),
    )

    runner = CliRunner()
    result = runner.invoke(app, ["repository", "cli", "--help"])

    assert result.exit_code == 0, result.output
    assert calls == [{"args": ["--help"]}]


def test_cli_reports_context_discovery_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """A context-discovery failure is reported cleanly, exit code 1."""
    monkeypatch.setattr(
        "oarepo_cli.cli.repository.discover_context",
        Mock(side_effect=ConfigurationError("pyproject.toml not found")),
    )

    runner = CliRunner()
    result = runner.invoke(app, ["repository", "cli", "services", "status"])

    assert result.exit_code == 1


# --- repository invenio -------------------------------------------------


def test_invenio_delegates_to_exec_invenio(
    mock_context: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`repository invenio <args>` execs the bare invenio binary with the given args
    verbatim (not invenio-cli -- see `repository cli` for that)."""
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        "oarepo_cli.cli.repository.repository.exec_invenio",
        lambda context, args, **_kwargs: calls.append({"context": context, "args": list(args)}),
    )

    runner = CliRunner()
    result = runner.invoke(app, ["repository", "invenio", "db", "upgrade"])

    assert result.exit_code == 0, result.output
    assert calls == [{"context": mock_context, "args": ["db", "upgrade"]}]


def test_invenio_help_forwarded_to_invenio(
    mock_context: Mock,  # noqa: ARG001 -- fixture used for its discover_context patch
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--help is forwarded to invenio rather than intercepted by Typer/Click."""
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        "oarepo_cli.cli.repository.repository.exec_invenio",
        lambda _context, args, **_kwargs: calls.append({"args": list(args)}),
    )

    runner = CliRunner()
    result = runner.invoke(app, ["repository", "invenio", "--help"])

    assert result.exit_code == 0, result.output
    assert calls == [{"args": ["--help"]}]


def test_invenio_reports_context_discovery_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """A context-discovery failure is reported cleanly, exit code 1."""
    monkeypatch.setattr(
        "oarepo_cli.cli.repository.discover_context",
        Mock(side_effect=ConfigurationError("pyproject.toml not found")),
    )

    runner = CliRunner()
    result = runner.invoke(app, ["repository", "invenio", "db", "upgrade"])

    assert result.exit_code == 1


# --- repository shell ----------------------------------------------------


def test_shell_starts_services_by_default_then_execs_shell(
    mock_context: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`repository shell` starts Docker services via invenio-cli (like `repository run`,
    not ServicesLifecycleManager) before exec'ing the shell, by default."""
    services_calls: list[dict[str, object]] = []
    shell_calls: list[object] = []
    monkeypatch.setattr(
        "oarepo_cli.cli.repository.invenio_cli.run_invenio_cli",
        lambda context, args, **kwargs: services_calls.append(
            {"context": context, "args": list(args), **kwargs}
        ),
    )
    monkeypatch.setattr("oarepo_cli.cli.repository.repository.exec_shell", shell_calls.append)

    runner = CliRunner()
    result = runner.invoke(app, ["repository", "shell"])

    assert result.exit_code == 0, result.output
    assert services_calls == [
        {"context": mock_context, "args": ["services", "start"], "quiet": False}
    ]
    assert shell_calls == [mock_context]


def test_shell_no_services_skips_starting_services(
    mock_context: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--no-services skips starting Docker services but still execs the shell."""
    services_calls: list[object] = []
    shell_calls: list[object] = []
    monkeypatch.setattr(
        "oarepo_cli.cli.repository.invenio_cli.run_invenio_cli",
        lambda *args, **kwargs: services_calls.append((args, kwargs)),
    )
    monkeypatch.setattr("oarepo_cli.cli.repository.repository.exec_shell", shell_calls.append)

    runner = CliRunner()
    result = runner.invoke(app, ["repository", "shell", "--no-services"])

    assert result.exit_code == 0, result.output
    assert services_calls == []
    assert shell_calls == [mock_context]


def test_shell_quiet_forwarded_to_services_start(
    mock_context: Mock,  # noqa: ARG001 -- fixture used for its discover_context patch
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--quiet is forwarded to the services-start invenio-cli call."""
    services_calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        "oarepo_cli.cli.repository.invenio_cli.run_invenio_cli",
        lambda context, args, **kwargs: services_calls.append(
            {"context": context, "args": list(args), **kwargs}
        ),
    )
    monkeypatch.setattr("oarepo_cli.cli.repository.repository.exec_shell", lambda _context: None)

    runner = CliRunner()
    result = runner.invoke(app, ["repository", "shell", "--quiet"])

    assert result.exit_code == 0, result.output
    assert services_calls[0]["quiet"] is True


def test_shell_reports_context_discovery_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """A context-discovery failure is reported cleanly, exit code 1."""
    monkeypatch.setattr(
        "oarepo_cli.cli.repository.discover_context",
        Mock(side_effect=ConfigurationError("pyproject.toml not found")),
    )

    runner = CliRunner()
    result = runner.invoke(app, ["repository", "shell"])

    assert result.exit_code == 1


def test_shell_reports_services_start_failure_and_never_execs_shell(
    mock_context: Mock,  # noqa: ARG001 -- fixture used for its discover_context patch
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A ProcessExecutionError starting services is reported cleanly, exit code 1, and
    the shell is never exec'd."""
    shell_calls: list[object] = []
    monkeypatch.setattr(
        "oarepo_cli.cli.repository.invenio_cli.run_invenio_cli",
        Mock(
            side_effect=ProcessExecutionError(
                message="invenio-cli services start failed",
                command=["invenio-cli", "services", "start"],
                returncode=1,
                stdout=None,
                stderr=None,
            )
        ),
    )
    monkeypatch.setattr("oarepo_cli.cli.repository.repository.exec_shell", shell_calls.append)

    runner = CliRunner()
    result = runner.invoke(app, ["repository", "shell"])

    assert result.exit_code == 1
    assert shell_calls == []
