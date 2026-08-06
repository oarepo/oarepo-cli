# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Typed parsing of pyproject.toml via tomllib (no grep/sed/awk)."""

from __future__ import annotations

import logging
import tomllib
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from packaging.requirements import InvalidRequirement, Requirement

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class PyProjectData:
    """Parsed pyproject.toml with typed accessors."""

    raw: dict[str, Any]

    @property
    def name(self) -> str:
        """Package name from [project].name."""
        return self.raw["project"]["name"]

    @property
    def homepage(self) -> str:
        """Homepage URL from [project].urls.Homepage."""
        return self.raw["project"]["urls"]["Homepage"]

    @property
    def requires_python(self) -> str:
        """Python version constraint from [project].requires-python."""
        return self.raw["project"]["requires-python"]

    @property
    def dependencies(self) -> list[str]:
        """List of dependency specifiers."""
        return self.raw["project"].get("dependencies", [])

    @property
    def optional_dependencies(self) -> dict[str, list[str]]:
        """Optional extra dependencies, keyed by extra name."""
        return self.raw["project"].get("optional-dependencies", {})

    @property
    def oarepo_versions(self) -> list[int]:
        """Extract OARepo major versions from dependency constraints.

        Scans [project].dependencies and [project].optional-dependencies for
        'oarepo' package references and extracts major version numbers from
        version constraints.

        Supports patterns like:
          oarepo>=14.0.0,<15.0.0  → 14
          oarepo>=13.0.0,<14.0.0  → 13
          oarepo==14.0.5         → 14

        Returns:
            List of unique major versions, sorted highest-first.
            Example: [14, 13] for a project using oarepo 14 in main deps
                     and oarepo 13 in tests extra.

        Note:
            Extracted from the dependency declarations themselves (the
            single source of truth) rather than a separate
            [tool.oarepo-cli].version config value, which would risk
            drifting out of sync -- see the deprecated-config warning
            below. Version constraints are parsed using
            packaging.requirements.

        """
        # Check for deprecated [tool.oarepo-cli].oarepo.version config and warn
        if deprecated_version := self.raw.get("tool", {}).get("oarepo-cli", {}).get("oarepo", {}).get("version"):
            logger.warning(
                "[tool.oarepo-cli].oarepo.version = %s is deprecated and ignored. "
                "OARepo versions are now extracted from [project].dependencies "
                "and [project].optional-dependencies. Remove this config key.",
                deprecated_version,
            )

        versions = set()

        # Scan main dependencies
        for dep in self.dependencies:
            if version := _extract_oarepo_version_from_specifier(dep):
                versions.add(version)

        # Scan all optional dependency groups
        for extra_deps in self.optional_dependencies.values():
            for dep in extra_deps:
                if version := _extract_oarepo_version_from_specifier(dep):
                    versions.add(version)

        return sorted(versions, reverse=True)  # Highest first

    @property
    def default_extras(self) -> list[str]:
        """Default extras to always install, from [tool.oarepo].default_extras."""
        return self.raw.get("tool", {}).get("oarepo", {}).get("default_extras", [])

    @property
    def uv_build_module_names(self) -> list[str]:
        """Module names from [tool.uv.build-backend].module-name, if any.

        Repositories built with the ``uv_build`` backend declare their
        source as several top-level module directories here (e.g.
        ``["common", "i18n", "ui"]``), unlike a library's single ``src/``
        or ``<package_name>/`` directory. Empty if the project uses a
        different build backend or doesn't set this key.
        """
        return self.raw.get("tool", {}).get("uv", {}).get("build-backend", {}).get("module-name", [])

    @property
    def uv_build_module_root(self) -> str:
        """Root prefix for `uv_build_module_names`, from [tool.uv.build-backend].module-root.

        Defaults to "" (project root itself), matching ``uv_build``'s own default.
        """
        return self.raw.get("tool", {}).get("uv", {}).get("build-backend", {}).get("module-root", "")


def _extract_oarepo_version_from_specifier(dep_spec: str) -> int | None:
    """Extract major version from an oarepo dependency specifier.

    Args:
        dep_spec: A PEP 508 dependency specifier, e.g.:
                  "oarepo>=14.0.0,<15.0.0"
                  "oarepo==14.0.5"
                  "oarepo[search]>=13.0.0,<14.0.0"

    Returns:
        The major version number if the package is 'oarepo', else None.
        Returns None for invalid specifiers (logs warning).

    Example:
        >>> _extract_oarepo_version_from_specifier(
        ...     "oarepo>=14.0.0,<15.0.0"
        ... )
        14
        >>> _extract_oarepo_version_from_specifier(
        ...     "other-package>=1.0"
        ... )
        None

    """
    try:
        req = Requirement(dep_spec)
    except InvalidRequirement:
        logger.warning("Invalid dependency specifier: %s", dep_spec)
        return None

    if req.name != "oarepo":
        return None

    # Extract major version from specifiers (>=X.Y.Z or ==X.Y.Z patterns)
    for spec in req.specifier:
        if spec.operator in (">=", "==", "~="):
            # Parse version string (e.g., "14.0.0" -> 14)
            version_str = spec.version
            return int(version_str.split(".")[0])

    return None


class PyProjectReader:
    """Reads and validates pyproject.toml files."""

    def read(self, path: Path) -> PyProjectData:
        """Read and parse pyproject.toml.

        Args:
            path: Path to pyproject.toml

        Returns:
            Typed PyProjectData object

        Raises:
            ConfigurationError: If the file is missing or contains invalid TOML

        """
        from oarepo_cli.core.errors import ConfigurationError

        if not path.exists():
            raise ConfigurationError(f"pyproject.toml not found at {path}")

        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as exc:
            raise ConfigurationError(f"Invalid TOML in {path}: {exc}") from exc

        return PyProjectData(raw=data)
