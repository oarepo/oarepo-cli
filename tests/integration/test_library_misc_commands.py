# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Integration tests for library miscellaneous commands."""

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


def test_translations_help_displays(runner: CliRunner) -> None:
    """Test that 'library translations --help' displays help text."""
    result = runner.invoke(app, ["library", "translations", "--help"])

    assert result.exit_code == 0
    assert "translations" in result.stdout.lower()


def test_license_headers_help_displays(runner: CliRunner) -> None:
    """Test that 'library license-headers --help' displays help text."""
    result = runner.invoke(app, ["library", "license-headers", "--help"])

    assert result.exit_code == 0
    assert "license" in result.stdout.lower()


def test_jslint_help_displays(runner: CliRunner) -> None:
    """Test that 'library jslint --help' displays help text."""
    result = runner.invoke(app, ["library", "jslint", "--help"])

    assert result.exit_code == 0
    assert "jslint" in result.stdout.lower()


def test_jstest_help_displays(runner: CliRunner) -> None:
    """Test that 'library jstest --help' displays help text."""
    result = runner.invoke(app, ["library", "jstest", "--help"])

    assert result.exit_code == 0
    assert "jstest" in result.stdout.lower()


def test_jslint_skips_without_package_json(
    runner: CliRunner, lint_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that 'library jslint' skips gracefully when no package.json exists."""
    monkeypatch.chdir(lint_project)

    result = runner.invoke(app, ["library", "jslint", "--quiet"], catch_exceptions=False)

    assert result.exit_code == 0


def test_license_headers_adds_headers(
    runner: CliRunner, lint_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that 'library license-headers' adds headers to files missing them."""
    monkeypatch.chdir(lint_project)

    # Create a file without a license header
    module = lint_project / "src" / "cleanlib" / "new_module.py"
    module.write_text(
        '"""A new module without a license header."""\n\n'
        "from __future__ import annotations\n\n\n"
        "def test() -> str:\n"
        '    """Return a test string."""\n'
        '    return "test"\n'
    )

    result = runner.invoke(app, ["library", "license-headers", "--quiet"], catch_exceptions=False)

    assert result.exit_code == 0
    # Check that the file now has a copyright header
    content = module.read_text()
    assert "copyright (c)" in content.lower()
