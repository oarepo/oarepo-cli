# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Integration test for library install alias command."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from oarepo_cli.cli.main import app

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def test_project(tmp_path: Path) -> Path:
    """Create a minimal test project."""
    # Create pyproject.toml
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[project]
name = "test-package"
version = "1.0.0"
requires-python = ">=3.14,<3.15"

[tool.oarepo-cli]
[tool.oarepo-cli.oarepo]
version = 14
"""
    )

    return tmp_path


def test_library_install_alias_works(
    test_project: Path,
    monkeypatch,
) -> None:
    """Test that 'library install' command works as alias for 'library venv'."""
    monkeypatch.chdir(test_project)

    # Verify venv doesn't exist
    assert not (test_project / ".venv").exists()

    runner = CliRunner()
    result = runner.invoke(app, ["library", "install", "--quiet"])

    # Command should succeed
    assert result.exit_code == 0

    # Verify venv was created
    assert (test_project / ".venv").exists()


def test_library_install_with_force_flag(
    test_project: Path,
    monkeypatch,
) -> None:
    """Test that 'library install --force' recreates venv."""
    monkeypatch.chdir(test_project)

    # Create a dummy venv
    venv_path = test_project / ".venv"
    venv_path.mkdir()
    marker_file = venv_path / "test_marker.txt"
    marker_file.write_text("old venv")

    # Verify marker exists
    assert marker_file.exists()

    runner = CliRunner()
    result = runner.invoke(app, ["library", "install", "--force", "--quiet"])

    # Command should succeed
    assert result.exit_code == 0

    # Verify venv still exists but marker is gone (venv was recreated)
    assert (test_project / ".venv").exists()
    assert not marker_file.exists()
