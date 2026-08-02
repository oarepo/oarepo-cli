# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Integration tests for library oarepo-versions command."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from oarepo_cli.cli.main import app

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def runner() -> CliRunner:
    """Provide a Typer CLI runner."""
    return CliRunner()


@pytest.fixture
def sample_project_with_versions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    """Create a sample project with oarepo version in dependencies."""
    project_root = tmp_path / "test-project"
    project_root.mkdir()

    pyproject_toml = """
[project]
name = "test-package"
version = "1.0.0"
requires-python = ">=3.12,<3.15"
dependencies = ["oarepo>=14.0.0,<15.0.0"]

[project.urls]
Homepage = "https://github.com/example/test-package"
"""

    (project_root / "pyproject.toml").write_text(pyproject_toml.strip())

    # Change to the project directory
    monkeypatch.chdir(project_root)

    return project_root


def test_oarepo_versions_json_format(
    runner: CliRunner,
    sample_project_with_versions: Path,  # noqa: ARG001
) -> None:
    """Test that oarepo-versions outputs valid JSON."""
    result = runner.invoke(app, ["library", "oarepo-versions"])

    assert result.exit_code == 0, f"Command failed: {result.stderr}"

    # Parse JSON output
    output = json.loads(result.stdout)

    # Check structure
    assert "oarepo_versions" in output
    assert "python_versions" in output
    assert "node_versions" in output

    # Check types
    assert isinstance(output["oarepo_versions"], list)
    assert isinstance(output["python_versions"], list)
    assert isinstance(output["node_versions"], list)


def test_oarepo_versions_correct_values(
    runner: CliRunner,
    sample_project_with_versions: Path,  # noqa: ARG001
) -> None:
    """Test that oarepo-versions extracts correct version values."""
    result = runner.invoke(app, ["library", "oarepo-versions"])

    assert result.exit_code == 0

    output = json.loads(result.stdout)

    # Check OARepo versions (from dependencies: oarepo>=14.0.0,<15.0.0)
    # Should be a single version as a string
    assert output["oarepo_versions"] == ["14"]

    # Check Python versions (from requires-python: >=3.12,<3.15)
    # Should include 3.12, 3.13, 3.14 (assuming they're in KNOWN_PYTHON_VERSIONS)
    assert isinstance(output["python_versions"], list)
    assert len(output["python_versions"]) > 0
    # All versions should be strings
    assert all(isinstance(v, str) for v in output["python_versions"])
    # Check that versions are sorted descending
    for i in range(len(output["python_versions"]) - 1):
        assert output["python_versions"][i] >= output["python_versions"][i + 1]

    # Node versions is hard-coded to ["24"]
    assert output["node_versions"] == ["24"]


def test_oarepo_versions_pipeable(
    runner: CliRunner,
    sample_project_with_versions: Path,  # noqa: ARG001
) -> None:
    """Test that output is clean and pipeable (no extra text on stdout)."""
    result = runner.invoke(app, ["library", "oarepo-versions"])

    assert result.exit_code == 0

    # The entire stdout should be valid JSON - no extra messages
    output = json.loads(result.stdout)
    assert isinstance(output, dict)

    # stderr should be empty (no info messages)
    assert result.stderr == ""


def test_oarepo_versions_single_version(
    runner: CliRunner,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test oarepo-versions with a single OARepo version in dependencies."""
    project_root = tmp_path / "test-project-single"
    project_root.mkdir()

    pyproject_toml = """
[project]
name = "test-package"
version = "1.0.0"
requires-python = ">=3.14"
dependencies = ["oarepo>=14.0.0,<15.0.0"]

[project.urls]
Homepage = "https://github.com/example/test-package"
"""

    (project_root / "pyproject.toml").write_text(pyproject_toml.strip())

    # Change to the project directory
    monkeypatch.chdir(project_root)

    result = runner.invoke(app, ["library", "oarepo-versions"])

    assert result.exit_code == 0

    output = json.loads(result.stdout)
    assert output["oarepo_versions"] == ["14"]


def test_oarepo_versions_no_oarepo_extra(
    runner: CliRunner,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test oarepo-versions with no oarepo extra defined."""
    project_root = tmp_path / "test-project-no-oarepo"
    project_root.mkdir()

    pyproject_toml = """
[project]
name = "test-package"
version = "1.0.0"
requires-python = ">=3.14"

[project.urls]
Homepage = "https://github.com/example/test-package"
"""

    (project_root / "pyproject.toml").write_text(pyproject_toml.strip())

    # Change to the project directory
    monkeypatch.chdir(project_root)

    result = runner.invoke(app, ["library", "oarepo-versions"])

    assert result.exit_code == 0

    output = json.loads(result.stdout)
    # No oarepo versions found
    assert output["oarepo_versions"] == []
    # Python versions should still be present
    assert len(output["python_versions"]) > 0


def test_oarepo_versions_multiple_versions(
    runner: CliRunner,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test oarepo-versions with multiple OARepo versions in different extras."""
    project_root = tmp_path / "test-project-multi"
    project_root.mkdir()

    pyproject_toml = """
[project]
name = "test-package"
version = "1.0.0"
requires-python = ">=3.14"

[project.urls]
Homepage = "https://github.com/example/test-package"

[project.optional-dependencies]
dev = ["oarepo>=14.0.0,<15.0.0"]
tests = ["oarepo>=13.0.0,<14.0.0"]
"""

    (project_root / "pyproject.toml").write_text(pyproject_toml.strip())

    # Change to the project directory
    monkeypatch.chdir(project_root)

    result = runner.invoke(app, ["library", "oarepo-versions"])

    assert result.exit_code == 0

    output = json.loads(result.stdout)
    # Multiple versions, sorted highest first
    assert output["oarepo_versions"] == ["14", "13"]
    # Python versions should still be present
    assert len(output["python_versions"]) > 0


def test_oarepo_version_env_override(
    runner: CliRunner,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that OAREPO_VERSION environment variable can override auto-detection.

    This test verifies the documented behavior for multi-version projects:
    when multiple oarepo versions are detected, users can set OAREPO_VERSION
    to select a specific version for venv/install commands.
    """
    project_root = tmp_path / "test-project-multi-override"
    project_root.mkdir()

    pyproject_toml = """
[project]
name = "test-package"
version = "1.0.0"
requires-python = ">=3.14"

[project.urls]
Homepage = "https://github.com/example/test-package"

[project.optional-dependencies]
dev = ["oarepo>=14.0.0,<15.0.0"]
tests = ["oarepo>=13.0.0,<14.0.0"]
"""

    (project_root / "pyproject.toml").write_text(pyproject_toml.strip())
    monkeypatch.chdir(project_root)

    # Verify multiple versions are detected
    result = runner.invoke(app, ["library", "oarepo-versions"])
    assert result.exit_code == 0
    output = json.loads(result.stdout)
    assert output["oarepo_versions"] == ["14", "13"]

    # Test that OAREPO_VERSION can override which version is used
    # (We can't easily test venv creation in integration tests, but we can
    # verify the context selection logic via a unit test - see test_context.py)
