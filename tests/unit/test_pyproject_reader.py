# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Tests for oarepo_cli.services.pyproject_reader.

PyProjectReader has exactly one real implementation (tomllib against a real
file), so it's exercised directly against real pyproject.toml files written
under tmp_path rather than through mocks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from oarepo_cli.core.errors import ConfigurationError
from oarepo_cli.services import pyproject_reader

if TYPE_CHECKING:
    from pathlib import Path


def test_parses_minimal_project(tmp_path: Path) -> None:
    """A pyproject.toml with only [project].name/requires-python parses with empty defaults."""
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "test-package"
requires-python = ">=3.12,<3.15"
"""
    )

    data = pyproject_reader.PyProjectReader().read(tmp_path / "pyproject.toml")

    assert data.name == "test-package"
    assert data.requires_python == ">=3.12,<3.15"
    assert data.dependencies == []
    assert data.optional_dependencies == {}
    assert data.oarepo_versions == []
    assert data.default_extras == []


def test_parses_homepage_and_dependencies(tmp_path: Path) -> None:
    """[project.urls].Homepage and [project].dependencies are both read correctly."""
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "test-package"
requires-python = ">=3.14,<3.15"
dependencies = ["click>=8.0"]

[project.urls]
Homepage = "https://example.com"
"""
    )

    data = pyproject_reader.PyProjectReader().read(tmp_path / "pyproject.toml")

    assert data.homepage == "https://example.com"
    assert data.dependencies == ["click>=8.0"]


def test_extracts_single_oarepo_version_from_dependencies(tmp_path: Path) -> None:
    """Test extraction from main dependencies."""
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "test-package"
dependencies = ["oarepo>=14.0.0,<15.0.0"]
"""
    )

    data = pyproject_reader.PyProjectReader().read(tmp_path / "pyproject.toml")

    assert data.oarepo_versions == [14]


def test_extracts_multiple_oarepo_versions_sorted_highest_first(tmp_path: Path) -> None:
    """Test that multiple versions are extracted from different extras and sorted highest-first."""
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "test-package"

[project.optional-dependencies]
dev = ["oarepo>=14.0.0,<15.0.0"]
tests = ["oarepo>=13.0.0,<14.0.0"]
"""
    )

    data = pyproject_reader.PyProjectReader().read(tmp_path / "pyproject.toml")

    # Multiple versions, sorted highest first
    assert data.oarepo_versions == [14, 13]


def test_extracts_oarepo_version_from_optional_dependencies(tmp_path: Path) -> None:
    """Test extraction from optional dependencies (dev/tests extras)."""
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "test-package"

[project.optional-dependencies]
dev = ["oarepo>=14.0.0,<15.0.0", "pytest>=7.0"]
"""
    )

    data = pyproject_reader.PyProjectReader().read(tmp_path / "pyproject.toml")

    assert data.oarepo_versions == [14]


def test_extracts_exact_version_pin(tmp_path: Path) -> None:
    """Test extraction from exact version pins (oarepo==14.0.5)."""
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "test-package"
dependencies = ["oarepo==14.0.5"]
"""
    )

    data = pyproject_reader.PyProjectReader().read(tmp_path / "pyproject.toml")

    assert data.oarepo_versions == [14]


def test_deduplicates_same_version_across_extras(tmp_path: Path) -> None:
    """Test that the same version in multiple extras appears only once."""
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "test-package"
dependencies = ["oarepo>=14.0.0,<15.0.0"]

[project.optional-dependencies]
dev = ["oarepo>=14.0.0,<15.0.0"]
"""
    )

    data = pyproject_reader.PyProjectReader().read(tmp_path / "pyproject.toml")

    # Same version should only appear once
    assert data.oarepo_versions == [14]


def test_oarepo_version_with_extras_marker(tmp_path: Path) -> None:
    """Test extraction from oarepo dependencies with extras (e.g., oarepo[search])."""
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "test-package"
dependencies = ["oarepo[search]>=14.0.0,<15.0.0"]
"""
    )

    data = pyproject_reader.PyProjectReader().read(tmp_path / "pyproject.toml")

    assert data.oarepo_versions == [14]


def test_ignores_invalid_dependency_specifier(tmp_path: Path) -> None:
    """Test that invalid specifiers are gracefully ignored."""
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "test-package"
dependencies = [
    "oarepo>=14.0.0,<15.0.0",
    "invalid [[[[ syntax"
]
"""
    )

    data = pyproject_reader.PyProjectReader().read(tmp_path / "pyproject.toml")

    # Should still extract valid oarepo version, ignoring invalid spec
    assert data.oarepo_versions == [14]


def test_warns_about_deprecated_tool_config(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that [tool.oarepo-cli].oarepo.version triggers a deprecation warning."""
    import logging

    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "test-package"
dependencies = ["oarepo>=14.0.0,<15.0.0"]

[tool.oarepo-cli.oarepo]
version = 14
"""
    )

    with caplog.at_level(logging.WARNING):
        data = pyproject_reader.PyProjectReader().read(tmp_path / "pyproject.toml")

        # Should extract from dependencies, not from tool config
        assert data.oarepo_versions == [14]

        # Should have logged a warning about deprecated config
        assert any(
            "[tool.oarepo-cli].oarepo.version" in record.message and "deprecated" in record.message
            for record in caplog.records
        )


def test_extracts_default_extras(tmp_path: Path) -> None:
    """[tool.oarepo].default_extras is read into PyProjectData.default_extras."""
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "test-package"

[tool.oarepo]
default_extras = ["dev", "tests"]
"""
    )

    data = pyproject_reader.PyProjectReader().read(tmp_path / "pyproject.toml")

    assert data.default_extras == ["dev", "tests"]


def test_extracts_uv_build_module_names_and_root(tmp_path: Path) -> None:
    """[tool.uv.build-backend]'s module-name/module-root are both read correctly."""
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "test-repository"

[tool.uv.build-backend]
module-root = ""
module-name = ["common", "i18n", "ui"]
"""
    )

    data = pyproject_reader.PyProjectReader().read(tmp_path / "pyproject.toml")

    assert data.uv_build_module_names == ["common", "i18n", "ui"]
    assert data.uv_build_module_root == ""


def test_uv_build_module_names_and_root_default_when_absent(tmp_path: Path) -> None:
    """Without a [tool.uv.build-backend] section, module names/root default to empty."""
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "test-package"
"""
    )

    data = pyproject_reader.PyProjectReader().read(tmp_path / "pyproject.toml")

    assert data.uv_build_module_names == []
    assert data.uv_build_module_root == ""


def test_missing_file_raises_configuration_error(tmp_path: Path) -> None:
    """Reading a pyproject.toml that doesn't exist raises ConfigurationError."""
    with pytest.raises(ConfigurationError) as exc_info:
        pyproject_reader.PyProjectReader().read(tmp_path / "nonexistent.toml")

    assert "not found" in str(exc_info.value)


def test_invalid_toml_raises_configuration_error(tmp_path: Path) -> None:
    """Malformed TOML raises ConfigurationError instead of a raw tomllib exception."""
    (tmp_path / "pyproject.toml").write_text("invalid [[[[ syntax")

    with pytest.raises(ConfigurationError) as exc_info:
        pyproject_reader.PyProjectReader().read(tmp_path / "pyproject.toml")

    assert "Invalid TOML" in str(exc_info.value)
