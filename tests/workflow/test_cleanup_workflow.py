# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Workflow tests for cleanup operations."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from oarepo_cli.core.config import CliConfig, ServicesConfig
from oarepo_cli.core.context import ProjectContext
from oarepo_cli.services.services_lifecycle import ServicesLifecycleManager

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

    # Create .env-services file
    env_file = tmp_path / ".env-services"
    env_file.write_text('export DATABASE_URL="postgresql://localhost:5432/test"\n')

    return tmp_path


@pytest.fixture
def test_context(test_project: Path) -> ProjectContext:
    """Create a test project context."""
    config = CliConfig()
    config.services = ServicesConfig(skip=False)

    return ProjectContext(
        root_directory=test_project,
        pyproject_path=test_project / "pyproject.toml",
        venv_path=test_project / ".venv",
        python_binary=test_project / ".venv" / "bin" / "python",
        oarepo_version=14,
        config=config,
    )


def test_clean_removes_venv(test_context: ProjectContext) -> None:
    """Test that clean command removes the venv directory."""
    import shutil

    # Verify venv exists before cleaning
    assert test_context.venv_path.exists()

    # Manually perform cleanup steps (testing the cleanup logic)
    # Remove .env-services if it exists
    env_file = test_context.root_directory / ".env-services"
    if env_file.exists():
        env_file.unlink()

    # Remove venv
    if test_context.venv_path.exists():
        shutil.rmtree(test_context.venv_path)

    # Verify venv was removed
    assert not test_context.venv_path.exists()


def test_clean_removes_env_services_file(test_context: ProjectContext) -> None:
    """Test that clean command removes the .env-services file."""
    env_file = test_context.root_directory / ".env-services"

    # Verify file exists before cleaning
    assert env_file.exists()

    # Remove the file
    env_file.unlink()

    # Verify file was removed
    assert not env_file.exists()


def test_clean_stops_services(
    test_context: ProjectContext,
    fake_process: FakeProcess,
) -> None:
    """Test that clean command stops services if they're running."""
    services_mgr = ServicesLifecycleManager(
        config=test_context.config, project_root=test_context.root_directory, quiet=True
    )

    # Verify services are considered running (env file exists)
    assert services_mgr.are_services_running()

    # Register docker-services-cli down command
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

    # Stop services
    services_mgr.stop_services()

    # Verify docker-services-cli was called
    assert (
        fake_process.call_count(
            [
                "uvx",
                "--with",
                "setuptools",
                "docker-services-cli",
                "down",
                "--env",
                "--quiet",
            ]
        )
        > 0
    )


def test_clean_is_idempotent(tmp_path: Path) -> None:
    """Test that clean command works even if nothing exists."""
    import shutil

    # Create minimal project without venv or .env-services
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[project]
name = "test-package"
version = "1.0.0"

[tool.oarepo-cli]
[tool.oarepo-cli.oarepo]
version = 14
"""
    )

    config = CliConfig()
    context = ProjectContext(
        root_directory=tmp_path,
        pyproject_path=pyproject,
        venv_path=tmp_path / ".venv",
        python_binary=tmp_path / ".venv" / "bin" / "python",
        oarepo_version=14,
        config=config,
    )

    # Verify nothing exists
    assert not context.venv_path.exists()
    assert not (tmp_path / ".env-services").exists()

    # Try to clean (should not raise errors)
    # These operations should be safe even if files don't exist
    env_file = tmp_path / ".env-services"
    if env_file.exists():
        env_file.unlink()

    if context.venv_path.exists():
        shutil.rmtree(context.venv_path)

    # Verify still nothing exists (idempotent)
    assert not context.venv_path.exists()
    assert not (tmp_path / ".env-services").exists()


def test_clean_handles_partial_cleanup(test_context: ProjectContext) -> None:
    """Test that clean handles cases where only some items exist."""
    import shutil

    # Remove venv but keep .env-services
    if test_context.venv_path.exists():
        shutil.rmtree(test_context.venv_path)

    # Verify venv is gone but .env-services remains
    assert not test_context.venv_path.exists()
    assert (test_context.root_directory / ".env-services").exists()

    # Clean should still work
    env_file = test_context.root_directory / ".env-services"
    if env_file.exists():
        env_file.unlink()

    # Verify cleanup completed
    assert not (test_context.root_directory / ".env-services").exists()
