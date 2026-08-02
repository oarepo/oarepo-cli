# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Tests for oarepo_cli.core.context."""

from __future__ import annotations

from pathlib import Path

import pytest

from oarepo_cli.core.config import CliConfig, VenvConfig
from oarepo_cli.core.context import ContextBuilder, discover_context
from oarepo_cli.core.errors import ConfigurationError


def test_context_discovery_from_valid_project(tmp_path: Path) -> None:
    """Test context discovery from a valid project directory."""
    # Create a minimal pyproject.toml
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "test-project"
requires-python = ">=3.12,<3.15"

[tool.oarepo-cli]
oarepo = { version = 14 }
"""
    )

    context = ContextBuilder().from_directory(tmp_path).validate()

    assert context.root_directory == tmp_path
    assert context.pyproject_path == tmp_path / "pyproject.toml"
    assert context.venv_path == tmp_path / ".venv"
    assert context.oarepo_version == 14
    assert context.python_binary.exists()


def test_error_when_pyproject_missing(tmp_path: Path) -> None:
    """Test that ConfigurationError is raised when pyproject.toml is missing."""
    with pytest.raises(ConfigurationError) as exc_info:
        ContextBuilder().from_directory(tmp_path).validate()

    assert "pyproject.toml not found" in str(exc_info.value)


def test_error_when_no_pyproject_in_cwd_or_parents(tmp_path: Path) -> None:
    """Test error when no pyproject.toml exists in cwd or parents."""
    subdir = tmp_path / "subdir"
    subdir.mkdir()

    with pytest.raises(ConfigurationError) as exc_info:
        ContextBuilder().from_directory(subdir).validate()

    assert "pyproject.toml not found" in str(exc_info.value)


def test_computed_properties_code_directories_src_layout(tmp_path: Path) -> None:
    """Test code_directories prefers a top-level src/ directory, plus tests/."""
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "test-project"
requires-python = ">=3.12,<3.15"

[tool.oarepo-cli]
oarepo = { version = 14 }
"""
    )
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()

    context = ContextBuilder().from_directory(tmp_path).validate()

    assert context.code_directories == [tmp_path / "src", tmp_path / "tests"]


def test_computed_properties_code_directories_package_layout(tmp_path: Path) -> None:
    """Test code_directories falls back to the package's own top-level directory."""
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "test-project"
requires-python = ">=3.12,<3.15"

[tool.oarepo-cli]
oarepo = { version = 14 }
"""
    )
    (tmp_path / "test_project").mkdir()

    context = ContextBuilder().from_directory(tmp_path).validate()

    assert context.code_directories == [tmp_path / "test_project"]


def test_computed_properties_code_directories_hatch_wheel_packages(tmp_path: Path) -> None:
    """Test code_directories falls back to [tool.hatch.build.targets.wheel].packages."""
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "test-project"
requires-python = ">=3.12,<3.15"

[tool.oarepo-cli]
oarepo = { version = 14 }

[tool.hatch.build.targets.wheel]
packages = ["custom_pkg"]
"""
    )
    (tmp_path / "custom_pkg").mkdir()

    context = ContextBuilder().from_directory(tmp_path).validate()

    assert context.code_directories == [tmp_path / "custom_pkg"]


def test_computed_properties_code_directories_raises_when_not_found(tmp_path: Path) -> None:
    """Test code_directories raises ConfigurationError with no src/ or package dir."""
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "test-project"
requires-python = ">=3.12,<3.15"

[tool.oarepo-cli]
oarepo = { version = 14 }
"""
    )

    context = ContextBuilder().from_directory(tmp_path).validate()

    with pytest.raises(ConfigurationError, match="No src/ or test_project/ directory found"):
        _ = context.code_directories


def test_computed_properties_instance_path_exists(tmp_path: Path) -> None:
    """Test instance_path when instance directory exists."""
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "test-project"
requires-python = ">=3.12,<3.15"

[tool.oarepo-cli]
oarepo = { version = 14 }
"""
    )
    (tmp_path / "instance").mkdir()

    context = ContextBuilder().from_directory(tmp_path).validate()

    assert context.instance_path == tmp_path / "instance"


def test_computed_properties_instance_path_none(tmp_path: Path) -> None:
    """Test instance_path returns None when instance directory doesn't exist."""
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "test-project"
requires-python = ">=3.12,<3.15"

[tool.oarepo-cli]
oarepo = { version = 14 }
"""
    )

    context = ContextBuilder().from_directory(tmp_path).validate()

    assert context.instance_path is None


def test_computed_properties_assets_path_exists(tmp_path: Path) -> None:
    """Test assets_path when assets directory exists."""
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "test-project"
requires-python = ">=3.12,<3.15"

[tool.oarepo-cli]
oarepo = { version = 14 }
"""
    )
    (tmp_path / "assets").mkdir()

    context = ContextBuilder().from_directory(tmp_path).validate()

    assert context.assets_path == tmp_path / "assets"


def test_computed_properties_assets_path_none(tmp_path: Path) -> None:
    """Test assets_path returns None when assets directory doesn't exist."""
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "test-project"
requires-python = ">=3.12,<3.15"

[tool.oarepo-cli]
oarepo = { version = 14 }
"""
    )

    context = ContextBuilder().from_directory(tmp_path).validate()

    assert context.assets_path is None


def test_builder_pattern_with_overrides(tmp_path: Path) -> None:
    """Test builder pattern with various overrides."""
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "test-project"
requires-python = ">=3.12,<3.15"

[tool.oarepo-cli]
oarepo = { version = 14 }
venv = { path = "/custom/venv" }
"""
    )

    # Use an existing Python binary
    import shutil

    existing_python = Path(shutil.which("python3") or "python")

    custom_config = CliConfig(venv=VenvConfig(path=Path("/config/venv")))

    context = (
        ContextBuilder()
        .from_directory(tmp_path)
        .with_venv_path(Path("/builder/venv"))
        .with_python_override(existing_python)
        .with_oarepo_version(13)
        .with_config(custom_config)
        .validate()
    )

    # Overrides should take precedence
    assert context.venv_path == Path("/builder/venv")
    assert context.python_binary == existing_python
    assert context.oarepo_version == 13


def test_validation_fails_for_incompatible_versions() -> None:
    """Test validation fails when versions are incompatible (placeholder test)."""
    (tmp_path := Path("/tmp")).mkdir(exist_ok=True)
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "test-project"
requires-python = ">=3.12,<3.15"

[tool.oarepo-cli]
oarepo = { version = 14 }
"""
    )

    # Currently validate_compatibility is a placeholder, so this should pass
    context = ContextBuilder().from_directory(tmp_path).validate()
    assert context.oarepo_version == 14


def test_context_is_immutable() -> None:
    """Test that ProjectContext is frozen (immutable)."""
    from dataclasses import FrozenInstanceError

    (tmp_path := Path("/tmp")).mkdir(exist_ok=True)
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "test-project"
requires-python = ">=3.12,<3.15"

[tool.oarepo-cli]
oarepo = { version = 14 }
"""
    )

    context = ContextBuilder().from_directory(tmp_path).validate()

    with pytest.raises(FrozenInstanceError):
        context.oarepo_version = 15  # type: ignore


def test_discover_context_convenience_function(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test the discover_context convenience function."""
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "test-project"
requires-python = ">=3.12,<3.15"

[tool.oarepo-cli]
oarepo = { version = 14 }
"""
    )

    monkeypatch.chdir(tmp_path)
    context = discover_context()

    assert context.root_directory == tmp_path
    assert context.oarepo_version == 14


def test_context_discovery_searches_parent_directories(tmp_path: Path) -> None:
    """Test that context discovery searches upward for pyproject.toml."""
    # Create pyproject.toml in parent
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "test-project"
requires-python = ">=3.12,<3.15"

[tool.oarepo-cli]
oarepo = { version = 14 }
"""
    )

    # Create subdirectory
    subdir = tmp_path / "subdir" / "nested"
    subdir.mkdir(parents=True)

    # Change to subdirectory and discover
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.chdir(subdir)

    try:
        context = discover_context()
        assert context.root_directory == tmp_path
        assert context.pyproject_path == tmp_path / "pyproject.toml"
    finally:
        monkeypatch.undo()
