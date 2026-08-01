# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Integration tests for library start/stop commands."""

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


def test_start_creates_env_file(
    runner: CliRunner,
    mock_library_project: Path,
    monkeypatch: pytest.MonkeyPatch,
    fake_process: FakeProcess,
) -> None:
    """Test that start command creates .env-services file."""
    monkeypatch.chdir(mock_library_project)

    # Mock docker-services-cli output
    env_output = "export SQLALCHEMY_DATABASE_URI=postgresql://test\nexport INVENIO_SEARCH_HOSTS=localhost:9200\n"

    # Register docker-services-cli up command
    fake_process.register(
        [
            "uvx",
            "--with",
            "setuptools",
            "docker-services-cli",
            "up",
            "--db",
            "postgresql",
            "--search",
            "opensearch",
            "--mq",
            "rabbitmq",
            "--cache",
            "redis",
            "--s3",
            "minio",
            "--env",
        ],
        stdout=env_output,
    )

    result = runner.invoke(app, ["library", "start"])

    # Should have created .env-services file
    env_file = mock_library_project / ".env-services"
    assert env_file.exists()
    assert env_file.read_text() == env_output

    # Should exit successfully
    assert result.exit_code == 0
    assert "started" in result.stdout.lower() or "success" in result.stdout.lower()


def test_stop_removes_env_file(
    runner: CliRunner,
    mock_library_project: Path,
    monkeypatch: pytest.MonkeyPatch,
    fake_process: FakeProcess,
) -> None:
    """Test that stop command removes .env-services file."""
    monkeypatch.chdir(mock_library_project)

    # Create existing .env-services file
    env_file = mock_library_project / ".env-services"
    env_file.write_text("export SQLALCHEMY_DATABASE_URI=postgresql://test\n")

    # Register docker-services-cli down command
    fake_process.register(["uvx", "--with", "setuptools", "docker-services-cli", "down", "--env"])

    result = runner.invoke(app, ["library", "stop"])

    # Should have removed .env-services file
    assert not env_file.exists()

    # Should exit successfully
    assert result.exit_code == 0
    assert "stopped" in result.stdout.lower() or "success" in result.stdout.lower()


def test_stop_when_no_services_running(
    runner: CliRunner,
    mock_library_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that stop command handles no services gracefully."""
    monkeypatch.chdir(mock_library_project)

    # No .env-services file exists

    result = runner.invoke(app, ["library", "stop"])

    # Should exit successfully with message
    assert result.exit_code == 0
    assert "no services" in result.stdout.lower() or "not running" in result.stdout.lower()


def test_start_exit_code_on_failure(
    runner: CliRunner,
    mock_library_project: Path,
    monkeypatch: pytest.MonkeyPatch,
    fake_process: FakeProcess,
) -> None:
    """Test that start command exits with code 1 on failure."""
    monkeypatch.chdir(mock_library_project)

    # Register docker-services-cli to fail
    fake_process.register(
        [
            "uvx",
            "--with",
            "setuptools",
            "docker-services-cli",
            "up",
            "--db",
            "postgresql",
            "--search",
            "opensearch",
            "--mq",
            "rabbitmq",
            "--cache",
            "redis",
            "--s3",
            "minio",
            "--env",
        ],
        returncode=1,
        stderr="Docker not running",
    )

    result = runner.invoke(app, ["library", "start"])

    # Should exit with code 1
    assert result.exit_code == 1


def test_stop_exit_code_on_failure(
    runner: CliRunner,
    mock_library_project: Path,
    monkeypatch: pytest.MonkeyPatch,
    fake_process: FakeProcess,
) -> None:
    """Test that stop command exits with code 1 on failure."""
    monkeypatch.chdir(mock_library_project)

    # Create existing .env-services file
    env_file = mock_library_project / ".env-services"
    env_file.write_text("export SQLALCHEMY_DATABASE_URI=postgresql://test\n")

    # Register docker-services-cli to fail
    fake_process.register(
        ["uvx", "--with", "setuptools", "docker-services-cli", "down", "--env"],
        returncode=1,
        stderr="Docker not running",
    )

    result = runner.invoke(app, ["library", "stop"])

    # Should exit with code 1
    assert result.exit_code == 1


# Test the services subcommand aliases


def test_services_start_alias(
    runner: CliRunner,
    mock_library_project: Path,
    monkeypatch: pytest.MonkeyPatch,
    fake_process: FakeProcess,
) -> None:
    """Test that 'library services start' works as an alias."""
    monkeypatch.chdir(mock_library_project)

    # Mock docker-services-cli output
    env_output = "export SQLALCHEMY_DATABASE_URI=postgresql://test\n"

    # Register docker-services-cli up command
    fake_process.register(
        [
            "uvx",
            "--with",
            "setuptools",
            "docker-services-cli",
            "up",
            "--db",
            "postgresql",
            "--search",
            "opensearch",
            "--mq",
            "rabbitmq",
            "--cache",
            "redis",
            "--s3",
            "minio",
            "--env",
        ],
        stdout=env_output,
    )

    result = runner.invoke(app, ["library", "services", "start"])

    # Should have created .env-services file
    env_file = mock_library_project / ".env-services"
    assert env_file.exists()
    assert env_file.read_text() == env_output

    # Should exit successfully
    assert result.exit_code == 0


def test_services_stop_alias(
    runner: CliRunner,
    mock_library_project: Path,
    monkeypatch: pytest.MonkeyPatch,
    fake_process: FakeProcess,
) -> None:
    """Test that 'library services stop' works as an alias."""
    monkeypatch.chdir(mock_library_project)

    # Create existing .env-services file
    env_file = mock_library_project / ".env-services"
    env_file.write_text("export SQLALCHEMY_DATABASE_URI=postgresql://test\n")

    # Register docker-services-cli down command
    fake_process.register(["uvx", "--with", "setuptools", "docker-services-cli", "down", "--env"])

    result = runner.invoke(app, ["library", "services", "stop"])

    # Should have removed .env-services file
    assert not env_file.exists()

    # Should exit successfully
    assert result.exit_code == 0


def test_services_help_displays(
    runner: CliRunner,
) -> None:
    """Test that 'library services --help' displays help text."""
    result = runner.invoke(app, ["library", "services", "--help"])

    assert result.exit_code == 0
    assert "services" in result.stdout.lower()
    assert "start" in result.stdout.lower()
    assert "stop" in result.stdout.lower()
