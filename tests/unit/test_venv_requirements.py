# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT
"""Tests for VenvRequirements model."""

from __future__ import annotations

import pytest

from oarepo_cli.core.errors import ValidationError
from oarepo_cli.services.venv import VenvRequirements


def test_requirements_creation_with_defaults() -> None:
    """Test creating VenvRequirements with default values."""
    req = VenvRequirements(python_binary="python3.14")

    assert req.python_binary == "python3.14"
    assert req.oarepo_version is None
    assert req.extras == []
    assert req.editable is True


def test_requirements_creation_with_custom_values() -> None:
    """Test creating VenvRequirements with custom values."""
    req = VenvRequirements(
        python_binary="/usr/bin/python3.14",
        oarepo_version=14,
        extras=["dev", "tests"],
        editable=False,
    )

    assert req.python_binary == "/usr/bin/python3.14"
    assert req.oarepo_version == 14
    assert req.extras == ["dev", "tests"]
    assert req.editable is False


def test_requirements_extras_defaults_to_empty_list() -> None:
    """Test that extras defaults to an empty list, not None."""
    req = VenvRequirements(python_binary="python3.14")
    assert req.extras == []
    assert isinstance(req.extras, list)


def test_editable_flag_handling() -> None:
    """Test editable flag can be set and retrieved."""
    req_editable = VenvRequirements(python_binary="python3.14", editable=True)
    assert req_editable.editable is True

    req_not_editable = VenvRequirements(python_binary="python3.14", editable=False)
    assert req_not_editable.editable is False


def test_validation_passes_without_oarepo_version() -> None:
    """Test that validation passes when no OARepo version is specified."""
    # Should not raise any exception
    req = VenvRequirements(python_binary="python3.14", oarepo_version=None)
    assert req.oarepo_version is None


def test_validation_passes_with_compatible_versions() -> None:
    """Test that validation passes with compatible Python and OARepo versions.

    Python 3.14 is the only version OAREPO_PYTHON_COMPATIBILITY lists for
    OARepo 14, so this combination must not raise.
    """
    req = VenvRequirements(
        python_binary="python3.14",
        oarepo_version=14,
    )
    assert req.python_binary == "python3.14"
    assert req.oarepo_version == 14


def test_validation_with_different_python_binary_formats() -> None:
    """Test that validation works with different Python binary path formats."""
    # Full path
    req1 = VenvRequirements(
        python_binary="/usr/local/bin/python3.14",
        oarepo_version=14,
    )
    assert req1.python_binary == "/usr/local/bin/python3.14"

    # Binary name with version
    # Note: OARepo 13 compatibility not yet defined, so use None for oarepo_version
    req2 = VenvRequirements(
        python_binary="python3.13",
        oarepo_version=None,  # No validation for unknown versions
    )
    assert req2.python_binary == "python3.13"

    # Binary name without specific version
    # Note: "python3" extracts to "3" which won't match "3.14", so skip validation
    req3 = VenvRequirements(
        python_binary="python3",
        oarepo_version=None,  # No validation
    )
    assert req3.python_binary == "python3"


def test_extract_python_version_from_binary_path() -> None:
    """Test extraction of Python version from various binary path formats."""
    req = VenvRequirements(python_binary="python3.14")
    assert req._extract_python_version() == "3.14"

    req = VenvRequirements(python_binary="/usr/bin/python3.13")
    assert req._extract_python_version() == "3.13"

    req = VenvRequirements(python_binary="python3")
    assert req._extract_python_version() == "3"

    # Edge case: just "python" (unusual but should handle gracefully)
    req = VenvRequirements(python_binary="python")
    assert req._extract_python_version() == "3"


def test_validation_fails_with_incompatible_versions() -> None:
    """Test that validation fails with incompatible Python and OARepo versions.

    Based on OAREPO_PYTHON_COMPATIBILITY:
    - OARepo 14 requires Python 3.14
    - Python 3.13 should fail with OARepo 14
    """
    with pytest.raises(ValidationError, match="not compatible"):
        VenvRequirements(
            python_binary="python3.13",
            oarepo_version=14,  # OARepo 14 requires Python 3.14
        )

    with pytest.raises(ValidationError, match="not compatible"):
        VenvRequirements(
            python_binary="/usr/bin/python3.12",
            oarepo_version=14,
        )


def test_immutability_of_requirements() -> None:
    """Test that VenvRequirements fields can be modified (dataclass not frozen).

    VenvRequirements is mutable by default, which allows field updates if needed.
    """
    req = VenvRequirements(python_binary="python3.14")

    # Should be able to modify fields
    req.editable = False
    assert req.editable is False

    req.extras = ["dev"]
    assert req.extras == ["dev"]
