# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Version resolution for Python and OARepo dependencies."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

from packaging.specifiers import SpecifierSet
from packaging.version import Version

from oarepo_cli.configuration.constants import KNOWN_PYTHON_VERSIONS, OAREPO_PYTHON_COMPATIBILITY
from oarepo_cli.core.errors import VersionMismatchError
from oarepo_cli.services.process import get_system_path
from oarepo_cli.services.pyproject_reader import PyProjectReader


@dataclass(frozen=True)
class VersionInfo:
    """Resolved version information for a project.

    Attributes:
        oarepo_versions: List of OARepo major versions required (e.g., [13, 14])
        python_versions: List of compatible Python versions sorted descending (e.g., ["3.14", "3.13", "3.12"])
        node_versions: List of Node.js major versions required (always empty --
            Node.js version detection isn't implemented)

    """

    oarepo_versions: list[int]
    python_versions: list[str]
    node_versions: list[int]

    def __post_init__(self) -> None:
        """Sort python_versions in descending order."""
        # Sort in descending order (highest first)
        object.__setattr__(
            self,
            "python_versions",
            sorted(self.python_versions, key=lambda v: Version(v), reverse=True),
        )


class VersionResolver:
    """Resolves compatible Python and OARepo versions from pyproject.toml.

    This resolver:
    1. Parses requires-python constraint into discrete version list
    2. Checks system for available Python binaries
    3. Selects highest available Python version within constraints
    4. Validates OARepo-Python compatibility
    """

    def __init__(self, pyproject_reader: PyProjectReader | None = None) -> None:
        """Initialize the version resolver.

        Args:
            pyproject_reader: Optional PyProjectReader instance. If not provided,
                a new instance is created.

        """
        self._pyproject_reader = pyproject_reader or PyProjectReader()

    def resolve_from_pyproject(self, pyproject_path: Path) -> VersionInfo:
        """Resolve version information from a pyproject.toml file.

        Args:
            pyproject_path: Path to pyproject.toml

        Returns:
            VersionInfo with resolved Python and OARepo versions

        Raises:
            ConfigurationError: If pyproject.toml cannot be read
            VersionMismatchError: If no compatible Python version is found

        """
        data = self._pyproject_reader.read(pyproject_path)

        # Parse Python version constraint
        python_versions = self._parse_requires_python(data.requires_python)

        # Find available Python versions on the system
        available_versions = self._find_available_python(python_versions)

        if not available_versions:
            raise VersionMismatchError(
                f"No compatible Python version found for constraint {data.requires_python}. "
                f"Available versions checked: {KNOWN_PYTHON_VERSIONS}"
            )

        return VersionInfo(
            oarepo_versions=data.oarepo_versions,
            python_versions=available_versions,
            node_versions=[],  # Node.js version detection isn't implemented
        )

    def find_available_python(self, versions: list[str]) -> str:
        """Find the highest available Python version from the given list.

        Args:
            versions: List of Python version strings (e.g., ["3.12", "3.13", "3.14"])

        Returns:
            The highest available Python version string (e.g., "3.14")

        Raises:
            VersionMismatchError: If no version from the list is available

        """
        for version in versions:
            if self._is_python_available(version):
                return version

        raise VersionMismatchError(
            f"No Python version available from: {versions}. "
            "Please install one of these versions or adjust your requires-python constraint."
        )

    def is_compatible(self, python: str, oarepo: int) -> bool:
        """Check if a Python version is compatible with an OARepo version.

        Args:
            python: Python version string (e.g., "3.12")
            oarepo: OARepo major version (e.g., 14)

        Returns:
            True if the combination is compatible, False otherwise

        """
        try:
            self.validate_compatibility(python, oarepo)
            return True
        except VersionMismatchError:
            return False

    def validate_compatibility(self, python: str, oarepo: int) -> None:
        """Validate that a Python version is compatible with an OARepo version.

        Args:
            python: Python version string (e.g., "3.12" or "python3.12")
            oarepo: OARepo major version (e.g., 14)

        Raises:
            VersionMismatchError: If the combination is incompatible

        """
        if oarepo not in OAREPO_PYTHON_COMPATIBILITY:
            # Unknown OARepo version - we don't have compatibility data
            # This is not necessarily an error, just means we can't validate
            return

        # Extract version from binary name if needed (e.g., "python3.14" -> "3.14")
        python_version = self._extract_version_from_binary(python)

        compatible_versions = OAREPO_PYTHON_COMPATIBILITY[oarepo]
        if python_version not in compatible_versions:
            raise VersionMismatchError(
                f"Python {python_version} is not compatible with OARepo version {oarepo}. "
                f"Compatible Python versions: {', '.join(compatible_versions)}"
            )

    def _extract_version_from_binary(self, python: str) -> str:
        """Extract version string from Python binary path or name.

        Examples:
            "python3.14" -> "3.14"
            "/usr/bin/python3.13" -> "3.13"
            "3.14" -> "3.14" (already a version)
            "python3" -> "3"

        Args:
            python: Python binary path, name, or version string

        Returns:
            Version string extracted from input

        """
        # Get the binary name without path
        binary_name = python.rsplit("/", maxsplit=1)[-1]

        # If it doesn't start with "python", assume it's already a version
        if not binary_name.startswith("python"):
            return binary_name

        # Remove "python" prefix
        version_str = binary_name[6:]  # Remove "python" (6 chars)
        return version_str or "3"  # Default to "3" if just "python"

    def _parse_requires_python(self, constraint: str) -> list[str]:
        """Parse a requires-python constraint into a list of discrete versions.

        Uses the packaging library to parse the constraint and filter known versions.

        Supports constraints like:
        - ">=3.12,<3.15" → ["3.12", "3.13", "3.14"]
        - ">=3.11" → ["3.11", "3.12", "3.13", "3.14"]
        - "==3.12.*" → ["3.12"]

        Args:
            constraint: The requires-python value from pyproject.toml

        Returns:
            Sorted list of Python version strings matching the constraint

        """
        specifier = SpecifierSet(constraint)

        # Filter known versions against the specifier
        versions = []
        for ver in KNOWN_PYTHON_VERSIONS:
            if Version(ver) in specifier:
                versions.append(ver)

        return versions

    def _find_available_python(self, versions: list[str]) -> list[str]:
        """Find which Python versions from the list are available on the system.

        Args:
            versions: List of Python version strings to check

        Returns:
            List of available versions (may be empty if none found)

        """
        return [ver for ver in versions if self._is_python_available(ver)]

    def _is_python_available(self, version: str) -> bool:
        """Check if a specific Python version is available on the system.

        Checks for:
        - python{version} (e.g., python3.12)
        - python{major}{minor} (e.g., python312)
        - python{major}.{minor} (e.g., python3.12)

        Args:
            version: Python version string (e.g., "3.12")

        Returns:
            True if the Python binary is found in PATH (excluding any active venv)

        """
        major, minor = version.split(".")

        # Possible binary names to check
        candidates = [
            f"python{version}",  # python3.12
            f"python{major}{minor}",  # python312
            f"python{major}.{minor}",  # python3.12
        ]

        # Exclude any active venv from PATH (see process.get_system_path):
        # otherwise a version only present inside the currently-active venv
        # would be reported "available" even when nothing about to (re)create
        # that venv could actually use it.
        system_path = get_system_path()
        return any(shutil.which(candidate, path=system_path) is not None for candidate in candidates)
