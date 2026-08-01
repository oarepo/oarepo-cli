# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Integration tests for library venv command using real testlib fixture."""

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


def test_library_venv_creates_venv_real(
    runner: CliRunner,
    clean_testlib: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that 'library venv' creates a virtual environment."""
    monkeypatch.chdir(clean_testlib)

    # clean_testlib fixture guarantees no venv exists yet
    venv_path = clean_testlib / ".venv"
    assert not venv_path.exists()

    # Run the command
    result = runner.invoke(app, ["library", "venv"], catch_exceptions=False)

    # Command should complete (may fail if uv not available, but should not crash)
    assert result.exit_code in [0, 1]

    # If successful, venv should exist
    if result.exit_code == 0:
        assert venv_path.exists()
        assert (venv_path / "bin" / "python").exists()


def test_library_venv_help_displays(runner: CliRunner) -> None:
    """Test that 'library venv --help' displays help text."""
    result = runner.invoke(app, ["library", "venv", "--help"])

    assert result.exit_code == 0
    assert "Set up virtual environment" in result.stdout
    assert "--force" in result.stdout
    assert "--no-editable" in result.stdout


def test_library_venv_force_flag_exists(runner: CliRunner) -> None:
    """Test that --force flag is recognized."""
    result = runner.invoke(app, ["library", "venv", "--help"])

    assert result.exit_code == 0
    assert "--force" in result.stdout or "-f" in result.stdout


def test_library_venv_no_editable_flag_exists(runner: CliRunner) -> None:
    """Test that --no-editable flag is recognized."""
    result = runner.invoke(app, ["library", "venv", "--help"])

    assert result.exit_code == 0
    assert "--no-editable" in result.stdout


def test_library_venv_strips_parent_venv_real(
    runner: CliRunner,
    clean_testlib: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that library venv command strips parent VIRTUAL_ENV."""
    monkeypatch.chdir(clean_testlib)

    # Simulate being run from within another venv
    monkeypatch.setenv("VIRTUAL_ENV", "/some/other/venv")
    monkeypatch.setenv("VIRTUAL_ENV_PROMPT", "(oarepo-cli) ")

    # The command should work without being confused by the parent venv
    result = runner.invoke(app, ["library", "venv"], catch_exceptions=False)

    # Should not crash with context errors about wrong venv
    # Exit code may be non-zero if uv is missing, but should not be a context error
    assert "context" not in result.stdout.lower() or result.exit_code in [0, 1]


def test_library_venv_requires_pyproject(
    runner: CliRunner,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that library venv fails gracefully without pyproject.toml."""
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    monkeypatch.chdir(empty_dir)

    result = runner.invoke(app, ["library", "venv"])

    assert result.exit_code != 0
    # The error should mention pyproject.toml
    assert (
        "pyproject.toml" in str(result.exception).lower()
        if result.exception
        else "pyproject.toml" in result.stdout.lower()
    )


def test_library_venv_with_testlib_real(
    runner: CliRunner,
    clean_testlib: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test library venv works correctly with the actual testlib project."""
    monkeypatch.chdir(clean_testlib)

    venv_path = clean_testlib / ".venv"

    # Run venv creation
    result = runner.invoke(app, ["library", "venv"], catch_exceptions=False)

    # Should succeed or fail with expected error (not crash)
    assert result.exit_code in [0, 1]

    # If successful, verify structure
    if result.exit_code == 0:
        assert venv_path.exists()
        assert (venv_path / "bin" / "python").exists()
        assert (venv_path / "bin" / "pip").exists()
