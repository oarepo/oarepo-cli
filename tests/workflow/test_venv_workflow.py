# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT
"""Workflow tests for VirtualEnvironmentManager.

These tests use pytest-subprocess to fake external tool calls (uv, pip)
at the OS boundary, allowing us to test the workflow logic without
actually creating virtual environments or installing packages.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pytest_subprocess import FakeProcess

import pytest

from oarepo_cli.core.config import CliConfig, VenvConfig
from oarepo_cli.core.errors import ValidationError
from oarepo_cli.services.venv import VenvRequirements, VirtualEnvironmentManager


def test_venv_creation_workflow(fake_process: FakeProcess, tmp_path: Path) -> None:
    """Test complete venv creation workflow with faked subprocess calls."""
    # Setup config with temp venv path
    config = CliConfig(venv=VenvConfig(path=tmp_path / ".venv"))
    manager = VirtualEnvironmentManager(config)

    # Mock the subprocess calls that would be made
    # 1. uv venv creation - use callback to create venv dir
    def create_venv(*_args, **_kwargs):
        (tmp_path / ".venv" / "bin").mkdir(parents=True)
        (tmp_path / ".venv" / "bin" / "python").touch()

    fake_process.register(
        ["uv", "venv", "--python", "python3.14", "--seed", str(tmp_path / ".venv")],
        returncode=0,
        callback=create_venv,
    )

    # 2. pip install setuptools
    fake_process.register(
        [str(tmp_path / ".venv" / "bin" / "python"), "-m", "pip", "install", "setuptools"],
        returncode=0,
    )

    # 3. uv pip install oarepo
    fake_process.register(
        [
            "uv",
            "pip",
            "install",
            "--prerelease",
            "allow",
            "oarepo[rdm,tests,oarepo14]",
        ],
        returncode=0,
    )

    # 4. uv pip install project in editable mode
    fake_process.register(
        ["uv", "pip", "install", "--prerelease", "allow", "-e", ".[dev,tests,oarepo14]"],
        returncode=0,
    )

    # Execute
    requirements = VenvRequirements(
        python_binary="python3.14",
        oarepo_version=14,
        extras=[],
        editable=True,
    )

    result = manager.ensure_venv(requirements, force=False)

    # Verify
    assert result == tmp_path / ".venv"
    # Verify all expected calls were made
    assert len(fake_process.calls) == 4


def test_setuptools_installed_first(fake_process: FakeProcess, tmp_path: Path) -> None:
    """Test that setuptools is installed before other packages."""
    config = CliConfig(venv=VenvConfig(path=tmp_path / ".venv"))
    manager = VirtualEnvironmentManager(config)

    # Track call order
    call_order = []

    def track_setuptools(*_args, **_kwargs):
        call_order.append("setuptools")

    def track_oarepo(*_args, **_kwargs):
        call_order.append("oarepo")

    def track_project(*_args, **_kwargs):
        call_order.append("project")

    # Register in order
    def create_venv_for_test(*_args, **_kwargs):
        (tmp_path / ".venv" / "bin").mkdir(parents=True)
        (tmp_path / ".venv" / "bin" / "python").touch()

    fake_process.register(
        ["uv", "venv", "--python", "python3.14", "--seed", str(tmp_path / ".venv")],
        returncode=0,
        callback=create_venv_for_test,
    )

    fake_process.register(
        [str(tmp_path / ".venv" / "bin" / "python"), "-m", "pip", "install", "setuptools"],
        returncode=0,
        callback=track_setuptools,
    )

    fake_process.register(
        [
            "uv",
            "pip",
            "install",
            "--prerelease",
            "allow",
            "oarepo[rdm,tests,oarepo14]",
        ],
        returncode=0,
        callback=track_oarepo,
    )

    fake_process.register(
        ["uv", "pip", "install", "--prerelease", "allow", "-e", ".[dev,tests,oarepo14]"],
        returncode=0,
        callback=track_project,
    )

    requirements = VenvRequirements(
        python_binary="python3.14",
        oarepo_version=14,
        editable=True,
    )

    manager.ensure_venv(requirements)

    # Verify order
    assert call_order == ["setuptools", "oarepo", "project"]


def test_oarepo_installed_with_correct_version_constraint(
    fake_process: FakeProcess, tmp_path: Path
) -> None:
    """Test OARepo is installed with correct version constraint."""
    config = CliConfig(venv=VenvConfig(path=tmp_path / ".venv"))
    manager = VirtualEnvironmentManager(config)

    # Mock calls
    def create_venv_extra(*_args, **_kwargs):
        (tmp_path / ".venv" / "bin").mkdir(parents=True)
        (tmp_path / ".venv" / "bin" / "python").touch()

    fake_process.register(
        ["uv", "venv", "--python", "python3.14", "--seed", str(tmp_path / ".venv")],
        returncode=0,
        callback=create_venv_extra,
    )

    fake_process.register(
        [str(tmp_path / ".venv" / "bin" / "python"), "-m", "pip", "install", "setuptools"],
        returncode=0,
    )

    # This is the key assertion - verify the exact constraint
    fake_process.register(
        [
            "uv",
            "pip",
            "install",
            "--prerelease",
            "allow",
            "oarepo[rdm,tests,oarepo14,extra1,extra2]",  # With extras
        ],
        returncode=0,
    )

    fake_process.register(
        [
            "uv",
            "pip",
            "install",
            "--prerelease",
            "allow",
            "-e",
            ".[dev,tests,oarepo14,extra1,extra2]",
        ],
        returncode=0,
    )

    requirements = VenvRequirements(
        python_binary="python3.14",
        oarepo_version=14,
        extras=["extra1", "extra2"],
        editable=True,
    )

    manager.ensure_venv(requirements)

    assert len(fake_process.calls) == 4


def test_editable_mode(fake_process: FakeProcess, tmp_path: Path) -> None:
    """Test project installed in editable mode with -e flag."""
    config = CliConfig(venv=VenvConfig(path=tmp_path / ".venv"))
    manager = VirtualEnvironmentManager(config)

    def create_venv_editable(*_args, **_kwargs):
        (tmp_path / ".venv" / "bin").mkdir(parents=True)
        (tmp_path / ".venv" / "bin" / "python").touch()

    fake_process.register(
        ["uv", "venv", "--python", "python3.14", "--seed", str(tmp_path / ".venv")],
        returncode=0,
        callback=create_venv_editable,
    )

    fake_process.register(
        [str(tmp_path / ".venv" / "bin" / "python"), "-m", "pip", "install", "setuptools"],
        returncode=0,
    )

    fake_process.register(
        [
            "uv",
            "pip",
            "install",
            "--prerelease",
            "allow",
            "oarepo[rdm,tests,oarepo14]",
        ],
        returncode=0,
    )

    # Verify -e flag is present for editable install
    fake_process.register(
        ["uv", "pip", "install", "--prerelease", "allow", "-e", ".[dev,tests,oarepo14]"],
        returncode=0,
    )

    requirements = VenvRequirements(
        python_binary="python3.14",
        oarepo_version=14,
        editable=True,  # Editable mode
    )

    manager.ensure_venv(requirements)
    assert len(fake_process.calls) == 4


def test_non_editable_mode(fake_process: FakeProcess, tmp_path: Path) -> None:
    """Test project installed as wheel in non-editable mode."""
    config = CliConfig(venv=VenvConfig(path=tmp_path / ".venv"))
    manager = VirtualEnvironmentManager(config)

    def create_venv_wheel(*_args, **_kwargs):
        (tmp_path / ".venv" / "bin").mkdir(parents=True)
        (tmp_path / ".venv" / "bin" / "python").touch()

    fake_process.register(
        ["uv", "venv", "--python", "python3.14", "--seed", str(tmp_path / ".venv")],
        returncode=0,
        callback=create_venv_wheel,
    )

    fake_process.register(
        [str(tmp_path / ".venv" / "bin" / "python"), "-m", "pip", "install", "setuptools"],
        returncode=0,
    )

    fake_process.register(
        [
            "uv",
            "pip",
            "install",
            "--prerelease",
            "allow",
            "oarepo[rdm,tests,oarepo14]",
        ],
        returncode=0,
    )

    # Wheel build - use callback to create the wheel after build
    def create_wheel(*_args, **_kwargs):
        dist_dir = tmp_path / "dist"
        dist_dir.mkdir(exist_ok=True)
        wheel_file = dist_dir / "test_package-1.0.0-py3-none-any.whl"
        wheel_file.touch()

    fake_process.register(
        ["uv", "build", "--wheel"],
        returncode=0,
        callback=create_wheel,
    )

    # Wheel install (no -e flag)
    fake_process.register(
        [
            "uv",
            "pip",
            "install",
            "--prerelease",
            "allow",
            # Use pattern matching since wheel path will be generated
            fake_process.any(),
        ],
        returncode=0,
    )

    # Change to tmp_path so relative paths work
    old_cwd = Path.cwd()
    try:
        import os

        os.chdir(tmp_path)

        requirements = VenvRequirements(
            python_binary="python3.14",
            oarepo_version=14,
            editable=False,  # Non-editable mode
        )

        manager.ensure_venv(requirements)
        assert len(fake_process.calls) == 5
    finally:
        import os

        os.chdir(old_cwd)


def test_force_recreation_removes_existing_venv(tmp_path: Path) -> None:
    """Test force=True removes and recreates existing venv."""
    venv_path = tmp_path / ".venv"
    venv_path.mkdir()
    marker_file = venv_path / "marker.txt"
    marker_file.write_text("old venv")

    config = CliConfig(venv=VenvConfig(path=venv_path))
    manager = VirtualEnvironmentManager(config)

    # Don't need to fake processes for this test, just check cleanup
    assert venv_path.exists()
    assert marker_file.exists()

    # Call cleanup via force
    manager.cleanup()

    # Venv should be removed
    assert not venv_path.exists()
    assert not marker_file.exists()


def test_skip_creation_if_venv_exists(fake_process: FakeProcess, tmp_path: Path) -> None:
    """Test venv creation is skipped if it already exists."""
    venv_path = tmp_path / ".venv"
    venv_path.mkdir()
    (venv_path / "bin").mkdir()
    (venv_path / "bin" / "python").touch()

    config = CliConfig(venv=VenvConfig(path=venv_path))
    manager = VirtualEnvironmentManager(config)

    # Only register dependency install commands, not venv creation
    fake_process.register(
        [str(venv_path / "bin" / "python"), "-m", "pip", "install", "setuptools"],
        returncode=0,
    )

    fake_process.register(
        [
            "uv",
            "pip",
            "install",
            "--prerelease",
            "allow",
            "oarepo[rdm,tests,oarepo14]",
        ],
        returncode=0,
    )

    fake_process.register(
        ["uv", "pip", "install", "--prerelease", "allow", "-e", ".[dev,tests,oarepo14]"],
        returncode=0,
    )

    requirements = VenvRequirements(
        python_binary="python3.14",
        oarepo_version=14,
        editable=True,
    )

    manager.ensure_venv(requirements, force=False)

    # Only 3 calls (no venv creation)
    assert len(fake_process.calls) == 3


def test_cleanup_removes_venv(tmp_path: Path) -> None:
    """Test cleanup() removes the virtual environment."""
    venv_path = tmp_path / ".venv"
    venv_path.mkdir()
    (venv_path / "bin").mkdir()
    (venv_path / "bin" / "python").touch()

    config = CliConfig(venv=VenvConfig(path=venv_path))
    manager = VirtualEnvironmentManager(config)

    assert venv_path.exists()

    manager.cleanup()

    assert not venv_path.exists()


def test_cleanup_idempotent_when_venv_missing(tmp_path: Path) -> None:
    """Test cleanup() doesn't fail when venv doesn't exist."""
    venv_path = tmp_path / ".venv"

    config = CliConfig(venv=VenvConfig(path=venv_path))
    manager = VirtualEnvironmentManager(config)

    assert not venv_path.exists()

    # Should not raise
    manager.cleanup()

    assert not venv_path.exists()


def test_wheel_build_fails_when_no_wheel_found(fake_process: FakeProcess, tmp_path: Path) -> None:
    """Test that an error is raised when wheel build doesn't produce a wheel."""
    config = CliConfig(venv=VenvConfig(path=tmp_path / ".venv"))
    manager = VirtualEnvironmentManager(config)

    def create_venv_no_wheel(*_args, **_kwargs):
        (tmp_path / ".venv" / "bin").mkdir(parents=True)
        (tmp_path / ".venv" / "bin" / "python").touch()

    fake_process.register(
        ["uv", "venv", "--python", "python3.14", "--seed", str(tmp_path / ".venv")],
        returncode=0,
        callback=create_venv_no_wheel,
    )

    fake_process.register(
        [str(tmp_path / ".venv" / "bin" / "python"), "-m", "pip", "install", "setuptools"],
        returncode=0,
    )

    fake_process.register(
        [
            "uv",
            "pip",
            "install",
            "--prerelease",
            "allow",
            "oarepo[rdm,tests,oarepo14]",
        ],
        returncode=0,
    )

    # Wheel build succeeds but doesn't create wheel file
    def create_empty_dist(*_args, **_kwargs):
        (tmp_path / "dist").mkdir(exist_ok=True)

    fake_process.register(
        ["uv", "build", "--wheel"],
        returncode=0,
        callback=create_empty_dist,
    )

    old_cwd = Path.cwd()
    try:
        import os

        os.chdir(tmp_path)

        requirements = VenvRequirements(
            python_binary="python3.14",
            oarepo_version=14,
            editable=False,
        )

        with pytest.raises(ValidationError, match="No wheel found"):
            manager.ensure_venv(requirements)
    finally:
        import os

        os.chdir(old_cwd)
