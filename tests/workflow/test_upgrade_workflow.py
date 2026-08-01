# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Workflow tests for library upgrade command."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from oarepo_cli.cli.main import app

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_subprocess import FakeProcess


@pytest.fixture
def runner() -> CliRunner:
    """Provide a Typer CLI runner."""
    return CliRunner()


@pytest.fixture
def mock_library_project(tmp_path: Path) -> Path:
    """Create a minimal mock library project."""
    project_dir = tmp_path / "test-library"
    project_dir.mkdir()

    # Create pyproject.toml
    pyproject_content = """
[project]
name = "test-library"
version = "1.0.0"
requires-python = ">=3.14,<3.15"

[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[tool.oarepo-cli]
oarepo.version = 14
"""
    (project_dir / "pyproject.toml").write_text(pyproject_content)

    # Create minimal package structure
    pkg_dir = project_dir / "test_library"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("")

    return project_dir


def test_upgrade_help_displays(runner: CliRunner) -> None:
    """Test that 'library upgrade --help' displays help text."""
    result = runner.invoke(app, ["library", "upgrade", "--help"])

    assert result.exit_code == 0
    assert "upgrade" in result.stdout.lower()
    assert "clean" in result.stdout.lower() or "cache" in result.stdout.lower()


def test_upgrade_cleans_cache(
    runner: CliRunner,
    mock_library_project: Path,
    monkeypatch: pytest.MonkeyPatch,
    fake_process: FakeProcess,
) -> None:
    """Test that upgrade command cleans uv cache."""
    monkeypatch.chdir(mock_library_project)

    # Register the uv cache clean command
    fake_process.register(["uv", "cache", "clean"])

    # Register other uv commands for venv creation (will be called by ensure_venv)
    fake_process.register(["uv", "venv", fake_process.any()])
    fake_process.register([fake_process.any(), "-m", "pip", "install", "setuptools"])
    fake_process.register(
        ["uv", "pip", "install", "--prerelease", "allow", fake_process.any()],
        occurrences=2,
    )

    result = runner.invoke(app, ["library", "upgrade"])

    # Should have called uv cache clean
    assert fake_process.call_count(["uv", "cache", "clean"]) >= 1
    assert result.exit_code == 0


def test_upgrade_recreates_venv(
    runner: CliRunner,
    mock_library_project: Path,
    monkeypatch: pytest.MonkeyPatch,
    fake_process: FakeProcess,
) -> None:
    """Test that upgrade command recreates virtual environment."""
    monkeypatch.chdir(mock_library_project)

    # Create an existing .venv directory
    venv_path = mock_library_project / ".venv"
    venv_path.mkdir()
    marker_file = venv_path / "old_marker.txt"
    marker_file.write_text("old")

    # Register subprocess calls
    fake_process.register(["uv", "cache", "clean"])
    fake_process.register(["uv", "venv", fake_process.any()])
    fake_process.register([fake_process.any(), "-m", "pip", "install", "setuptools"])
    fake_process.register(
        ["uv", "pip", "install", "--prerelease", "allow", fake_process.any()],
        occurrences=2,
    )

    result = runner.invoke(app, ["library", "upgrade"])

    # The old marker file should be gone (venv was recreated)
    assert not marker_file.exists()
    assert result.exit_code == 0


def test_upgrade_displays_success_message(
    runner: CliRunner,
    mock_library_project: Path,
    monkeypatch: pytest.MonkeyPatch,
    fake_process: FakeProcess,
) -> None:
    """Test that upgrade command displays success message."""
    monkeypatch.chdir(mock_library_project)

    # Register subprocess calls - need to be more specific about the order
    fake_process.register(["uv", "cache", "clean"])
    fake_process.register(["uv", "venv", fake_process.any()])
    fake_process.register([fake_process.any(), "-m", "pip", "install", "setuptools"])
    fake_process.register(
        ["uv", "pip", "install", "--prerelease", "allow", fake_process.any()],
        occurrences=2,  # Once for oarepo, once for project
    )

    result = runner.invoke(app, ["library", "upgrade"])

    # Should complete successfully
    assert result.exit_code == 0
    # Check for success indicators
    assert "completed" in result.stdout.lower() or "upgrade" in result.stdout.lower()
    assert result.exit_code == 0


def test_upgrade_handles_cache_clean_failure(
    runner: CliRunner,
    mock_library_project: Path,
    monkeypatch: pytest.MonkeyPatch,
    fake_process: FakeProcess,
) -> None:
    """Test that upgrade continues even if cache clean fails."""
    monkeypatch.chdir(mock_library_project)

    # Register cache clean to fail
    fake_process.register(["uv", "cache", "clean"], returncode=1, stderr="Cache clean failed")

    # Register other commands to succeed
    fake_process.register(["uv", "venv", fake_process.any()])
    fake_process.register([fake_process.any(), "-m", "pip", "install", "setuptools"])
    fake_process.register(
        ["uv", "pip", "install", "--prerelease", "allow", fake_process.any()],
        occurrences=2,
    )

    result = runner.invoke(app, ["library", "upgrade"], catch_exceptions=False)

    # Should still complete successfully (cache clean failure is non-fatal)
    assert result.exit_code == 0
    # Check that "completed" or "upgrade" appears (shows it continued despite failure)
    assert "completed" in result.stdout.lower() or "upgrade" in result.stdout.lower()


def test_upgrade_requires_pyproject(
    runner: CliRunner,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that upgrade fails gracefully without pyproject.toml."""
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    monkeypatch.chdir(empty_dir)

    result = runner.invoke(app, ["library", "upgrade"])

    assert result.exit_code != 0
    # The error is raised as an exception
    assert (
        result.exception is not None
        and "pyproject.toml" in str(result.exception).lower()
        or result.stdout
    )


def test_upgrade_stops_services_if_running(
    runner: CliRunner,
    mock_library_project: Path,
    monkeypatch: pytest.MonkeyPatch,
    fake_process: FakeProcess,
) -> None:
    """Test that upgrade stops services before recreating venv."""
    monkeypatch.chdir(mock_library_project)

    # Create .env-services file to simulate running services
    env_services = mock_library_project / ".env-services"
    env_services.write_text("export SQLALCHEMY_DATABASE_URI=postgresql://test")

    # Register docker-services-cli down command
    fake_process.register(["uvx", "--with", "setuptools", "docker-services-cli", "down", "--env"])

    # Register other commands
    fake_process.register(["uv", "cache", "clean"])
    fake_process.register(["uv", "venv", fake_process.any()])
    fake_process.register([fake_process.any(), "-m", "pip", "install", "setuptools"])
    fake_process.register(
        ["uv", "pip", "install", "--prerelease", "allow", fake_process.any()],
        occurrences=2,
    )

    result = runner.invoke(app, ["library", "upgrade"])

    # Should have called docker-services-cli down
    assert (
        fake_process.call_count(
            ["uvx", "--with", "setuptools", "docker-services-cli", "down", "--env"]
        )
        >= 1
    )
    # .env-services should be removed
    assert not env_services.exists()
    assert result.exit_code == 0


def test_upgrade_skips_stopping_if_no_services_running(
    runner: CliRunner,
    mock_library_project: Path,
    monkeypatch: pytest.MonkeyPatch,
    fake_process: FakeProcess,
) -> None:
    """Test that upgrade doesn't try to stop services if none are running."""
    monkeypatch.chdir(mock_library_project)

    # No .env-services file (no running services)

    # Register commands - but NOT docker-services-cli down
    fake_process.register(["uv", "cache", "clean"])
    fake_process.register(["uv", "venv", fake_process.any()])
    fake_process.register([fake_process.any(), "-m", "pip", "install", "setuptools"])
    fake_process.register(
        ["uv", "pip", "install", "--prerelease", "allow", fake_process.any()],
        occurrences=2,
    )

    result = runner.invoke(app, ["library", "upgrade"])

    # Should NOT have called docker-services-cli down
    assert (
        fake_process.call_count(
            ["uvx", "--with", "setuptools", "docker-services-cli", "down", "--env"]
        )
        == 0
    )
    assert result.exit_code == 0
