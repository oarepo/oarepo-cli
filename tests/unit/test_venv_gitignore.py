# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Unit tests for VirtualEnvironmentManager._ensure_uv_lock_gitignored."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

from oarepo_cli.core.config import CliConfig
from oarepo_cli.services.venv import VirtualEnvironmentManager


def test_gitignore_exists_with_uv_lock(tmp_path: Path) -> None:
    """Test that no changes are made when uv.lock is already in .gitignore."""
    # Create a pyproject.toml (required for CliConfig)
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[project]\nname = 'test'\nversion = '1.0.0'\n")

    # Create .gitignore with uv.lock already present
    gitignore = tmp_path / ".gitignore"
    original_content = "*.pyc\nuv.lock\n__pycache__/\n"
    gitignore.write_text(original_content)

    # Initialize VirtualEnvironmentManager
    config = CliConfig.from_pyproject(pyproject)
    manager = VirtualEnvironmentManager(config, tmp_path)

    # Call the method
    manager._ensure_uv_lock_gitignored(quiet=True)

    # Verify .gitignore was not modified
    assert gitignore.read_text() == original_content


def test_gitignore_exists_without_uv_lock(tmp_path: Path, capsys) -> None:
    """Test that uv.lock is added to .gitignore with warning when missing."""
    # Create a pyproject.toml (required for CliConfig)
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[project]\nname = 'test'\nversion = '1.0.0'\n")

    # Create .gitignore without uv.lock
    gitignore = tmp_path / ".gitignore"
    original_content = "*.pyc\n__pycache__/\n"
    gitignore.write_text(original_content)

    # Initialize VirtualEnvironmentManager
    config = CliConfig.from_pyproject(pyproject)
    manager = VirtualEnvironmentManager(config, tmp_path)

    # Call the method (not quiet - should print warning)
    manager._ensure_uv_lock_gitignored(quiet=False)

    # Verify uv.lock was added to .gitignore
    content = gitignore.read_text()
    assert "uv.lock" in content
    assert "# UV package management" in content

    # Verify warning was printed to stderr
    captured = capsys.readouterr()
    assert "Warning: uv.lock was not in .gitignore" in captured.err
    assert "Adding 'uv.lock' to .gitignore" in captured.err


def test_gitignore_exists_without_uv_lock_quiet(tmp_path: Path, capsys) -> None:
    """Test that uv.lock is added silently when quiet=True."""
    # Create a pyproject.toml (required for CliConfig)
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[project]\nname = 'test'\nversion = '1.0.0'\n")

    # Create .gitignore without uv.lock
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("*.pyc\n")

    # Initialize VirtualEnvironmentManager
    config = CliConfig.from_pyproject(pyproject)
    manager = VirtualEnvironmentManager(config, tmp_path)

    # Call the method with quiet=True
    manager._ensure_uv_lock_gitignored(quiet=True)

    # Verify uv.lock was added
    assert "uv.lock" in gitignore.read_text()

    # Verify no warning was printed
    captured = capsys.readouterr()
    assert captured.err == ""


def test_gitignore_not_exists(tmp_path: Path) -> None:
    """Test that .gitignore is created with uv.lock if it doesn't exist."""
    # Create a pyproject.toml (required for CliConfig)
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[project]\nname = 'test'\nversion = '1.0.0'\n")

    # Don't create .gitignore

    # Initialize VirtualEnvironmentManager
    config = CliConfig.from_pyproject(pyproject)
    manager = VirtualEnvironmentManager(config, tmp_path)

    # Call the method
    manager._ensure_uv_lock_gitignored(quiet=True)

    # Verify .gitignore was created with uv.lock
    gitignore = tmp_path / ".gitignore"
    assert gitignore.exists()
    assert "uv.lock" in gitignore.read_text()
