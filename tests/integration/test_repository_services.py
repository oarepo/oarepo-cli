# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Tests for `repository services` subcommands (setup/start/stop/destroy).

Each subcommand is a pure passthrough to `invenio-cli services <subcommand>
...` (mirroring repository_runner.sh's services() function), so these
tests mock discover_context() and run_invenio_cli() to verify the
delegation, argument forwarding, and exit-code propagation without needing
a real project or invenio-cli installation -- unlike
test_repository_install.py/test_repository_upgrade.py, there's no
meaningful "real" behavior to exercise here beyond command construction.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Never
from unittest.mock import Mock

import pytest
from typer.testing import CliRunner

from oarepo_cli.cli.main import app
from oarepo_cli.core.errors import ConfigurationError
from oarepo_cli.services import process

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

SUBCOMMANDS = ["setup", "start", "stop", "destroy"]


@pytest.fixture
def mock_context(monkeypatch: pytest.MonkeyPatch) -> Mock:
    """Mock discover_context() so no real project is needed."""
    context = Mock()
    monkeypatch.setattr("oarepo_cli.cli.repository.discover_context", lambda: context)
    return context


def _fake_run_invenio_cli(calls: list[dict[str, object]], return_code: int = 0) -> Callable[..., process.ProcessResult]:
    def fake(
        context: object,
        args: Sequence[str],
        *,
        quiet: bool = False,
        check: bool = True,
        _env: dict[str, str] | None = None,
    ) -> process.ProcessResult:
        calls.append({"context": context, "args": list(args), "quiet": quiet, "check": check})
        return process.ProcessResult(
            return_code=return_code,
            stdout="",
            stderr="",
            command=["invenio-cli", *args],
            cwd=Path(),
            duration_ms=0,
        )

    return fake


@pytest.mark.parametrize("subcommand", SUBCOMMANDS)
def test_services_subcommand_delegates_to_invenio_cli(
    subcommand: str, mock_context: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Services subcommand calls invenio-cli services <subcommand> with check=False.

    So the subcommand's own exit code can be propagated, rather than being
    collapsed by run_invenio_cli's default check=True -> ProcessExecutionError
    -> exit 1.
    """
    calls: list[dict[str, object]] = []
    monkeypatch.setattr("oarepo_cli.cli.repository.invenio_cli.run_invenio_cli", _fake_run_invenio_cli(calls))

    runner = CliRunner()
    result = runner.invoke(app, ["repository", "services", subcommand])

    assert result.exit_code == 0
    assert len(calls) == 1
    assert calls[0]["context"] is mock_context
    assert calls[0]["args"] == ["services", subcommand]
    assert calls[0]["check"] is False


@pytest.mark.parametrize("subcommand", SUBCOMMANDS)
def test_services_subcommand_passes_through_extra_args(
    subcommand: str,
    mock_context: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Extra arguments after the subcommand are forwarded to invenio-cli.

    Forwarded verbatim.
    """
    calls: list[dict[str, object]] = []
    monkeypatch.setattr("oarepo_cli.cli.repository.invenio_cli.run_invenio_cli", _fake_run_invenio_cli(calls))

    runner = CliRunner()
    result = runner.invoke(app, ["repository", "services", subcommand, "-N", "--foo", "bar"])

    assert result.exit_code == 0
    assert calls[0]["args"] == ["services", subcommand, "-N", "--foo", "bar"]


@pytest.mark.parametrize("subcommand", SUBCOMMANDS)
def test_services_subcommand_propagates_exit_code(
    subcommand: str,
    mock_context: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The delegated command's own exit code is propagated exactly.

    Not collapsed to 0/1.
    """
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        "oarepo_cli.cli.repository.invenio_cli.run_invenio_cli",
        _fake_run_invenio_cli(calls, return_code=42),
    )

    runner = CliRunner()
    result = runner.invoke(app, ["repository", "services", subcommand])

    assert result.exit_code == 42


def test_services_setup_quiet_flag_forwarded(
    mock_context: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Quiet flag is consumed as the quiet= kwarg.

    Not forwarded as an extra positional arg.
    """
    calls: list[dict[str, object]] = []
    monkeypatch.setattr("oarepo_cli.cli.repository.invenio_cli.run_invenio_cli", _fake_run_invenio_cli(calls))

    runner = CliRunner()
    result = runner.invoke(app, ["repository", "services", "setup", "--quiet"])

    assert result.exit_code == 0
    assert calls[0]["quiet"] is True
    assert calls[0]["args"] == ["services", "setup"]


def test_services_subcommand_help_reaches_invenio_cli(
    mock_context: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Help is forwarded to invenio-cli rather than intercepted by Typer/Click.

    So the user sees invenio-cli's own help for the delegated subcommand.
    """
    calls: list[dict[str, object]] = []
    monkeypatch.setattr("oarepo_cli.cli.repository.invenio_cli.run_invenio_cli", _fake_run_invenio_cli(calls))

    runner = CliRunner()
    result = runner.invoke(app, ["repository", "services", "setup", "--help"])

    assert result.exit_code == 0
    assert calls[0]["args"] == ["services", "setup", "--help"]


def test_services_subcommand_reports_context_discovery_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A context-discovery failure (e.g. no pyproject.toml) is reported cleanly, exit code 1."""

    def raise_config_error() -> Never:
        raise ConfigurationError("pyproject.toml not found")

    monkeypatch.setattr("oarepo_cli.cli.repository.discover_context", raise_config_error)

    runner = CliRunner()
    result = runner.invoke(app, ["repository", "services", "setup"])

    assert result.exit_code == 1
