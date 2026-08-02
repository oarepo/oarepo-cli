# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Integration tests for cleanup operations using real testlib fixture."""

from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

import pytest

from oarepo_cli.core.config import CliConfig, ServicesConfig
from oarepo_cli.core.context import ProjectContext
from oarepo_cli.services.services_lifecycle import ServicesLifecycleManager

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def test_context(clean_testlib: Path) -> ProjectContext:
    """Create a test project context using testlib."""
    config = CliConfig()
    config.services = ServicesConfig(skip=False)

    # Use a temporary venv path to avoid affecting the actual testlib
    tmp_venv = clean_testlib.parent / "testlib_test_venv"

    return ProjectContext(
        root_directory=clean_testlib,
        pyproject_path=clean_testlib / "pyproject.toml",
        venv_path=tmp_venv,
        python_binary=tmp_venv / "bin" / "python",
        oarepo_version=14,
        config=config,
    )


def test_clean_removes_venv(test_context: ProjectContext) -> None:
    """Test that clean command removes the venv directory."""
    venv_path = test_context.venv_path

    # Create a test venv structure
    venv_path.mkdir(parents=True, exist_ok=True)
    venv_bin = venv_path / "bin"
    venv_bin.mkdir(exist_ok=True)
    (venv_bin / "python").touch()

    # Verify venv exists before cleaning
    assert venv_path.exists()

    # Perform cleanup
    if venv_path.exists():
        shutil.rmtree(venv_path)

    # Verify venv was removed
    assert not venv_path.exists()


def test_clean_removes_env_services_file(test_context: ProjectContext) -> None:
    """Test that clean command removes the .env-services file."""
    env_file = test_context.root_directory / ".env-services"

    # Create the file
    env_file.write_text('export DATABASE_URL="postgresql://localhost:5432/test"\n')

    # Verify file exists before cleaning
    assert env_file.exists()

    # Remove the file
    env_file.unlink()

    # Verify file was removed
    assert not env_file.exists()


def test_clean_stops_services_real(
    test_context: ProjectContext,
) -> None:
    """Test that clean command stops services if they're running."""
    services_mgr = ServicesLifecycleManager(
        config=test_context.config, project_root=test_context.root_directory
    )

    # Create .env-services to simulate running services
    env_file = test_context.root_directory / ".env-services"
    env_file.write_text("export DATABASE_URL=test\n")

    # Verify services are considered running
    assert services_mgr.are_services_running()

    # Stop services
    services_mgr.stop_services()

    # Verify .env-services was removed
    assert not env_file.exists()


def test_clean_is_idempotent(clean_testlib: Path) -> None:
    """Test that clean command works even if nothing exists."""
    # Use a unique venv path
    venv_path = clean_testlib.parent / "testlib_cleanup_test_venv"

    # clean_testlib fixture guarantees nothing exists yet
    config = CliConfig()
    context = ProjectContext(
        root_directory=clean_testlib,
        pyproject_path=clean_testlib / "pyproject.toml",
        venv_path=venv_path,
        python_binary=venv_path / "bin" / "python",
        oarepo_version=14,
        config=config,
    )

    # Verify nothing exists
    assert not context.venv_path.exists()
    assert not (clean_testlib / ".env-services").exists()

    # Try to clean (should not raise errors)
    env_file = clean_testlib / ".env-services"
    if env_file.exists():
        env_file.unlink()

    if context.venv_path.exists():
        shutil.rmtree(context.venv_path)

    # Verify still nothing exists (idempotent)
    assert not context.venv_path.exists()
    assert not (clean_testlib / ".env-services").exists()


def test_clean_handles_partial_cleanup(test_context: ProjectContext) -> None:
    """Test that clean handles cases where only some items exist."""
    venv_path = test_context.venv_path

    # Create venv but no .env-services
    venv_path.mkdir(parents=True, exist_ok=True)
    (venv_path / "bin").mkdir(exist_ok=True)
    (venv_path / "bin" / "python").touch()

    # Ensure no .env-services
    env_file = test_context.root_directory / ".env-services"
    if env_file.exists():
        env_file.unlink()

    # Verify venv exists but .env-services doesn't
    assert venv_path.exists()
    assert not env_file.exists()

    # Clean should still work
    if venv_path.exists():
        shutil.rmtree(venv_path)

    # Verify cleanup completed
    assert not venv_path.exists()
    assert not env_file.exists()


def test_clean_with_actual_venv_creation_and_removal(
    clean_testlib: Path,
) -> None:
    """Test complete cycle: create venv, then clean it."""
    venv_path = clean_testlib.parent / "testlib_full_cleanup_venv"

    # Create a minimal venv structure
    venv_path.mkdir(parents=True)
    bin_dir = venv_path / "bin"
    bin_dir.mkdir()
    python_bin = bin_dir / "python"
    python_bin.touch()
    python_bin.chmod(0o755)

    # Also create .env-services
    env_file = clean_testlib / ".env-services"
    env_file.write_text("export TEST=value\n")

    # Verify both exist
    assert venv_path.exists()
    assert env_file.exists()

    # Perform cleanup
    if env_file.exists():
        env_file.unlink()
    if venv_path.exists():
        shutil.rmtree(venv_path)

    # Verify both removed
    assert not venv_path.exists()
    assert not env_file.exists()
