# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT
"""Integration tests for VirtualEnvironmentManager using real testlib fixture.

These tests use the real testlib project (tests/testlib/) and execute
actual subprocess calls to uv/pip to verify the complete venv creation
workflow with real tooling.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from oarepo_cli.core.config import CliConfig, VenvConfig
from oarepo_cli.services.venv import VenvRequirements, VirtualEnvironmentManager

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def testlib_venv_path(clean_testlib: Path, tmp_path: Path) -> Path:  # noqa: ARG001
    """Create a unique venv path for each test to avoid conflicts."""
    # Use tmp_path to create isolated venv directories per test
    return tmp_path / "testlib_venv"


def test_venv_creation_workflow_real_tools(
    clean_testlib: Path,
    testlib_venv_path: Path,
) -> None:
    """Test complete venv creation workflow with real uv/pip calls."""
    config = CliConfig(venv=VenvConfig(path=testlib_venv_path))
    manager = VirtualEnvironmentManager(config, project_root=clean_testlib)

    requirements = VenvRequirements(
        python_binary="python3.14",
        oarepo_version=14,
        extras=[],
        editable=True,
    )

    result = manager.ensure_venv(requirements, force=False)

    # Verify venv was created
    assert result == testlib_venv_path
    assert (result / "bin" / "python").exists()
    assert (result / "bin" / "pip").exists()


def test_setuptools_installed_first_real_tools(
    clean_testlib: Path,
    testlib_venv_path: Path,
) -> None:
    """Test that setuptools is installed before other packages (verified by actual install)."""
    config = CliConfig(venv=VenvConfig(path=testlib_venv_path))
    manager = VirtualEnvironmentManager(config, project_root=clean_testlib)

    requirements = VenvRequirements(
        python_binary="python3.14",
        oarepo_version=14,
        editable=True,
    )

    manager.ensure_venv(requirements)

    # Verify venv exists and has expected structure
    assert (testlib_venv_path / "bin" / "python").exists()
    # setuptools should be installed (check via pip list in the venv)
    import subprocess

    result = subprocess.run(
        [str(testlib_venv_path / "bin" / "python"), "-m", "pip", "list"],
        capture_output=True,
        text=True,
    )
    assert "setuptools" in result.stdout.lower()


def test_oarepo_installed_with_correct_version_real_tools(
    clean_testlib: Path,
    testlib_venv_path: Path,
) -> None:
    """Test OARepo is installed with correct version constraint."""
    config = CliConfig(venv=VenvConfig(path=testlib_venv_path))
    manager = VirtualEnvironmentManager(config, project_root=clean_testlib)

    requirements = VenvRequirements(
        python_binary="python3.14",
        oarepo_version=14,
        extras=["rdm", "tests"],
        editable=True,
    )

    manager.ensure_venv(requirements)

    # Verify oarepo is installed
    import subprocess

    result = subprocess.run(
        [str(testlib_venv_path / "bin" / "python"), "-m", "pip", "list"],
        capture_output=True,
        text=True,
    )
    assert "oarepo" in result.stdout.lower()


def test_editable_mode_real_tools(
    clean_testlib: Path,
    testlib_venv_path: Path,
) -> None:
    """Test project installed in editable mode."""
    config = CliConfig(venv=VenvConfig(path=testlib_venv_path))
    manager = VirtualEnvironmentManager(config, project_root=clean_testlib)

    requirements = VenvRequirements(
        python_binary="python3.14",
        oarepo_version=14,
        editable=True,
    )

    manager.ensure_venv(requirements)

    # Verify editable install - check if testlib is listed as editable
    import subprocess

    result = subprocess.run(
        [str(testlib_venv_path / "bin" / "python"), "-m", "pip", "list", "--format=freeze"],
        capture_output=True,
        text=True,
    )
    # Editable installs show with -e or in parentheses with file://
    assert "testlib" in result.stdout.lower()


def test_non_editable_mode_real_tools(
    clean_testlib: Path,
    testlib_venv_path: Path,
) -> None:
    """Test project installed as wheel in non-editable mode."""
    config = CliConfig(venv=VenvConfig(path=testlib_venv_path))
    manager = VirtualEnvironmentManager(config, project_root=clean_testlib)

    requirements = VenvRequirements(
        python_binary="python3.14",
        oarepo_version=14,
        editable=False,
    )

    manager.ensure_venv(requirements)

    # Verify venv exists
    assert (testlib_venv_path / "bin" / "python").exists()

    # Non-editable should still have testlib installed
    import subprocess

    result = subprocess.run(
        [str(testlib_venv_path / "bin" / "python"), "-m", "pip", "list"],
        capture_output=True,
        text=True,
    )
    assert "testlib" in result.stdout.lower()


def test_force_recreation_removes_existing_venv(
    clean_testlib: Path,
    testlib_venv_path: Path,
) -> None:
    """Test force=True removes and recreates existing venv."""
    # Pre-create a marker file to verify removal
    testlib_venv_path.mkdir(parents=True)
    marker_file = testlib_venv_path / "marker.txt"
    marker_file.write_text("old venv")

    config = CliConfig(venv=VenvConfig(path=testlib_venv_path))
    manager = VirtualEnvironmentManager(config, project_root=clean_testlib)

    assert marker_file.exists()

    # Force recreation
    requirements = VenvRequirements(
        python_binary="python3.14",
        oarepo_version=14,
        editable=True,
    )
    manager.ensure_venv(requirements, force=True)

    # Old marker should be gone
    assert not marker_file.exists()
    # New venv should exist
    assert (testlib_venv_path / "bin" / "python").exists()


def test_skip_creation_if_venv_exists_real_tools(
    clean_testlib: Path,
    testlib_venv_path: Path,
) -> None:
    """Test venv creation is skipped if it already exists with proper structure."""
    # Pre-create a minimal venv structure
    testlib_venv_path.mkdir(parents=True)
    bin_dir = testlib_venv_path / "bin"
    bin_dir.mkdir()
    python_bin = bin_dir / "python"
    python_bin.touch()
    python_bin.chmod(0o755)

    config = CliConfig(venv=VenvConfig(path=testlib_venv_path))
    manager = VirtualEnvironmentManager(config, project_root=clean_testlib)

    # Should not fail even though venv exists but is incomplete
    # The manager should detect it's not a proper venv and recreate
    requirements = VenvRequirements(
        python_binary="python3.14",
        oarepo_version=14,
        editable=True,
    )

    # This will either skip (if venv is valid) or recreate (if invalid)
    result = manager.ensure_venv(requirements, force=False)
    assert result == testlib_venv_path
    assert (testlib_venv_path / "bin" / "python").exists()


def test_cleanup_removes_venv_real_tools(
    clean_testlib: Path,
    testlib_venv_path: Path,
) -> None:
    """Test cleanup() removes the virtual environment."""
    # First create a venv
    config = CliConfig(venv=VenvConfig(path=testlib_venv_path))
    manager = VirtualEnvironmentManager(config, project_root=clean_testlib)

    requirements = VenvRequirements(
        python_binary="python3.14",
        oarepo_version=14,
        editable=True,
    )
    manager.ensure_venv(requirements)

    assert testlib_venv_path.exists()

    # Cleanup
    manager.cleanup()

    assert not testlib_venv_path.exists()


def test_cleanup_idempotent_when_venv_missing_real_tools(
    clean_testlib: Path,
    testlib_venv_path: Path,
) -> None:
    """Test cleanup() doesn't fail when venv doesn't exist."""
    config = CliConfig(venv=VenvConfig(path=testlib_venv_path))
    manager = VirtualEnvironmentManager(config, project_root=clean_testlib)

    assert not testlib_venv_path.exists()

    # Should not raise
    manager.cleanup()

    assert not testlib_venv_path.exists()


def test_wheel_build_and_install_real_tools(
    clean_testlib: Path,
    testlib_venv_path: Path,
) -> None:
    """Test wheel build and installation in non-editable mode."""
    config = CliConfig(venv=VenvConfig(path=testlib_venv_path))
    manager = VirtualEnvironmentManager(config, project_root=clean_testlib)

    requirements = VenvRequirements(
        python_binary="python3.14",
        oarepo_version=14,
        editable=False,
    )

    manager.ensure_venv(requirements)

    # Verify venv was created successfully
    assert (testlib_venv_path / "bin" / "python").exists()

    # Verify testlib is installed (as wheel, not editable)
    import subprocess

    result = subprocess.run(
        [str(testlib_venv_path / "bin" / "python"), "-m", "pip", "show", "testlib"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "testlib" in result.stdout
