# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Tests for CLI skeleton and basic command structure."""

from __future__ import annotations

from typer.testing import CliRunner

from oarepo_cli import __version__
from oarepo_cli.cli.main import app

runner = CliRunner()


def test_help_shows_all_commands() -> None:
    """Test that --help displays all top-level commands."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "oarepo-cli" in result.stdout.lower()
    assert "library" in result.stdout.lower()
    assert "repository" in result.stdout.lower()


def test_unknown_command_returns_exit_code_2() -> None:
    """Test that unknown commands return exit code 2."""
    result = runner.invoke(app, ["unknown-command"])
    assert result.exit_code == 2


def test_global_option_verbose() -> None:
    """Test that --verbose flag is parsed correctly."""
    result = runner.invoke(app, ["--verbose", "--help"])
    assert result.exit_code == 0


def test_global_option_config() -> None:
    """Test that --config option is parsed correctly."""
    # Create a temporary config file
    import tempfile
    from pathlib import Path

    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        config_path = Path(f.name)
        f.write("[tool.oarepo-cli]\n")

    try:
        result = runner.invoke(app, ["--config", str(config_path), "--help"])
        assert result.exit_code == 0
    finally:
        config_path.unlink()


def test_global_option_cd(tmp_path) -> None:
    """Test that --cd option changes directory."""
    result = runner.invoke(app, ["--cd", str(tmp_path), "--help"])
    assert result.exit_code == 0


def test_version_displays_package_version() -> None:
    """Test that --version displays the correct version."""
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout
    assert "oarepo-cli" in result.stdout.lower()


def test_version_short_flag() -> None:
    """Test that -v flag also displays version."""
    result = runner.invoke(app, ["-v"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_library_help() -> None:
    """Test that library subcommand help works."""
    result = runner.invoke(app, ["library", "--help"])
    assert result.exit_code == 0
    assert "library" in result.stdout.lower()


def test_repository_help() -> None:
    """Test that repository subcommand help works."""
    result = runner.invoke(app, ["repository", "--help"])
    assert result.exit_code == 0
    assert "repository" in result.stdout.lower()


def test_no_args_shows_help() -> None:
    """Test that running without arguments shows usage information."""
    result = runner.invoke(app, [])
    # When no args provided to Typer app with subcommands, it shows usage and exits with 2
    assert "Usage:" in result.stdout or "Commands" in result.stdout


def test_library_no_args_shows_help() -> None:
    """Test that library without arguments shows usage information."""
    result = runner.invoke(app, ["library"])
    # Typer group with no_args_is_help shows usage when no subcommand provided
    assert "library" in result.stdout.lower() or "Usage" in result.stdout


def test_repository_no_args_shows_help() -> None:
    """Test that repository without arguments shows usage information."""
    result = runner.invoke(app, ["repository"])
    # Typer group with no_args_is_help shows usage when no subcommand provided
    assert "repository" in result.stdout.lower() or "Usage" in result.stdout
