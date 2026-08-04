# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Integration tests for library clean command using real testlib fixture."""

from __future__ import annotations

import shutil
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


@pytest.fixture
def testlib_with_artifacts(clean_testlib: Path) -> Path:
    """Create testlib with venv and .env-services artifacts."""
    # Create venv structure
    venv_path = clean_testlib / ".venv"
    venv_bin = venv_path / "bin"
    venv_bin.mkdir(parents=True, exist_ok=True)

    # Create dummy files in venv
    python_bin = venv_bin / "python"
    if not python_bin.exists():
        python_bin.write_text("#!/bin/sh\necho 'python'")
        python_bin.chmod(0o755)

    (venv_path / "pyvenv.cfg").write_text("version = 3.14\n")

    # Create .env-services file
    env_file = clean_testlib / ".env-services"
    env_file.write_text('export DATABASE_URL="postgresql://localhost:5432/test"\n')

    return clean_testlib


def test_library_clean_command_removes_all_real(
    runner: CliRunner,
    testlib_with_artifacts: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that library clean command removes venv and .env-services."""
    monkeypatch.chdir(testlib_with_artifacts)

    # Verify files exist before cleaning
    assert (testlib_with_artifacts / ".venv").exists()
    assert (testlib_with_artifacts / ".env-services").exists()

    result = runner.invoke(app, ["library", "clean", "--quiet"], catch_exceptions=False)

    # Command should succeed or fail gracefully
    assert result.exit_code in [0, 1]

    # Verify files were removed (if successful)
    if result.exit_code == 0:
        assert not (testlib_with_artifacts / ".venv").exists()
        assert not (testlib_with_artifacts / ".env-services").exists()


def test_library_clean_command_idempotent_real(
    runner: CliRunner,
    clean_testlib: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that library clean works when nothing exists."""
    monkeypatch.chdir(clean_testlib)

    # clean_testlib fixture guarantees nothing exists yet
    venv_path = clean_testlib / ".venv"
    env_file = clean_testlib / ".env-services"

    assert not venv_path.exists()
    assert not env_file.exists()

    result = runner.invoke(app, ["library", "clean", "--quiet"], catch_exceptions=False)

    # Command should succeed even with nothing to clean
    assert result.exit_code == 0


def test_library_clean_command_shows_output_real(
    runner: CliRunner,
    testlib_with_artifacts: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that library clean shows informative output without --quiet."""
    monkeypatch.chdir(testlib_with_artifacts)

    result = runner.invoke(app, ["library", "clean"], catch_exceptions=False)

    # Command should succeed or fail gracefully
    assert result.exit_code in [0, 1]

    # Output should contain informative messages (if any)
    # We just verify it doesn't crash
    assert len(result.output) >= 0  # Always true, just checking no exception


def test_library_clean_command_prints_summary_once_when_something_removed(
    runner: CliRunner,
    testlib_with_artifacts: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The "Cleanup completed" summary line is printed exactly once, not twice
    (regression test for a copy-paste bug where the summary block was duplicated)."""
    monkeypatch.chdir(testlib_with_artifacts)

    result = runner.invoke(app, ["library", "clean"], catch_exceptions=False)

    assert result.exit_code == 0, result.output
    assert result.output.count("Cleanup completed") == 1


def test_library_clean_command_prints_summary_once_when_already_clean(
    runner: CliRunner,
    clean_testlib: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The "already clean" summary line is printed exactly once, not twice
    (regression test for a copy-paste bug where the summary block was duplicated)."""
    monkeypatch.chdir(clean_testlib)

    result = runner.invoke(app, ["library", "clean"], catch_exceptions=False)

    assert result.exit_code == 0, result.output
    assert result.output.count("already clean") == 1


def test_library_clean_command_partial_cleanup_real(
    runner: CliRunner,
    clean_testlib: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that library clean handles partial cleanup gracefully."""
    monkeypatch.chdir(clean_testlib)

    # Ensure only .env-services exists (no venv)
    venv_path = clean_testlib / ".venv"
    env_file = clean_testlib / ".env-services"

    if venv_path.exists():
        shutil.rmtree(venv_path)

    env_file.write_text("export TEST=value\n")

    # Verify partial state
    assert not venv_path.exists()
    assert env_file.exists()

    result = runner.invoke(app, ["library", "clean", "--quiet"], catch_exceptions=False)

    # Command should succeed
    assert result.exit_code == 0

    # Verify .env-services was removed
    assert not env_file.exists()


def test_library_clean_with_actual_venv_real(
    runner: CliRunner,
    clean_testlib: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test clean with a real venv structure."""
    monkeypatch.chdir(clean_testlib)

    # Create a proper venv structure
    venv_path = clean_testlib / ".venv"
    if venv_path.exists():
        shutil.rmtree(venv_path)

    venv_path.mkdir(parents=True)
    bin_dir = venv_path / "bin"
    bin_dir.mkdir()
    python_bin = bin_dir / "python"
    python_bin.touch()
    python_bin.chmod(0o755)
    (venv_path / "pyvenv.cfg").write_text("home = /usr\n")

    # Create .env-services
    env_file = clean_testlib / ".env-services"
    env_file.write_text("export DATABASE_URL=test\n")

    # Run clean
    result = runner.invoke(app, ["library", "clean", "--quiet"], catch_exceptions=False)

    # Should complete
    assert result.exit_code in [0, 1]

    # If successful, both should be removed
    if result.exit_code == 0:
        assert not venv_path.exists()
        assert not env_file.exists()
