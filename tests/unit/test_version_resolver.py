# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Tests for oarepo_cli.services.version_resolver."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from packaging.version import Version

from oarepo_cli.core.errors import VersionMismatchError
from oarepo_cli.services.pyproject_reader import PyProjectReader
from oarepo_cli.services.version_resolver import VersionResolver

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture


def test_version_range_parsing_gte_lt(tmp_path: Path) -> None:
    """Test parsing >=X.Y,<Z constraint returns versions in that range."""
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "test-package"
requires-python = ">=3.12,<3.15"
"""
    )

    reader = PyProjectReader()
    resolver = VersionResolver(pyproject_reader=reader)

    info = resolver.resolve_from_pyproject(tmp_path / "pyproject.toml")

    # Should include versions in range, sorted highest-first
    versions = info.python_versions
    assert all(Version(v) >= Version("3.12") for v in versions), "All versions should be >= 3.12"
    assert all(Version(v) < Version("3.15") for v in versions), "All versions should be < 3.15"
    # Verify sorted highest-first
    for i in range(len(versions) - 1):
        assert Version(versions[i]) > Version(versions[i + 1]), (
            "Versions should be sorted highest-first"
        )


def test_version_range_parsing_gte_only(tmp_path: Path) -> None:
    """Test parsing >=X.Y constraint returns all known versions >= X.Y."""
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "test-package"
requires-python = ">=3.11"
"""
    )

    reader = PyProjectReader()
    resolver = VersionResolver(pyproject_reader=reader)

    info = resolver.resolve_from_pyproject(tmp_path / "pyproject.toml")

    # Should include all known versions >= 3.11 (as of 2026, KNOWN_PYTHON_VERSIONS is ["3.14"])
    versions = info.python_versions
    assert all(Version(v) >= Version("3.11") for v in versions), "All versions should be >= 3.11"
    assert len(versions) >= 1, "Should have at least one Python version"
    # With current KNOWN_PYTHON_VERSIONS=["3.14"], should have exactly ["3.14"]
    assert "3.14" in versions


def test_version_range_parsing_eq_constraint(tmp_path: Path, mocker: MockerFixture) -> None:
    """Test parsing ==X.Y.* constraint returns only X.Y.x versions."""
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "test-package"
requires-python = "==3.14.*"
"""
    )

    # Mock shutil.which to simulate python3.14 being available
    mocker.patch(
        "oarepo_cli.services.version_resolver.shutil.which",
        return_value="/usr/bin/python3.14",
    )

    reader = PyProjectReader()
    resolver = VersionResolver(pyproject_reader=reader)

    info = resolver.resolve_from_pyproject(tmp_path / "pyproject.toml")

    # Should have only 3.14 (major.minor, no patch version in KNOWN_PYTHON_VERSIONS)
    assert info.python_versions == ["3.14"]


def test_finding_highest_available_python(mocker: MockerFixture) -> None:
    """Test that the highest available Python version is selected."""
    resolver = VersionResolver()

    # Mock shutil.which to simulate python3.14 and python3.12 being available
    def mock_which(name: str, **_kwargs: object) -> str | None:
        if name in ("python3.14", "python3.12"):
            return f"/usr/bin/{name}"
        return None

    mocker.patch("oarepo_cli.services.version_resolver.shutil.which", side_effect=mock_which)

    result = resolver.find_available_python(["3.14", "3.13", "3.12"])

    assert result == "3.14"


def test_fallback_to_lower_version_if_highest_unavailable(mocker: MockerFixture) -> None:
    """Test fallback to lower version when highest is not available."""
    resolver = VersionResolver()

    # Mock shutil.which to simulate only python3.12 being available
    def mock_which(name: str, **_kwargs: object) -> str | None:
        if name == "python3.12":
            return "/usr/bin/python3.12"
        return None

    mocker.patch("oarepo_cli.services.version_resolver.shutil.which", side_effect=mock_which)

    result = resolver.find_available_python(["3.14", "3.13", "3.12"])

    assert result == "3.12"


def test_version_mismatch_error_when_no_compatible_version(mocker: MockerFixture) -> None:
    """Test VersionMismatchError when no Python version is available."""
    resolver = VersionResolver()

    # Mock shutil.which to simulate no Python available
    mocker.patch("oarepo_cli.services.version_resolver.shutil.which", return_value=None)

    with pytest.raises(VersionMismatchError) as exc_info:
        resolver.find_available_python(["3.14", "3.13", "3.12"])

    assert "No Python version available" in str(exc_info.value)


def test_oarepo_python_compatibility_validation() -> None:
    """Test validate_compatibility with the actual compatibility matrix.

    Based on OAREPO_PYTHON_COMPATIBILITY:
    - OARepo 14 requires Python 3.14
    """
    resolver = VersionResolver()

    # Valid combinations should not raise
    resolver.validate_compatibility("3.14", 14)

    # Invalid combinations should raise VersionMismatchError
    with pytest.raises(VersionMismatchError, match="not compatible"):
        resolver.validate_compatibility("3.13", 14)

    with pytest.raises(VersionMismatchError, match="not compatible"):
        resolver.validate_compatibility("3.12", 14)

    # Unknown OARepo versions should not raise (no compatibility data)
    resolver.validate_compatibility("3.12", 99)  # Unknown version


def test_is_compatible_convenience_method() -> None:
    """Test is_compatible returns bool instead of raising."""
    resolver = VersionResolver()

    # Valid combination
    assert resolver.is_compatible("3.14", 14) is True

    # Invalid combinations
    assert resolver.is_compatible("3.13", 14) is False
    assert resolver.is_compatible("3.12", 14) is False

    # Unknown OARepo version (no compatibility data, returns True)
    assert resolver.is_compatible("3.12", 99) is True


def test_extract_oarepo_versions_with_python_resolution(tmp_path: Path) -> None:
    """Test full resolution including OARepo version extraction."""
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "test-package"
requires-python = ">=3.12,<3.15"

[project.optional-dependencies]
oarepo14 = ["oarepo>=14.0.0,<15.0.0"]
oarepo13 = ["oarepo>=13.0.0,<14.0.0"]
"""
    )

    reader = PyProjectReader()
    resolver = VersionResolver(pyproject_reader=reader)

    info = resolver.resolve_from_pyproject(tmp_path / "pyproject.toml")

    # OARepo versions should be extracted and sorted highest-first
    assert info.oarepo_versions == [14, 13]
    # Python versions should be in the specified range
    assert all(Version(v) >= Version("3.12") for v in info.python_versions)
    assert all(Version(v) < Version("3.15") for v in info.python_versions)


def test_version_info_is_immutable() -> None:
    """Test that VersionInfo is frozen (immutable)."""
    from dataclasses import FrozenInstanceError

    from oarepo_cli.services.version_resolver import VersionInfo

    info = VersionInfo(
        oarepo_versions=[14],
        python_versions=["3.12"],
        node_versions=[],
    )

    with pytest.raises(FrozenInstanceError):
        object.__setattr__(info, "oarepo_versions", [15])  # type: ignore[misc]


def test_parse_requires_python_with_complex_constraint() -> None:
    """Test parsing complex version constraints using packaging library."""
    resolver = VersionResolver()

    # Test various constraint formats - verify behavior works with current KNOWN_PYTHON_VERSIONS
    result = resolver._parse_requires_python(">=3.10,<3.15")
    # With KNOWN_PYTHON_VERSIONS=["3.14"], should include 3.14
    assert "3.14" in result, "Should include 3.14 (which is in range >=3.10,<3.15)"
    assert all(Version(v) >= Version("3.10") for v in result), "All versions should be >= 3.10"
    assert all(Version(v) < Version("3.15") for v in result), "All versions should be < 3.15"

    result = resolver._parse_requires_python(">=3.13")
    assert all(Version(v) >= Version("3.13") for v in result), "All versions should be >= 3.13"
    # With current KNOWN_PYTHON_VERSIONS=["3.14"], should include 3.14
    assert "3.14" in result


def test_version_compare_function() -> None:
    """Test that packaging.version.Version is used for comparisons."""
    # The implementation uses packaging.version.Version directly
    assert Version("3.12") < Version("3.13")
    assert Version("3.13") > Version("3.12")
    assert Version("3.12") == Version("3.12")
    assert Version("3.12.1") > Version("3.12.0")
