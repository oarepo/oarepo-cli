# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Integration tests for `repository test`, using a real venv/pytest (installed on
demand, since -- unlike a library -- a fresh repository has no "tests" extras
convention of its own). Always run with --no-services: this doesn't need Docker at
all, so there's no reason to touch it (or invenio-cli, which isn't installed in
these minimal fixtures anyway).
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


def test_repository_test_help_displays(runner: CliRunner) -> None:
    """Test that 'repository test --help' displays help text."""
    result = runner.invoke(app, ["repository", "test", "--help"])

    assert result.exit_code == 0
    assert "test" in result.stdout.lower()
    assert "pytest" in result.stdout.lower()


def test_repository_test_runs_real_pytest_and_installs_it_on_demand(
    runner: CliRunner, lint_project_multi_module: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`repository test` installs pytest into the venv (missing by default in a fresh
    repository fixture) and then actually runs it, real end to end."""
    monkeypatch.chdir(lint_project_multi_module)
    tests_dir = lint_project_multi_module / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_sample.py").write_text("def test_pass():\n    assert True\n")

    result = runner.invoke(
        app, ["repository", "test", "--no-services", "--quiet"], catch_exceptions=False
    )

    assert result.exit_code == 0, result.output


def test_repository_test_exit_code_on_failure(
    runner: CliRunner, lint_project_multi_module: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failing test makes `repository test` exit with pytest's own non-zero code."""
    monkeypatch.chdir(lint_project_multi_module)
    tests_dir = lint_project_multi_module / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_sample.py").write_text(
        "def test_fail():\n    assert False, 'this test fails'\n"
    )

    result = runner.invoke(
        app, ["repository", "test", "--no-services", "--quiet"], catch_exceptions=False
    )

    assert result.exit_code != 0
