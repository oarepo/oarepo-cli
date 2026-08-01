# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Integration tests for library clean command."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from oarepo_cli.cli.main import app

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_subprocess import FakeProcess


@pytest.fixture
def test_project(tmp_path: Path) -> Path:
    """Create a minimal test project with venv and .env-services."""
    # Create pyproject.toml
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[project]
name = "test-package"
version = "1.0.0"
requires-python = ">=3.14,<3.15"

[tool.oarepo-cli]
[tool.oarepo-cli.oarepo]
version = 14
"""
    )

    # Create venv structure
    venv_path = tmp_path / ".venv"
    venv_bin = venv_path / "bin"
    venv_bin.mkdir(parents=True)

    # Create dummy files in venv
    (venv_bin / "python").write_text("#!/bin/sh\necho 'python'")
    (venv_bin / "python").chmod(0o755)
    (venv_path / "pyvenv.cfg").write_text("version = 3.14\n")

    # Create .env-services file
    env_file = tmp_path / ".env-services"
    env_file.write_text('export DATABASE_URL="postgresql://localhost:5432/test"\n')

    return tmp_path


def test_library_clean_command_removes_all(
    test_project: Path,
    fake_process: FakeProcess,
    monkeypatch,
) -> None:
    """Test that library clean command removes venv and .env-services."""
    # Change to test project directory
    monkeypatch.chdir(test_project)

    # Verify files exist before cleaning
    assert (test_project / ".venv").exists()
    assert (test_project / ".env-services").exists()

    # Register docker-services-cli down command (for stopping services)
    fake_process.register(
        [
            "uvx",
            "--with",
            "setuptools",
            "docker-services-cli",
            "down",
            "--env",
            "--quiet",
        ],
        stdout="",
    )

    runner = CliRunner()
    result = runner.invoke(app, ["library", "clean", "--quiet"])

    # Command should succeed
    assert result.exit_code == 0

    # Verify files were removed
    assert not (test_project / ".venv").exists()
    assert not (test_project / ".env-services").exists()


def test_library_clean_command_idempotent(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Test that library clean works when nothing exists."""
    # Create minimal project without venv or .env-services
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[project]
name = "test-package"
version = "1.0.0"
requires-python = ">=3.14,<3.15"

[tool.oarepo-cli]
[tool.oarepo-cli.oarepo]
version = 14
"""
    )

    monkeypatch.chdir(tmp_path)

    # Verify nothing exists
    assert not (tmp_path / ".venv").exists()
    assert not (tmp_path / ".env-services").exists()

    runner = CliRunner()
    result = runner.invoke(app, ["library", "clean", "--quiet"])

    # Command should succeed even with nothing to clean
    assert result.exit_code == 0
    # With --quiet, output will be suppressed, so we just check exit code


def test_library_clean_command_shows_output(
    test_project: Path,
    fake_process: FakeProcess,
    monkeypatch,
) -> None:
    """Test that library clean shows informative output without --quiet."""
    monkeypatch.chdir(test_project)

    # Register docker-services-cli down command
    fake_process.register(
        [
            "uvx",
            "--with",
            "setuptools",
            "docker-services-cli",
            "down",
            "--env",
        ],
        stdout="",
    )

    runner = CliRunner()
    result = runner.invoke(app, ["library", "clean"])

    # Command should succeed
    assert result.exit_code == 0

    # Output should contain informative messages
    assert "Cleaning environment" in result.output or "🧹" in result.output
    assert "completed" in result.output or "✓" in result.output


def test_library_clean_command_partial_cleanup(
    test_project: Path,
    monkeypatch,
) -> None:
    """Test that library clean handles partial cleanup gracefully."""
    monkeypatch.chdir(test_project)

    # Remove venv but keep .env-services
    import shutil

    shutil.rmtree(test_project / ".venv")

    # Verify partial state
    assert not (test_project / ".venv").exists()
    assert (test_project / ".env-services").exists()

    runner = CliRunner()
    result = runner.invoke(app, ["library", "clean", "--quiet"])

    # Command should succeed
    assert result.exit_code == 0

    # Verify .env-services was removed
    assert not (test_project / ".env-services").exists()


def test_library_test_after_clean_creates_venv(
    test_project: Path,
    fake_process: FakeProcess,
    monkeypatch,
) -> None:
    """Test that running tests after clean attempts to create venv."""
    monkeypatch.chdir(test_project)

    # Run clean first to remove everything
    runner = CliRunner()
    result = runner.invoke(app, ["library", "clean", "--quiet"])
    assert result.exit_code == 0

    # Verify nothing exists
    assert not (test_project / ".venv").exists()
    assert not (test_project / ".env-services").exists()

    # Register all the commands that test will invoke
    # uv venv creation
    fake_process.register(
        ["uv", "venv", "--python", fake_process.any()],
        stdout="",
    )

    # Install commands
    fake_process.register(
        [fake_process.any()],
        stdout="",
        occurrences=20,
    )

    # Now run tests - it should attempt to create venv automatically
    result = runner.invoke(app, ["library", "test", "--quiet", "--skip-services"])

    # Command should succeed (even if venv creation is mocked)
    assert result.exit_code == 0

    # Verify uv venv was called
    assert fake_process.call_count(["uv", "venv", "--python", fake_process.any()]) > 0
