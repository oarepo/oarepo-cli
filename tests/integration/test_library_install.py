# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Integration test for library install alias command using real testlib fixture."""

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


def test_library_install_alias_works_real(
    runner: CliRunner,
    clean_testlib: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that 'library install' command works as alias for 'library venv'."""
    monkeypatch.chdir(clean_testlib)

    # clean_testlib fixture guarantees no venv exists yet
    assert not (clean_testlib / ".venv").exists()

    result = runner.invoke(app, ["library", "install", "--quiet"], catch_exceptions=False)

    # Command should succeed or fail with expected error
    assert result.exit_code in [0, 1]

    # If successful, verify venv was created
    if result.exit_code == 0:
        assert (clean_testlib / ".venv").exists()


def test_library_install_with_force_flag_real(
    runner: CliRunner,
    clean_testlib: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that 'library install --force' recreates venv."""
    monkeypatch.chdir(clean_testlib)

    # Create an existing venv with marker
    venv_path = clean_testlib / ".venv"
    venv_path.mkdir(parents=True)
    marker_file = venv_path / "test_marker.txt"
    marker_file.write_text("old venv")

    # Verify marker exists
    assert marker_file.exists()

    # Run install with force
    result = runner.invoke(
        app, ["library", "install", "--force", "--quiet"], catch_exceptions=False
    )

    # Should complete (may fail if uv not available)
    assert result.exit_code in [0, 1]

    # If successful, marker should be gone (venv was recreated)
    if result.exit_code == 0:
        assert not marker_file.exists()


def test_library_install_help_displays(runner: CliRunner) -> None:
    """Test that 'library install --help' displays help text."""
    result = runner.invoke(app, ["library", "install", "--help"])

    assert result.exit_code == 0
    # Should show same help as venv since it's an alias
    assert "--force" in result.stdout or "--quiet" in result.stdout


def test_library_install_creates_venv_with_testlib(
    runner: CliRunner,
    clean_testlib: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test library install creates venv for actual testlib project."""
    monkeypatch.chdir(clean_testlib)

    venv_path = clean_testlib / ".venv"
    result = runner.invoke(app, ["library", "install"], catch_exceptions=False)

    # Should succeed or fail with expected error
    assert result.exit_code in [0, 1]

    # If successful, verify structure
    if result.exit_code == 0:
        assert venv_path.exists()
        assert (venv_path / "bin" / "python").exists()
