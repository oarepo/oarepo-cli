# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Integration tests for the read-only `repository check` command, against a
multi-module uv_build project -- see test_repository_lint_format.py's module
docstring for why this doesn't re-cover ground already tested for `library check`.
"""

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


def test_repository_check_help_displays(runner: CliRunner) -> None:
    """Test that 'repository check --help' displays help text."""
    result = runner.invoke(app, ["repository", "check", "--help"])

    assert result.exit_code == 0
    assert "check" in result.stdout.lower()


def test_repository_check_passes_on_clean_multi_module_project(
    runner: CliRunner, lint_project_multi_module: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that 'repository check' exits 0 on a clean, multi-module project."""
    monkeypatch.chdir(lint_project_multi_module)

    result = runner.invoke(app, ["repository", "check", "--quiet"], catch_exceptions=False)

    assert result.exit_code == 0


def test_repository_check_never_modifies_files(
    runner: CliRunner, lint_project_multi_module: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that 'repository check' reports a violation without modifying any file."""
    monkeypatch.chdir(lint_project_multi_module)

    module = lint_project_multi_module / "i18n" / "__init__.py"
    dirty = module.read_text() + "\nimport os\n"
    module.write_text(dirty)

    result = runner.invoke(app, ["repository", "check", "--quiet"], catch_exceptions=False)

    assert result.exit_code != 0
    assert module.read_text() == dirty


def test_repository_check_matches_lint_no_fix_exit_code(
    runner: CliRunner, lint_project_multi_module: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that 'repository check' and 'repository lint --no-fix' agree on pass/fail."""
    monkeypatch.chdir(lint_project_multi_module)

    module = lint_project_multi_module / "common" / "__init__.py"
    module.write_text(module.read_text() + "\nimport os\n")

    check_result = runner.invoke(app, ["repository", "check", "--quiet"], catch_exceptions=False)
    lint_no_fix_result = runner.invoke(app, ["repository", "lint", "--no-fix", "--quiet"], catch_exceptions=False)

    assert check_result.exit_code == lint_no_fix_result.exit_code
    assert check_result.exit_code != 0
