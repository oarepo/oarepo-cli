# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Integration tests for `repository jslint`/`jstest`.

A full real jstest run needs an installed venv plus node/npm/webpack --
too heavy for this suite, and not exercised for `library jstest` either
(see test_library_misc_commands.py, which only covers --help there). The
underlying services.js_tools.run_jslint()/run_jstest() and the shared
cli/js_commands.py wiring are reused verbatim from `library` (Step 4.19),
not duplicated, so this mirrors that file's own coverage level.
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


def test_repository_jslint_help_displays(runner: CliRunner) -> None:
    """Test that 'repository jslint --help' displays help text."""
    result = runner.invoke(app, ["repository", "jslint", "--help"])

    assert result.exit_code == 0
    assert "jslint" in result.stdout.lower()


def test_repository_jstest_help_displays(runner: CliRunner) -> None:
    """Test that 'repository jstest --help' displays help text."""
    result = runner.invoke(app, ["repository", "jstest", "--help"])

    assert result.exit_code == 0
    assert "jstest" in result.stdout.lower()


def test_repository_jslint_skips_without_package_json(
    runner: CliRunner, lint_project_multi_module: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that 'repository jslint' skips gracefully when no package.json exists --
    the common case for a repository, which doesn't commit one at the project root."""
    monkeypatch.chdir(lint_project_multi_module)

    result = runner.invoke(app, ["repository", "jslint", "--quiet"], catch_exceptions=False)

    assert result.exit_code == 0
