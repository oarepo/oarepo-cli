# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Integration tests for `repository lint`/`format`, using real ruff/ty against a
multi-module uv_build project (unlike test_library_lint_format.py's single-src-dir
project) -- the CLI wiring and LintRunner internals themselves are already covered
there and in tests/unit/test_lint_service.py, since Step 4.18 reuses both verbatim
(cli/lint_commands.py, services/lint.py) rather than duplicating them for repository.
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


def test_repository_lint_help_displays(runner: CliRunner) -> None:
    """Test that 'repository lint --help' displays help text."""
    result = runner.invoke(app, ["repository", "lint", "--help"])

    assert result.exit_code == 0
    assert "lint" in result.stdout.lower()


def test_repository_format_help_displays(runner: CliRunner) -> None:
    """Test that 'repository format --help' displays help text."""
    result = runner.invoke(app, ["repository", "format", "--help"])

    assert result.exit_code == 0
    assert "format" in result.stdout.lower()


def test_repository_lint_passes_on_clean_multi_module_project(
    runner: CliRunner, lint_project_multi_module: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`repository lint` exits 0 on a clean, multi-module (uv_build) project -- exercising
    the real ty/ruff invocation across every module directory, not just the first."""
    monkeypatch.chdir(lint_project_multi_module)

    result = runner.invoke(app, ["repository", "lint", "--quiet"], catch_exceptions=False)

    assert result.exit_code == 0, result.output
    assert (lint_project_multi_module / ".ruff.toml").exists()
    assert (lint_project_multi_module / "ty.toml").exists()


def test_repository_lint_fails_on_type_error_in_second_module(
    runner: CliRunner, lint_project_multi_module: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`repository lint` catches a type error in the *second* module directory --
    regression test for Step 4.15's ty-check fix, which used to only pass
    code_directories[0] (the first module) to ty, silently skipping the rest."""
    monkeypatch.chdir(lint_project_multi_module)

    second_module = lint_project_multi_module / "i18n" / "__init__.py"
    second_module.write_text(
        "# Copyright (c) 2026 Example Org.\n"
        "#\n"
        "# This file is a part of cleanrepo.\n"
        '"""Sample module with a real type error."""\n'
        "\n"
        "from __future__ import annotations\n"
        "\n"
        "\n"
        "def greet() -> str:\n"
        '    """Return a greeting message."""\n'
        "    return 42\n"
    )

    result = runner.invoke(app, ["repository", "lint", "--quiet"], catch_exceptions=False)

    assert result.exit_code != 0


def test_repository_format_fixes_issues(
    runner: CliRunner, lint_project_multi_module: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`repository format` (default --fix) rewrites a badly-formatted file."""
    monkeypatch.chdir(lint_project_multi_module)

    module = lint_project_multi_module / "common" / "__init__.py"
    module.write_text(
        "# Copyright (c) 2026 Example Org.\n"
        "#\n"
        "# This file is a part of cleanrepo.\n"
        '"""Sample module."""\n'
        "\n"
        "from __future__ import annotations\n"
        "\n"
        "\n"
        "def greet(  )->str:\n"
        '    """Return a greeting message."""\n'
        "    return   'hello'\n"
    )

    result = runner.invoke(app, ["repository", "format", "--quiet"], catch_exceptions=False)

    assert result.exit_code == 0, result.output
    assert "def greet() -> str:" in module.read_text()


def test_repository_lint_requires_pyproject(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`repository lint` fails cleanly (exit 1) when no pyproject.toml can be found."""
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["repository", "lint", "--quiet"])

    assert result.exit_code == 1
