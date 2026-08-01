# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT
"""Virtual environment management for OARepo projects."""

from __future__ import annotations

from dataclasses import dataclass, field

from oarepo_cli.core.errors import ValidationError
from oarepo_cli.services.version_resolver import VersionResolver


@dataclass
class VenvRequirements:
    """Requirements for virtual environment setup.

    Defines what Python version, OARepo version, and extras are needed
    to create or verify a virtual environment for an OARepo project.
    """

    python_binary: str
    oarepo_version: int | None = None
    extras: list[str] = field(default_factory=list)
    editable: bool = True

    def __post_init__(self) -> None:
        """Validate requirements after initialization."""
        self._validate()

    def _validate(self) -> None:
        """Validate Python-OARepo compatibility.

        Raises:
            ValidationError: If Python version is incompatible with OARepo version.
        """
        if self.oarepo_version is None:
            # No OARepo version specified, nothing to validate
            return

        # Extract Python version from binary path (e.g., "python3.14" -> "3.14")
        python_version = self._extract_python_version()

        # Use VersionResolver to check compatibility
        resolver = VersionResolver()
        if not resolver.is_compatible(python_version, self.oarepo_version):
            msg = (
                f"Python {python_version} is not compatible with "
                f"OARepo version {self.oarepo_version}"
            )
            raise ValidationError(msg)

    def _extract_python_version(self) -> str:
        """Extract version string from Python binary path.

        Examples:
            "python3.14" -> "3.14"
            "/usr/bin/python3.13" -> "3.13"
            "python3" -> "3" (will be validated by VersionResolver)

        Returns:
            Version string extracted from binary name.
        """
        # Get the binary name without path
        binary_name = self.python_binary.split("/")[-1]

        # Remove "python" prefix if present
        if binary_name.startswith("python"):
            version_str = binary_name[6:]  # Remove "python" (6 chars)
            return version_str if version_str else "3"  # Default to "3" if just "python"

        # If no "python" prefix, return as-is (unusual case)
        return binary_name
