# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Version resolution for Python and OARepo dependencies."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

from packaging.specifiers import SpecifierSet
from packaging.version import Version

from oarepo_cli.configuration.constants import KNOWN_NODE_VERSIONS, KNOWN_PYTHON_VERSIONS, OAREPO_PYTHON_COMPATIBILITY
from oarepo_cli.core.errors import VersionMismatchError
from oarepo_cli.services import process
from oarepo_cli.services.process import ProcessOutputMode, get_system_path
from oarepo_cli.services.pyproject_reader import PyProjectReader


@dataclass(frozen=True)
class VersionInfo:
    """Resolved version information for a project.

    Attributes:
        oarepo_versions: List of OARepo major versions required (e.g., [13, 14])
        python_versions: List of compatible Python versions sorted descending (e.g., ["3.14", "3.13", "3.12"])
        node_versions: List of Node.js major versions available on the system,
            sorted descending (e.g., ["24", "22", "20"])

    """

    oarepo_versions: list[int]
    python_versions: list[str]
    node_versions: list[str]

    def __post_init__(self) -> None:
        """Sort python_versions and node_versions in descending order."""
        # Sort in descending order (highest first)
        object.__setattr__(
            self,
            "python_versions",
            sorted(self.python_versions, key=Version, reverse=True),
        )
        # Sort node versions as integers for proper ordering ("24" > "20" > "8")
        object.__setattr__(
            self,
            "node_versions",
            sorted(self.node_versions, key=int, reverse=True),
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

        # Find available Node.js versions on the system
        available_node_versions = self._find_available_node()

        return VersionInfo(
            oarepo_versions=data.oarepo_versions,
            python_versions=available_versions,
            node_versions=available_node_versions,
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
        return [ver for ver in KNOWN_PYTHON_VERSIONS if Version(ver) in specifier]

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
        - a matching interpreter already known to `uv` (see
          `_is_uv_managed_python_available`), as a fallback

        Args:
            version: Python version string (e.g., "3.12")

        Returns:
            True if the Python binary is found in PATH (excluding any active
            venv) or `uv` already has a matching interpreter on hand

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
        if any(shutil.which(candidate, path=system_path) is not None for candidate in candidates):
            return True

        return self._is_uv_managed_python_available(version)

    def _is_uv_managed_python_available(self, version: str) -> bool:
        """Check uv's own interpreter registry for a matching Python.

        `uv venv --python <version>` (see services.venv._create_venv)
        transparently downloads a matching interpreter on demand, so a
        machine can satisfy `version` even when no `pythonX.Y` binary is
        exposed on PATH -- e.g. a fresh CI runner where an earlier `uv
        venv`/`uv sync` call already auto-downloaded the interpreter into
        uv's own managed-installations directory without ever symlinking it
        onto PATH. `uv python list --only-installed` reports exactly what
        uv already has on hand and never triggers a download itself, so
        this only ever reflects an interpreter that's already there.

        Args:
            version: Python version string (e.g., "3.14")

        Returns:
            True if `uv` is on PATH and reports at least one matching
            already-installed interpreter

        """
        if shutil.which("uv", path=get_system_path()) is None:
            return False

        result = process.run(
            ["uv", "python", "list", version, "--only-installed", "--output-format", "json"],
            check=False,
            output_mode=ProcessOutputMode.CAPTURE,
        )
        if not result.success:
            return False

        try:
            installed = json.loads(result.stdout)
        except json.JSONDecodeError:
            return False
        return bool(installed)

    def _find_available_node(self) -> list[str]:
        """Find available Node.js versions on the system.

        Checks for known Node.js versions (from KNOWN_NODE_VERSIONS) that are
        available on the system PATH.

        Returns:
            List of available Node.js major versions as strings (e.g., ["24", "22"]),
            sorted descending (highest first). May be empty if no Node.js is found.

        """
        return [ver for ver in KNOWN_NODE_VERSIONS if self._is_node_available(ver)]

    def _is_node_available(self, version: str) -> bool:
        """Check if a specific Node.js version is available on the system.

        Uses `node --version` to check if the binary exists and extracts the
        major version to match against the requested version.

        Args:
            version: Node.js major version string (e.g., "24", "22", "20")

        Returns:
            True if a `node` binary is found in PATH (excluding any active venv)
            and its major version matches the requested version

        """
        system_path = get_system_path()
        node_binary = shutil.which("node", path=system_path)
        if node_binary is None:
            return False

        # Get node version
        result = process.run(
            ["node", "--version"],
            check=False,
            output_mode=ProcessOutputMode.CAPTURE,
        )
        if not result.success:
            return False

        # Parse version (output format: "v24.1.0" or "v22.9.0")
        version_output = result.stdout.strip()
        if not version_output.startswith("v"):
            return False

        # Extract major version
        try:
            major_version = version_output[1:].split(".")[0]
            return major_version == version
        except IndexError, ValueError:
            return False
