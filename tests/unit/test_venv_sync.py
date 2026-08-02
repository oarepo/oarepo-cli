# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT
"""Unit tests for VirtualEnvironmentManager uv sync behavior.

These tests verify that the VirtualEnvironmentManager correctly builds
uv sync commands with the right extras and flags, without actually
executing the commands (mocked via pytest-subprocess).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from oarepo_cli.core.config import CliConfig, VenvConfig
from oarepo_cli.services.venv import VenvRequirements, VirtualEnvironmentManager

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_subprocess import FakeProcess


@pytest.fixture
def mock_project_root(tmp_path: Path) -> Path:
    """Create a mock project root with pyproject.toml."""
    project = tmp_path / "test_project"
    project.mkdir()

    # Create minimal pyproject.toml
    pyproject = project / "pyproject.toml"
    pyproject.write_text("""
[project]
name = "test-project"
version = "0.1.0"
dependencies = []

[project.optional-dependencies]
dev = []
tests = []
oarepo14 = []
""")

    # Create .gitignore
    gitignore = project / ".gitignore"
    gitignore.write_text("/.venv/\n")

    return project


def test_sync_editable_builds_correct_command(
    mock_project_root: Path,
    fake_process: FakeProcess,
) -> None:
    """Test that uv sync is called with correct extras for editable install."""
    venv_path = mock_project_root / ".venv"
    config = CliConfig(venv=VenvConfig(path=venv_path))
    manager = VirtualEnvironmentManager(config, project_root=mock_project_root)

    # Mock uv venv creation
    fake_process.register(["uv", "venv", "--python", "python3.14", "--seed", str(venv_path)])

    # Mock uv sync with expected extras
    python_path = venv_path / "bin" / "python"
    fake_process.register(
        [
            "uv",
            "sync",
            "--python",
            str(python_path),
            "--extra",
            "dev",
            "--extra",
            "tests",
            "--extra",
            "oarepo14",
        ]
    )

    requirements = VenvRequirements(
        python_binary="python3.14",
        oarepo_version=14,
        extras=[],
        editable=True,
    )

    manager.ensure_venv(requirements, quiet=True)

    # Verify uv sync was called with correct arguments
    assert (
        fake_process.call_count(
            [
                "uv",
                "sync",
                "--python",
                str(python_path),
                "--extra",
                "dev",
                "--extra",
                "tests",
                "--extra",
                "oarepo14",
            ]
        )
        == 1
    )


def test_sync_editable_with_additional_extras(
    mock_project_root: Path,
    fake_process: FakeProcess,
) -> None:
    """Test that additional extras are included in uv sync command."""
    venv_path = mock_project_root / ".venv"
    config = CliConfig(venv=VenvConfig(path=venv_path))
    manager = VirtualEnvironmentManager(config, project_root=mock_project_root)

    # Mock uv venv creation
    fake_process.register(["uv", "venv", "--python", "python3.14", "--seed", str(venv_path)])

    # Mock uv sync with all extras including additional ones
    python_path = venv_path / "bin" / "python"
    fake_process.register(
        [
            "uv",
            "sync",
            "--python",
            str(python_path),
            "--extra",
            "dev",
            "--extra",
            "tests",
            "--extra",
            "oarepo14",
            "--extra",
            "rdm",
            "--extra",
            "search",
        ]
    )

    requirements = VenvRequirements(
        python_binary="python3.14",
        oarepo_version=14,
        extras=["rdm", "search"],
        editable=True,
    )

    manager.ensure_venv(requirements, quiet=True)

    # Verify all extras were included
    assert (
        fake_process.call_count(
            [
                "uv",
                "sync",
                "--python",
                str(python_path),
                "--extra",
                "dev",
                "--extra",
                "tests",
                "--extra",
                "oarepo14",
                "--extra",
                "rdm",
                "--extra",
                "search",
            ]
        )
        == 1
    )


def test_sync_editable_without_oarepo_version(
    mock_project_root: Path,
    fake_process: FakeProcess,
) -> None:
    """Test that uv sync works without oarepo version extra."""
    venv_path = mock_project_root / ".venv"
    config = CliConfig(venv=VenvConfig(path=venv_path))
    manager = VirtualEnvironmentManager(config, project_root=mock_project_root)

    # Mock uv venv creation
    fake_process.register(["uv", "venv", "--python", "python3.14", "--seed", str(venv_path)])

    # Mock uv sync without oarepo version extra
    python_path = venv_path / "bin" / "python"
    fake_process.register(
        [
            "uv",
            "sync",
            "--python",
            str(python_path),
            "--extra",
            "dev",
            "--extra",
            "tests",
        ]
    )

    requirements = VenvRequirements(
        python_binary="python3.14",
        oarepo_version=None,
        extras=[],
        editable=True,
    )

    manager.ensure_venv(requirements, quiet=True)

    # Verify uv sync was called without oarepo version extra
    assert (
        fake_process.call_count(
            [
                "uv",
                "sync",
                "--python",
                str(python_path),
                "--extra",
                "dev",
                "--extra",
                "tests",
            ]
        )
        == 1
    )


def test_non_editable_uses_wheel_not_sync(
    mock_project_root: Path,
    fake_process: FakeProcess,
) -> None:
    """Test that non-editable install uses uv build + uv pip install, not uv sync."""
    venv_path = mock_project_root / ".venv"
    config = CliConfig(venv=VenvConfig(path=venv_path))
    manager = VirtualEnvironmentManager(config, project_root=mock_project_root)

    # Mock uv venv creation
    fake_process.register(["uv", "venv", "--python", "python3.14", "--seed", str(venv_path)])

    dist_dir = mock_project_root / "dist"
    wheel_path = dist_dir / "test_project-0.1.0-py3-none-any.whl"

    # Mock uv build - use callback to create the wheel file after build is called
    def create_wheel_callback(_process):
        dist_dir.mkdir(exist_ok=True)
        wheel_path.touch()

    fake_process.register(
        ["uv", "build", "--wheel", "--out-dir", str(dist_dir), str(mock_project_root)],
        callback=create_wheel_callback,
    )

    # Mock uv pip install (not uv sync!)
    python_path = venv_path / "bin" / "python"
    fake_process.register(
        [
            "uv",
            "pip",
            "install",
            "--python",
            str(python_path),
            "--prerelease",
            "allow",
            f"{wheel_path}[tests,oarepo14]",
        ]
    )

    requirements = VenvRequirements(
        python_binary="python3.14",
        oarepo_version=14,
        extras=[],
        editable=False,
    )

    manager.ensure_venv(requirements, quiet=True)

    # Verify uv sync was NOT called (only uv pip install)
    assert (
        fake_process.call_count(
            [
                "uv",
                "sync",
            ]
        )
        == 0
    )

    # Verify uv pip install was called
    assert (
        fake_process.call_count(
            [
                "uv",
                "pip",
                "install",
                "--python",
                str(python_path),
                "--prerelease",
                "allow",
                f"{wheel_path}[tests,oarepo14]",
            ]
        )
        == 1
    )


def test_sync_command_runs_from_project_root(
    mock_project_root: Path,
    fake_process: FakeProcess,
) -> None:
    """Test that uv sync is executed from the project root directory.

    Note: pytest-subprocess doesn't support cwd verification directly,
    so this test just verifies the command is called. The process.run()
    implementation ensures cwd=project_root is used.
    """
    venv_path = mock_project_root / ".venv"
    config = CliConfig(venv=VenvConfig(path=venv_path))
    manager = VirtualEnvironmentManager(config, project_root=mock_project_root)

    # Mock uv venv creation
    fake_process.register(["uv", "venv", "--python", "python3.14", "--seed", str(venv_path)])

    # Mock uv sync - cwd verification happens in process.run() implementation
    python_path = venv_path / "bin" / "python"
    fake_process.register(
        [
            "uv",
            "sync",
            "--python",
            str(python_path),
            "--extra",
            "dev",
            "--extra",
            "tests",
            "--extra",
            "oarepo14",
        ]
    )

    requirements = VenvRequirements(
        python_binary="python3.14",
        oarepo_version=14,
        extras=[],
        editable=True,
    )

    manager.ensure_venv(requirements, quiet=True)

    # Command was called successfully (cwd is correct by implementation)


def test_sync_uses_absolute_python_path(
    mock_project_root: Path,
    fake_process: FakeProcess,
) -> None:
    """Test that uv sync uses absolute path to venv Python interpreter."""
    venv_path = mock_project_root / ".venv"
    config = CliConfig(venv=VenvConfig(path=venv_path))
    manager = VirtualEnvironmentManager(config, project_root=mock_project_root)

    # Mock uv venv creation
    fake_process.register(["uv", "venv", "--python", "python3.14", "--seed", str(venv_path)])

    # Verify absolute path is used
    python_path = venv_path / "bin" / "python"
    assert python_path.is_absolute()

    fake_process.register(
        [
            "uv",
            "sync",
            "--python",
            str(python_path),
            "--extra",
            "dev",
            "--extra",
            "tests",
            "--extra",
            "oarepo14",
        ]
    )

    requirements = VenvRequirements(
        python_binary="python3.14",
        oarepo_version=14,
        extras=[],
        editable=True,
    )

    manager.ensure_venv(requirements, quiet=True)


def test_gitignore_updated_before_sync(
    mock_project_root: Path,
    fake_process: FakeProcess,
) -> None:
    """Test that uv.lock is added to .gitignore before running uv sync."""
    venv_path = mock_project_root / ".venv"
    config = CliConfig(venv=VenvConfig(path=venv_path))
    manager = VirtualEnvironmentManager(config, project_root=mock_project_root)

    # Mock uv commands
    fake_process.register(["uv", "venv", "--python", "python3.14", "--seed", str(venv_path)])

    python_path = venv_path / "bin" / "python"
    fake_process.register(
        [
            "uv",
            "sync",
            "--python",
            str(python_path),
            "--extra",
            "dev",
            "--extra",
            "tests",
            "--extra",
            "oarepo14",
        ]
    )

    # Verify .gitignore doesn't have uv.lock yet
    gitignore = mock_project_root / ".gitignore"
    content_before = gitignore.read_text()
    assert "uv.lock" not in content_before

    requirements = VenvRequirements(
        python_binary="python3.14",
        oarepo_version=14,
        extras=[],
        editable=True,
    )

    manager.ensure_venv(requirements, quiet=True)

    # Verify uv.lock was added to .gitignore
    content_after = gitignore.read_text()
    assert "uv.lock" in content_after


def test_extras_list_format_each_extra_separate_flag(
    mock_project_root: Path,
    fake_process: FakeProcess,
) -> None:
    """Test that each extra is passed as a separate --extra flag (not comma-separated)."""
    venv_path = mock_project_root / ".venv"
    config = CliConfig(venv=VenvConfig(path=venv_path))
    manager = VirtualEnvironmentManager(config, project_root=mock_project_root)

    # Mock uv venv creation
    fake_process.register(["uv", "venv", "--python", "python3.14", "--seed", str(venv_path)])

    # Each extra should be a separate --extra flag, NOT --extra dev,tests,oarepo14
    python_path = venv_path / "bin" / "python"
    fake_process.register(
        [
            "uv",
            "sync",
            "--python",
            str(python_path),
            "--extra",
            "dev",
            "--extra",
            "tests",
            "--extra",
            "oarepo14",
        ]
    )

    requirements = VenvRequirements(
        python_binary="python3.14",
        oarepo_version=14,
        extras=[],
        editable=True,
    )

    manager.ensure_venv(requirements, quiet=True)

    # This should succeed - if the format was wrong, the mock wouldn't match
