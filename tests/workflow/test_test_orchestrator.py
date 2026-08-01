# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Workflow tests for test orchestrator."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from oarepo_cli.core.config import CliConfig, ServicesConfig, TestingConfig
from oarepo_cli.core.context import ProjectContext
from oarepo_cli.services.test_orchestrator import TestOrchestrator

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_subprocess import FakeProcess


@pytest.fixture
def test_project(tmp_path: Path) -> Path:
    """Create a minimal test project structure."""
    # Create pyproject.toml
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[project]
name = "test-package"
version = "1.0.0"

[project.optional-dependencies]
tests = ["pytest>=7.0"]

[tool.oarepo-cli]
[tool.oarepo-cli.oarepo]
version = 14
"""
    )

    # Create venv structure
    venv_path = tmp_path / ".venv"
    venv_bin = venv_path / "bin"
    venv_bin.mkdir(parents=True)

    # Create dummy pytest executable
    pytest_bin = venv_bin / "pytest"
    pytest_bin.write_text("#!/bin/sh\necho 'pytest mock'")
    pytest_bin.chmod(0o755)

    # Create dummy python executable
    python_bin = venv_bin / "python"
    python_bin.write_text("#!/bin/sh\necho 'python mock'")
    python_bin.chmod(0o755)

    return tmp_path


@pytest.fixture
def test_context(test_project: Path) -> ProjectContext:
    """Create a test project context."""
    config = CliConfig()
    config.test = TestingConfig(coverage=False, skip_services=False)
    config.services = ServicesConfig(skip=False)

    return ProjectContext(
        root_directory=test_project,
        pyproject_path=test_project / "pyproject.toml",
        venv_path=test_project / ".venv",
        python_binary=test_project / ".venv" / "bin" / "python",
        oarepo_version=14,
        config=config,
    )


def test_starts_services_before_tests(
    test_context: ProjectContext,
    fake_process: FakeProcess,
) -> None:
    """Test that services are started before pytest runs."""
    orchestrator = TestOrchestrator(test_context)

    # Register commands in expected order
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
    fake_process.register(
        ["uv", "pip", "install", "-e", ".[tests]"],
        stdout="Installing test dependencies\n",
    )
    fake_process.register(
        [str(test_context.venv_path / "bin" / "pytest")],
        stdout="All tests passed\n",
        returncode=0,
    )
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

    orchestrator.run_tests()

    # Verify docker-services-cli up was called
    assert (
        fake_process.call_count(
            [
                "uvx",
                "--with",
                "setuptools",
                "docker-services-cli",
                "up",
                fake_process.any(),
            ]
        )
        > 0
    )
    # Verify pytest was called
    assert fake_process.call_count([str(test_context.venv_path / "bin" / "pytest")]) > 0


def test_stops_services_after_tests(
    test_context: ProjectContext,
    fake_process: FakeProcess,
) -> None:
    """Test that services are stopped after pytest completes."""
    orchestrator = TestOrchestrator(test_context)

    # Register commands
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
    fake_process.register(
        ["uv", "pip", "install", "-e", ".[tests]"],
        stdout="",
    )
    fake_process.register(
        [str(test_context.venv_path / "bin" / "pytest")],
        stdout="All tests passed\n",
        returncode=0,
    )
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

    orchestrator.run_tests()

    # Verify both pytest and services down were called
    assert fake_process.call_count([str(test_context.venv_path / "bin" / "pytest")]) > 0
    assert (
        fake_process.call_count(
            [
                "uvx",
                "--with",
                "setuptools",
                "docker-services-cli",
                "down",
                "--env",
            ]
        )
        > 0
    )


def test_passes_coverage_flags_when_enabled(
    test_context: ProjectContext,
    fake_process: FakeProcess,
) -> None:
    """Test that coverage flags are added when coverage is enabled."""
    # Enable coverage in context
    test_context.config.test.coverage = True

    orchestrator = TestOrchestrator(test_context)

    # Register commands
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
    fake_process.register(
        ["uv", "pip", "install", "-e", ".[tests]"],
        stdout="",
    )
    # Check for pytest-cov availability
    fake_process.register(
        [str(test_context.venv_path / "bin" / "python"), "-c", "import pytest_cov"],
        returncode=1,  # Not installed
    )
    # Install pytest-cov
    fake_process.register(
        ["uv", "pip", "install", "pytest-cov"],
        stdout="Installing pytest-cov\n",
    )
    fake_process.register(
        [
            str(test_context.venv_path / "bin" / "pytest"),
            "--cov",
            "test_package",
            "--cov-report=html",
            "--cov-report=term",
        ],
        stdout="Coverage: 100%\n",
        returncode=0,
    )
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

    orchestrator.run_tests()

    # Verify pytest was called with coverage flags
    assert (
        fake_process.call_count(
            [
                str(test_context.venv_path / "bin" / "pytest"),
                "--cov",
                "test_package",
                "--cov-report=html",
                "--cov-report=term",
            ]
        )
        > 0
    )


def test_skips_services_when_configured(
    test_context: ProjectContext,
    fake_process: FakeProcess,
) -> None:
    """Test that services start/stop are skipped when configured."""
    # Skip services in context
    test_context.config.test.skip_services = True

    orchestrator = TestOrchestrator(test_context)

    # Only register pytest command (no docker-services-cli)
    fake_process.register(
        ["uv", "pip", "install", "-e", ".[tests]"],
        stdout="",
    )
    fake_process.register(
        [str(test_context.venv_path / "bin" / "pytest")],
        stdout="All tests passed\n",
        returncode=0,
    )

    orchestrator.run_tests()

    # Verify no docker-services-cli calls were made
    assert (
        fake_process.call_count(
            [
                "uvx",
                "--with",
                "setuptools",
                "docker-services-cli",
                fake_process.any(),
            ]
        )
        == 0
    )


def test_returns_failure_status_on_test_failure(
    test_context: ProjectContext,
    fake_process: FakeProcess,
) -> None:
    """Test that failure status is returned when pytest fails."""
    orchestrator = TestOrchestrator(test_context)

    # Register commands with pytest failure
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
    fake_process.register(
        ["uv", "pip", "install", "-e", ".[tests]"],
        stdout="",
    )
    fake_process.register(
        [str(test_context.venv_path / "bin" / "pytest")],
        stdout="FAILED test_something.py::test_func\n",
        returncode=1,
    )
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

    result = orchestrator.run_tests()

    assert result.return_code == 1
    assert not result.success


def test_stops_services_even_on_pytest_failure(
    test_context: ProjectContext,
    fake_process: FakeProcess,
) -> None:
    """Test that services are stopped even when pytest fails."""
    orchestrator = TestOrchestrator(test_context)

    # Register commands with pytest failure
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
    fake_process.register(
        ["uv", "pip", "install", "-e", ".[tests]"],
        stdout="",
    )
    fake_process.register(
        [str(test_context.venv_path / "bin" / "pytest")],
        stdout="FAILED\n",
        returncode=1,
    )
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

    # Should not raise even though pytest failed
    result = orchestrator.run_tests()

    # Verify services were stopped
    assert (
        fake_process.call_count(
            [
                "uvx",
                "--with",
                "setuptools",
                "docker-services-cli",
                "down",
                "--env",
            ]
        )
        > 0
    )

    # And pytest did fail
    assert result.return_code == 1


def test_passes_additional_pytest_args(
    test_context: ProjectContext,
    fake_process: FakeProcess,
) -> None:
    """Test that additional pytest arguments are passed through."""
    orchestrator = TestOrchestrator(test_context)

    # Register commands
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
    fake_process.register(
        ["uv", "pip", "install", "-e", ".[tests]"],
        stdout="",
    )
    fake_process.register(
        [
            str(test_context.venv_path / "bin" / "pytest"),
            "-v",
            "-x",
            "tests/test_specific.py",
        ],
        stdout="Tests passed\n",
        returncode=0,
    )
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

    orchestrator.run_tests(pytest_args=["-v", "-x", "tests/test_specific.py"])

    # Verify pytest was called with the additional args
    assert (
        fake_process.call_count(
            [
                str(test_context.venv_path / "bin" / "pytest"),
                "-v",
                "-x",
                "tests/test_specific.py",
            ]
        )
        > 0
    )


def test_coverage_override_via_parameter(
    test_context: ProjectContext,
    fake_process: FakeProcess,
) -> None:
    """Test that coverage parameter overrides config."""
    # Config says no coverage
    test_context.config.test.coverage = False

    orchestrator = TestOrchestrator(test_context)

    # Register commands
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
    fake_process.register(
        ["uv", "pip", "install", "-e", ".[tests]"],
        stdout="",
    )
    # Check for pytest-cov
    fake_process.register(
        [str(test_context.venv_path / "bin" / "python"), "-c", "import pytest_cov"],
        returncode=0,  # Already installed
    )
    fake_process.register(
        [
            str(test_context.venv_path / "bin" / "pytest"),
            "--cov",
            "test_package",
            "--cov-report=html",
            "--cov-report=term",
        ],
        stdout="Coverage: 100%\n",
        returncode=0,
    )
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

    # But we pass coverage=True as parameter
    orchestrator.run_tests(coverage=True)

    # Should have coverage flags
    assert (
        fake_process.call_count(
            [
                str(test_context.venv_path / "bin" / "pytest"),
                "--cov",
                "test_package",
                "--cov-report=html",
                "--cov-report=term",
            ]
        )
        > 0
    )


def test_skip_services_override_via_parameter(
    test_context: ProjectContext,
    fake_process: FakeProcess,
) -> None:
    """Test that skip_services parameter overrides config."""
    # Config says use services
    test_context.config.test.skip_services = False

    orchestrator = TestOrchestrator(test_context)

    # Only register pytest command (no docker-services-cli)
    fake_process.register(
        ["uv", "pip", "install", "-e", ".[tests]"],
        stdout="",
    )
    fake_process.register(
        [str(test_context.venv_path / "bin" / "pytest")],
        stdout="All tests passed\n",
        returncode=0,
    )

    # But we pass skip_services=True as parameter
    orchestrator.run_tests(skip_services=True)

    # Should not have any docker-services-cli calls
    assert (
        fake_process.call_count(
            [
                "uvx",
                "--with",
                "setuptools",
                "docker-services-cli",
                fake_process.any(),
            ]
        )
        == 0
    )
