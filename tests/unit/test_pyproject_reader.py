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


def test_extracts_single_oarepo_version(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "test-package"

[project.optional-dependencies]
oarepo14 = ["oarepo>=14.0.0,<15.0.0"]
"""
    )

    data = pyproject_reader.PyProjectReader().read(tmp_path / "pyproject.toml")

    assert data.oarepo_versions == [14]


def test_extracts_multiple_oarepo_versions_sorted_and_deduplicated(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "test-package"

[project.optional-dependencies]
oarepo14 = ["oarepo>=14.0.0,<15.0.0"]
oarepo13 = ["oarepo>=13.0.0,<14.0.0"]
"""
    )

    data = pyproject_reader.PyProjectReader().read(tmp_path / "pyproject.toml")

    assert data.oarepo_versions == [13, 14]


def test_extracts_default_extras(tmp_path: Path) -> None:
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


def test_missing_file_raises_configuration_error(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError) as exc_info:
        pyproject_reader.PyProjectReader().read(tmp_path / "nonexistent.toml")

    assert "not found" in str(exc_info.value)


def test_invalid_toml_raises_configuration_error(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("invalid [[[[ syntax")

    with pytest.raises(ConfigurationError) as exc_info:
        pyproject_reader.PyProjectReader().read(tmp_path / "pyproject.toml")

    assert "Invalid TOML" in str(exc_info.value)
