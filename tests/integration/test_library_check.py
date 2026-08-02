# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Integration tests for the read-only library check command."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from oarepo_cli.cli.main import app

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def runner() -> CliRunner:
    """Provide a Typer CLI runner."""
    return CliRunner()


def test_check_help_displays(runner: CliRunner) -> None:
    """Test that 'library check --help' displays help text."""
    result = runner.invoke(app, ["library", "check", "--help"])

    assert result.exit_code == 0
    assert "check" in result.stdout.lower()


def test_check_passes_on_clean_code(
    runner: CliRunner, lint_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that 'library check' exits 0 on a clean project."""
    monkeypatch.chdir(lint_project)

    result = runner.invoke(app, ["library", "check", "--quiet"], catch_exceptions=False)

    assert result.exit_code == 0


def test_check_never_modifies_files(
    runner: CliRunner, lint_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that 'library check' reports a violation without modifying any file."""
    monkeypatch.chdir(lint_project)

    module = lint_project / "src" / "cleanlib" / "__init__.py"
    dirty = module.read_text() + "\nimport os\n"
    module.write_text(dirty)

    result = runner.invoke(app, ["library", "check", "--quiet"], catch_exceptions=False)

    assert result.exit_code != 0
    assert module.read_text() == dirty


def test_check_matches_lint_no_fix_exit_code(
    runner: CliRunner, lint_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that 'library check' and 'library lint --no-fix' agree on pass/fail.

    `library check` is documented as functionally equivalent to `library
    lint --no-fix` - verify that directly rather than just testing each in
    isolation.
    """
    monkeypatch.chdir(lint_project)

    module = lint_project / "src" / "cleanlib" / "__init__.py"
    module.write_text(module.read_text() + "\nimport os\n")

    check_result = runner.invoke(app, ["library", "check", "--quiet"], catch_exceptions=False)
    lint_no_fix_result = runner.invoke(
        app, ["library", "lint", "--no-fix", "--quiet"], catch_exceptions=False
    )

    assert check_result.exit_code == lint_no_fix_result.exit_code
    assert check_result.exit_code != 0
