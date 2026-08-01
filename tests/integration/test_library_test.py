# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Integration tests for library test command."""

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
def mock_test_project(tmp_path: Path) -> Path:
    """Create a minimal mock project with tests."""
    project_dir = tmp_path / "test-project"
    project_dir.mkdir()

    # Create pyproject.toml
    pyproject_content = """
[project]
name = "test-project"
version = "1.0.0"
requires-python = ">=3.14,<3.15"

[project.optional-dependencies]
tests = ["pytest>=7.0"]

[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[tool.oarepo-cli]
oarepo.version = 14
"""
    (project_dir / "pyproject.toml").write_text(pyproject_content)

    # Create minimal package structure
    pkg_dir = project_dir / "test_project"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("")

    # Create venv structure
    venv_dir = project_dir / ".venv"
    venv_bin = venv_dir / "bin"
    venv_bin.mkdir(parents=True)

    # Create mock pytest executable
    pytest_bin = venv_bin / "pytest"
    pytest_bin.write_text("#!/bin/sh\necho 'pytest mock'")
    pytest_bin.chmod(0o755)

    # Create mock python executable
    python_bin = venv_bin / "python"
    python_bin.write_text("#!/bin/sh\necho 'python mock'")
    python_bin.chmod(0o755)

    return project_dir


def test_help_displays(runner: CliRunner) -> None:
    """Test that 'library test --help' displays help text."""
    result = runner.invoke(app, ["library", "test", "--help"])

    assert result.exit_code == 0
    assert "test" in result.stdout.lower()
    assert "pytest" in result.stdout.lower()


def test_runs_tests_successfully(
    runner: CliRunner,
    mock_test_project: Path,
    monkeypatch: pytest.MonkeyPatch,
    fake_process: FakeProcess,
) -> None:
    """Test that test command runs pytest successfully."""
    monkeypatch.chdir(mock_test_project)

    # Register docker-services-cli up
    fake_process.register(
        [
            "uvx",
            "--with",
            "setuptools",
            "docker-services-cli",
            "up",
            fake_process.any(),
        ],
        stdout="export DATABASE_URL=postgresql://localhost:5432/test\n",
    )

    # Register test dependency installation
    fake_process.register(
        ["uv", "pip", "install", "-e", ".[tests]"],
        stdout="Installing dependencies\n",
    )

    # Register pytest execution (success)
    fake_process.register(
        [str(mock_test_project / ".venv" / "bin" / "pytest")],
        stdout="===== 10 passed in 0.5s =====\n",
        returncode=0,
    )

    # Register docker-services-cli down
    fake_process.register(
        ["uvx", "--with", "setuptools", "docker-services-cli", "down", "--env"],
        stdout="",
    )

    result = runner.invoke(app, ["library", "test"])

    # Should exit successfully
    assert result.exit_code == 0
    assert "passed" in result.stdout.lower() or "success" in result.stdout.lower()


def test_with_coverage_flag(
    runner: CliRunner,
    mock_test_project: Path,
    monkeypatch: pytest.MonkeyPatch,
    fake_process: FakeProcess,
) -> None:
    """Test that --with-coverage flag adds coverage arguments."""
    monkeypatch.chdir(mock_test_project)

    # Register docker-services-cli up
    fake_process.register(
        [
            "uvx",
            "--with",
            "setuptools",
            "docker-services-cli",
            "up",
            fake_process.any(),
        ],
        stdout="export DATABASE_URL=test\n",
    )

    # Register test dependency installation
    fake_process.register(
        ["uv", "pip", "install", "-e", ".[tests]"],
        stdout="",
    )

    # Check if pytest-cov is installed
    fake_process.register(
        [str(mock_test_project / ".venv" / "bin" / "python"), "-c", "import pytest_cov"],
        returncode=1,  # Not installed
    )

    # Install pytest-cov
    fake_process.register(
        ["uv", "pip", "install", "pytest-cov"],
        stdout="Installing pytest-cov\n",
    )

    # Register pytest with coverage flags
    fake_process.register(
        [
            str(mock_test_project / ".venv" / "bin" / "pytest"),
            "--cov",
            "test_project",
            "--cov-report=html",
            "--cov-report=term",
        ],
        stdout="Coverage: 95%\n===== 10 passed in 0.5s =====\n",
        returncode=0,
    )

    # Register docker-services-cli down
    fake_process.register(
        ["uvx", "--with", "setuptools", "docker-services-cli", "down", "--env"],
        stdout="",
    )

    result = runner.invoke(app, ["library", "test", "--with-coverage"])

    # Should exit successfully
    assert result.exit_code == 0


def test_skip_services_flag(
    runner: CliRunner,
    mock_test_project: Path,
    monkeypatch: pytest.MonkeyPatch,
    fake_process: FakeProcess,
) -> None:
    """Test that --skip-services flag skips Docker services."""
    monkeypatch.chdir(mock_test_project)

    # Only register test dependencies and pytest (no docker-services-cli)
    fake_process.register(
        ["uv", "pip", "install", "-e", ".[tests]"],
        stdout="",
    )

    fake_process.register(
        [str(mock_test_project / ".venv" / "bin" / "pytest")],
        stdout="===== 10 passed in 0.5s =====\n",
        returncode=0,
    )

    result = runner.invoke(app, ["library", "test", "--skip-services"])

    # Should exit successfully
    assert result.exit_code == 0

    # Verify no docker-services-cli was called
    assert fake_process.call_count(["uvx", fake_process.any()]) == 0


def test_extra_pytest_args_passed_through(
    runner: CliRunner,
    mock_test_project: Path,
    monkeypatch: pytest.MonkeyPatch,
    fake_process: FakeProcess,
) -> None:
    """Test that extra arguments are passed to pytest."""
    monkeypatch.chdir(mock_test_project)

    # Register docker-services-cli up
    fake_process.register(
        [
            "uvx",
            "--with",
            "setuptools",
            "docker-services-cli",
            "up",
            fake_process.any(),
        ],
        stdout="export DATABASE_URL=test\n",
    )

    # Register test dependency installation
    fake_process.register(
        ["uv", "pip", "install", "-e", ".[tests]"],
        stdout="",
    )

    # Register pytest with extra args
    fake_process.register(
        [
            str(mock_test_project / ".venv" / "bin" / "pytest"),
            "-v",
            "-x",
            "tests/unit/",
        ],
        stdout="===== 5 passed in 0.3s =====\n",
        returncode=0,
    )

    # Register docker-services-cli down
    fake_process.register(
        ["uvx", "--with", "setuptools", "docker-services-cli", "down", "--env"],
        stdout="",
    )

    result = runner.invoke(app, ["library", "test", "-v", "-x", "tests/unit/"])

    # Should exit successfully
    assert result.exit_code == 0


def test_exit_code_on_test_failure(
    runner: CliRunner,
    mock_test_project: Path,
    monkeypatch: pytest.MonkeyPatch,
    fake_process: FakeProcess,
) -> None:
    """Test that test command exits with pytest's exit code on failure."""
    monkeypatch.chdir(mock_test_project)

    # Register docker-services-cli up
    fake_process.register(
        [
            "uvx",
            "--with",
            "setuptools",
            "docker-services-cli",
            "up",
            fake_process.any(),
        ],
        stdout="export DATABASE_URL=test\n",
    )

    # Register test dependency installation
    fake_process.register(
        ["uv", "pip", "install", "-e", ".[tests]"],
        stdout="",
    )

    # Register pytest execution (failure)
    fake_process.register(
        [str(mock_test_project / ".venv" / "bin" / "pytest")],
        stdout="FAILED tests/test_something.py::test_func\n===== 1 failed, 9 passed in 0.5s =====\n",
        returncode=1,
    )

    # Register docker-services-cli down (should still be called)
    fake_process.register(
        ["uvx", "--with", "setuptools", "docker-services-cli", "down", "--env"],
        stdout="",
    )

    result = runner.invoke(app, ["library", "test"])

    # Should exit with pytest's exit code
    assert result.exit_code == 1
    # Note: with interactive=True, pytest output goes to terminal, not captured by runner


def test_combined_flags(
    runner: CliRunner,
    mock_test_project: Path,
    monkeypatch: pytest.MonkeyPatch,
    fake_process: FakeProcess,
) -> None:
    """Test that --skip-services and --with-coverage can be combined."""
    monkeypatch.chdir(mock_test_project)

    # Only register test dependencies and pytest (no docker-services-cli)
    fake_process.register(
        ["uv", "pip", "install", "-e", ".[tests]"],
        stdout="",
    )

    # Check if pytest-cov is installed
    fake_process.register(
        [str(mock_test_project / ".venv" / "bin" / "python"), "-c", "import pytest_cov"],
        returncode=0,  # Already installed
    )

    # Register pytest with coverage
    fake_process.register(
        [
            str(mock_test_project / ".venv" / "bin" / "pytest"),
            "--cov",
            "test_project",
            "--cov-report=html",
            "--cov-report=term",
        ],
        stdout="Coverage: 95%\n===== 10 passed in 0.5s =====\n",
        returncode=0,
    )

    result = runner.invoke(app, ["library", "test", "--skip-services", "--with-coverage"])

    # Should exit successfully
    assert result.exit_code == 0

    # Verify no docker-services-cli was called
    assert fake_process.call_count(["uvx", fake_process.any()]) == 0


def test_interspersed_flags(
    runner: CliRunner,
    mock_test_project: Path,
    monkeypatch: pytest.MonkeyPatch,
    fake_process: FakeProcess,
) -> None:
    """Test that pytest flags can be interspersed with oarepo-cli flags."""
    monkeypatch.chdir(mock_test_project)

    # Register docker-services-cli up
    fake_process.register(
        [
            "uvx",
            "--with",
            "setuptools",
            "docker-services-cli",
            "up",
            fake_process.any(),
        ],
        stdout="export DATABASE_URL=test\n",
    )

    # Register test dependency installation
    fake_process.register(
        ["uv", "pip", "install", "-e", ".[tests]"],
        stdout="",
    )

    # Register pytest with mixed args
    fake_process.register(
        [
            str(mock_test_project / ".venv" / "bin" / "pytest"),
            "-v",
            "-x",
        ],
        stdout="===== 10 passed in 0.5s =====\n",
        returncode=0,
    )

    # Register docker-services-cli down
    fake_process.register(
        ["uvx", "--with", "setuptools", "docker-services-cli", "down", "--env"],
        stdout="",
    )

    # Test with pytest flags interspersed
    result = runner.invoke(app, ["library", "test", "-v", "--skip-services", "-x"])

    # Should exit successfully
    assert result.exit_code == 0

    # Verify no docker-services-cli was called (because --skip-services)
    assert fake_process.call_count(["uvx", fake_process.any()]) == 0
