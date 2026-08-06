# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Tests for oarepo_cli.core.context."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from oarepo_cli.core.config import CliConfig, VenvConfig
from oarepo_cli.core.context import ContextBuilder, discover_context, find_pyproject_toml
from oarepo_cli.core.errors import ConfigurationError, VersionMismatchError


def test_context_discovery_from_valid_project(tmp_path: Path) -> None:
    """Test context discovery from a valid project directory."""
    # Create a minimal pyproject.toml
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "test-project"
requires-python = ">=3.12,<3.15"
dependencies = ["oarepo>=14.0.0,<15.0.0"]
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
dependencies = ["oarepo>=14.0.0,<15.0.0"]
"""
    )
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()

    context = ContextBuilder().from_directory(tmp_path).validate()

    assert context.code_directories == [tmp_path / "src", tmp_path / "tests"]


def test_computed_properties_code_directories_uv_build_modules(tmp_path: Path) -> None:
    """code_directories resolves every [tool.uv.build-backend].module-name entry,
    matching a real repository's multi-module uv_build layout (tests/testrepo).
    """
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "test-repository"
requires-python = ">=3.12,<3.15"
dependencies = ["oarepo>=14.0.0,<15.0.0"]

[tool.uv.build-backend]
module-root = ""
module-name = ["common", "i18n", "ui"]
"""
    )
    (tmp_path / "common").mkdir()
    (tmp_path / "i18n").mkdir()
    (tmp_path / "ui").mkdir()
    (tmp_path / "tests").mkdir()

    context = ContextBuilder().from_directory(tmp_path).validate()

    assert context.code_directories == [
        tmp_path / "common",
        tmp_path / "i18n",
        tmp_path / "ui",
        tmp_path / "tests",
    ]


def test_computed_properties_code_directories_uv_build_modules_skips_missing(
    tmp_path: Path,
) -> None:
    """A declared module-name entry that doesn't exist on disk is silently skipped,
    rather than raising -- e.g. a module not yet scaffolded.
    """
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "test-repository"
requires-python = ">=3.12,<3.15"
dependencies = ["oarepo>=14.0.0,<15.0.0"]

[tool.uv.build-backend]
module-root = ""
module-name = ["common", "not-yet-created"]
"""
    )
    (tmp_path / "common").mkdir()

    context = ContextBuilder().from_directory(tmp_path).validate()

    assert context.code_directories == [tmp_path / "common"]


def test_computed_properties_code_directories_src_takes_priority_over_uv_build_modules(
    tmp_path: Path,
) -> None:
    """src/, when present, wins over [tool.uv.build-backend].module-name."""
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "test-repository"
requires-python = ">=3.12,<3.15"
dependencies = ["oarepo>=14.0.0,<15.0.0"]

[tool.uv.build-backend]
module-root = ""
module-name = ["common"]
"""
    )
    (tmp_path / "src").mkdir()
    (tmp_path / "common").mkdir()

    context = ContextBuilder().from_directory(tmp_path).validate()

    assert context.code_directories == [tmp_path / "src"]


def test_computed_properties_code_directories_uv_build_module_root_prefix(
    tmp_path: Path,
) -> None:
    """A non-empty module-root prefixes every module-name entry."""
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "test-repository"
requires-python = ">=3.12,<3.15"
dependencies = ["oarepo>=14.0.0,<15.0.0"]

[tool.uv.build-backend]
module-root = "packages"
module-name = ["common"]
"""
    )
    (tmp_path / "packages" / "common").mkdir(parents=True)

    context = ContextBuilder().from_directory(tmp_path).validate()

    assert context.code_directories == [tmp_path / "packages" / "common"]


def test_computed_properties_code_directories_package_layout(tmp_path: Path) -> None:
    """Test code_directories falls back to the package's own top-level directory."""
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "test-project"
requires-python = ">=3.12,<3.15"
dependencies = ["oarepo>=14.0.0,<15.0.0"]
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
dependencies = ["oarepo>=14.0.0,<15.0.0"]

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
dependencies = ["oarepo>=14.0.0,<15.0.0"]
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
dependencies = ["oarepo>=14.0.0,<15.0.0"]
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
dependencies = ["oarepo>=14.0.0,<15.0.0"]
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
dependencies = ["oarepo>=14.0.0,<15.0.0"]
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
dependencies = ["oarepo>=14.0.0,<15.0.0"]
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
dependencies = ["oarepo>=14.0.0,<15.0.0"]

[tool.oarepo-cli]
venv = { path = "/custom/venv" }
"""
    )

    # Use an existing Python binary
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


def test_validation_fails_for_incompatible_versions(tmp_path: Path) -> None:
    """ContextBuilder.validate() raises VersionMismatchError when the resolved
    Python binary's version isn't in OAREPO_PYTHON_COMPATIBILITY for the
    project's OARepo version (only "3.14" is compatible with OARepo 14).
    """
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "test-project"
requires-python = ">=3.12,<3.15"
dependencies = ["oarepo>=14.0.0,<15.0.0"]
"""
    )
    incompatible_python = Path(shutil.which("python3") or "/usr/bin/python3")

    with pytest.raises(VersionMismatchError):
        ContextBuilder().from_directory(tmp_path).with_python_override(incompatible_python).validate()


def test_context_is_immutable(tmp_path: Path) -> None:
    """Test that ProjectContext is frozen (immutable)."""
    from dataclasses import FrozenInstanceError

    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "test-project"
requires-python = ">=3.12,<3.15"
dependencies = ["oarepo>=14.0.0,<15.0.0"]
"""
    )

    context = ContextBuilder().from_directory(tmp_path).validate()

    with pytest.raises(FrozenInstanceError):
        context.oarepo_version = 15  # type: ignore


def test_discover_context_convenience_function(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test the discover_context convenience function."""
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "test-project"
requires-python = ">=3.12,<3.15"
dependencies = ["oarepo>=14.0.0,<15.0.0"]
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
dependencies = ["oarepo>=14.0.0,<15.0.0"]
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


def test_find_pyproject_toml_in_given_directory(tmp_path: Path) -> None:
    """find_pyproject_toml() finds a pyproject.toml directly in the given directory."""
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")

    assert find_pyproject_toml(tmp_path) == tmp_path / "pyproject.toml"


def test_find_pyproject_toml_searches_parents(tmp_path: Path) -> None:
    """find_pyproject_toml() searches upward through parent directories."""
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")
    subdir = tmp_path / "subdir" / "nested"
    subdir.mkdir(parents=True)

    assert find_pyproject_toml(subdir) == tmp_path / "pyproject.toml"


def test_find_pyproject_toml_returns_none_when_not_found(tmp_path: Path) -> None:
    """find_pyproject_toml() returns None (not an exception) when nothing is found."""
    subdir = tmp_path / "subdir"
    subdir.mkdir()

    assert find_pyproject_toml(subdir) is None


def test_find_pyproject_toml_defaults_to_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """find_pyproject_toml() defaults to searching from the current working directory."""
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")
    monkeypatch.chdir(tmp_path)

    assert find_pyproject_toml() == tmp_path / "pyproject.toml"


def test_multi_version_selects_highest_by_default(tmp_path: Path) -> None:
    """Test that when multiple oarepo versions are detected, the highest is selected."""
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "test-project"
requires-python = ">=3.14"

[project.optional-dependencies]
dev = ["oarepo>=14.0.0,<15.0.0"]
tests = ["oarepo>=13.0.0,<14.0.0"]
"""
    )

    context = ContextBuilder().from_directory(tmp_path).validate()

    # Should select the highest version (14)
    assert context.oarepo_version == 14


def test_python_autodetect_ignores_active_venv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Auto-detecting the Python binary must exclude the currently active venv.

    Running oarepo-cli from inside a project with its own venv activated
    (VIRTUAL_ENV/PATH pointing at that project's own .venv) must not resolve
    python_binary to that venv's own interpreter. That would be harmless for
    a plain `install` on an existing venv (uv sync just reuses it), but
    `repository upgrade` removes the venv *before* reinstalling -- so
    recreating it with a python_binary that lived inside the very venv just
    deleted would fail with "No interpreter found at path ...".
    """
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "test-project"
requires-python = ">=3.14,<3.15"
dependencies = ["oarepo>=14.0.0,<15.0.0"]
"""
    )

    # A fake "activated venv" interpreter that must NOT be picked...
    venv_bin = tmp_path / "project-venv" / "bin"
    venv_bin.mkdir(parents=True)
    venv_python = venv_bin / "python3.14"
    venv_python.write_text("#!/bin/sh\n")
    venv_python.chmod(0o755)

    # ...and a real "system" interpreter that should be picked instead.
    system_bin = tmp_path / "system-bin"
    system_bin.mkdir()
    system_python = system_bin / "python3.14"
    system_python.write_text("#!/bin/sh\n")
    system_python.chmod(0o755)

    monkeypatch.setenv("VIRTUAL_ENV", str(tmp_path / "project-venv"))
    monkeypatch.setenv("PATH", f"{venv_bin}:{system_bin}")

    context = ContextBuilder().from_directory(tmp_path).validate()

    assert context.python_binary == system_python


def test_oarepo_version_env_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that OAREPO_VERSION environment variable overrides auto-detection."""
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "test-project"
requires-python = ">=3.14"

[project.optional-dependencies]
dev = ["oarepo>=14.0.0,<15.0.0"]
tests = ["oarepo>=13.0.0,<14.0.0"]
"""
    )

    # Set environment variable to use version 13 instead of 14
    monkeypatch.setenv("OAREPO_VERSION", "13")

    context = ContextBuilder().from_directory(tmp_path).validate()

    # Should use version 13 from environment, not 14 from auto-detection
    assert context.oarepo_version == 13
