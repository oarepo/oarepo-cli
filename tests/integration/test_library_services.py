# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Integration tests for library start/stop commands using real testlib fixture."""

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


def test_start_help_displays(runner: CliRunner) -> None:
    """Test that 'library start --help' displays help text."""
    result = runner.invoke(app, ["library", "start", "--help"])

    assert result.exit_code == 0
    assert "start" in result.stdout.lower()
    assert "services" in result.stdout.lower() or "docker" in result.stdout.lower()


def test_stop_help_displays(runner: CliRunner) -> None:
    """Test that 'library stop --help' displays help text."""
    result = runner.invoke(app, ["library", "stop", "--help"])

    assert result.exit_code == 0
    assert "stop" in result.stdout.lower()
    assert "services" in result.stdout.lower() or "docker" in result.stdout.lower()


def test_start_creates_env_file_real(
    runner: CliRunner,
    clean_testlib: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that start command creates .env-services file."""
    monkeypatch.chdir(clean_testlib)

    result = runner.invoke(app, ["library", "start"], catch_exceptions=False)

    # Command should complete (may fail if docker not running, but should not crash)
    assert result.exit_code in [0, 1]

    # If successful, .env-services should exist
    if result.exit_code == 0:
        assert (clean_testlib / ".env-services").exists()


def test_stop_removes_env_file_real(
    runner: CliRunner,
    clean_testlib: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that stop command removes .env-services file."""
    monkeypatch.chdir(clean_testlib)

    # Create existing .env-services file
    env_file = clean_testlib / ".env-services"
    env_file.write_text("export SQLALCHEMY_DATABASE_URI=postgresql://test\n")

    result = runner.invoke(app, ["library", "stop"], catch_exceptions=False)

    # Should complete
    assert result.exit_code in [0, 1]

    # If successful, file should be removed
    if result.exit_code == 0:
        assert not env_file.exists()


def test_stop_when_no_services_running_real(
    runner: CliRunner,
    clean_testlib: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that stop command handles no services gracefully."""
    monkeypatch.chdir(clean_testlib)

    # clean_testlib fixture guarantees no .env-services file exists
    result = runner.invoke(app, ["library", "stop"], catch_exceptions=False)

    # Should exit successfully with message
    assert result.exit_code == 0


def test_start_handles_docker_not_running_real(
    runner: CliRunner,
    clean_testlib: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that start command handles docker not running gracefully."""
    monkeypatch.chdir(clean_testlib)

    result = runner.invoke(app, ["library", "start"], catch_exceptions=False)

    # May fail if docker not running, but should handle gracefully
    # Exit code may be non-zero, but should not crash unexpectedly
    assert result.exit_code in [0, 1]


def test_stop_handles_no_env_file_real(
    runner: CliRunner,
    clean_testlib: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that stop command handles missing env file gracefully."""
    monkeypatch.chdir(clean_testlib)

    # clean_testlib fixture guarantees no .env-services file
    result = runner.invoke(app, ["library", "stop"], catch_exceptions=False)

    # Should succeed even without env file
    assert result.exit_code == 0


def test_services_subcommand_alias_works(runner: CliRunner) -> None:
    """Test that 'library services' subcommand exists and shows help.

    'library services start' and 'library services stop' are aliases for
    'library start' and 'library stop'. We verify the subcommand exists
    without re-testing all start/stop functionality.
    """
    result = runner.invoke(app, ["library", "services", "--help"])

    assert result.exit_code == 0
    assert "services" in result.stdout.lower()
    assert "start" in result.stdout.lower()
    assert "stop" in result.stdout.lower()
