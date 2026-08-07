# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Integration tests for the read-only library check command.

Since 'library check' is functionally equivalent to 'library lint --no-fix',
we only verify that the alias works and enforces read-only behavior.
Full lint functionality is tested in test_library_lint_format.py.
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


def test_check_never_modifies_files(runner: CliRunner, lint_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that 'library check' reports violations without modifying any file.

    This is the critical behavior difference from 'library lint' - check is
    read-only, while lint auto-fixes by default.
    """
    monkeypatch.chdir(lint_project)

    module = lint_project / "src" / "cleanlib" / "__init__.py"
    dirty = module.read_text() + "\nimport os\n"
    module.write_text(dirty)

    result = runner.invoke(app, ["library", "check", "--quiet"], catch_exceptions=False)

    assert result.exit_code != 0
    # Critical: file should not be modified (read-only check)
    assert module.read_text() == dirty


def test_check_matches_lint_no_fix_behavior(
    runner: CliRunner, lint_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that 'library check' is functionally equivalent to 'library lint --no-fix'.

    This verifies the alias behaves as documented rather than just testing it
    in isolation.
    """
    monkeypatch.chdir(lint_project)

    module = lint_project / "src" / "cleanlib" / "__init__.py"
    module.write_text(module.read_text() + "\nimport os\n")

    check_result = runner.invoke(app, ["library", "check", "--quiet"], catch_exceptions=False)
    lint_no_fix_result = runner.invoke(app, ["library", "lint", "--no-fix", "--quiet"], catch_exceptions=False)

    assert check_result.exit_code == lint_no_fix_result.exit_code
    assert check_result.exit_code != 0
