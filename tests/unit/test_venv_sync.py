# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT
"""Unit tests for VirtualEnvironmentManager edge cases.

These tests cover specific edge cases and critical code paths that are
difficult or slow to test via integration tests. The bulk of venv
functionality is tested end-to-end in tests/integration/test_library_venv*.py.
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
rdm = []
search = []
""")

    # Create .gitignore
    gitignore = project / ".gitignore"
    gitignore.write_text("/.venv/\n")

    return project


def test_non_editable_uses_wheel_not_sync(
    mock_project_root: Path,
    fake_process: FakeProcess,
) -> None:
    """Test that non-editable install uses uv build + uv pip install, not uv sync.

    This is a critical different code path from the editable install (which uses
    uv sync). Integration tests primarily test editable mode, so this unit test
    ensures the wheel-based installation path works correctly.
    """
    venv_path = mock_project_root / ".venv"
    config = CliConfig(venv=VenvConfig(path=venv_path))
    manager = VirtualEnvironmentManager(config, project_root=mock_project_root)

    # Mock uv venv creation
    fake_process.register(["uv", "venv", "--python", "python3.14", "--seed", str(venv_path)])

    dist_dir = mock_project_root / "dist"
    wheel_path = dist_dir / "test_project-0.1.0-py3-none-any.whl"

    # Mock uv build - use callback to create the wheel file after build is called
    def create_wheel_callback(_process) -> None:
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
            f"{wheel_path}[dev,tests,oarepo14]",
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
                f"{wheel_path}[dev,tests,oarepo14]",
            ]
        )
        == 1
    )


def test_sync_editable_without_oarepo_version(
    mock_project_root: Path,
    fake_process: FakeProcess,
) -> None:
    """Test that uv sync works when oarepo_version is None.

    This edge case (no OARepo version extra) is important for non-OARepo
    projects that might use the CLI tooling. Integration tests typically
    use oarepo_version=14, so this unit test ensures the None case works.
    """
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
            "--prerelease",
            "allow",
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
                "--prerelease",
                "allow",
                "--extra",
                "dev",
                "--extra",
                "tests",
            ]
        )
        == 1
    )


def test_extras_list_format_each_extra_separate_flag(
    mock_project_root: Path,
    fake_process: FakeProcess,
) -> None:
    """Test that each extra is passed as a separate --extra flag.

    This is critical for correctness - uv expects '--extra dev --extra tests'
    not '--extra dev,tests'. This format requirement is an implementation detail
    but important enough to have a fast unit test to catch regressions.
    """
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
            "--prerelease",
            "allow",
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
