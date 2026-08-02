# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Typed parsing of pyproject.toml via tomllib (no grep/sed/awk)."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path


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
        r"""OARepo major versions, extracted from [tool.oarepo-cli].

        Looks for `version` key in `[tool.oarepo-cli]` and returns it as a
        single-element list if present, or empty list if not configured.

        Example pyproject.toml:
            [tool.oarepo-cli]
            version = 14

        Returns: [14] or [] if not configured

        This replaces the bash script's multi-version approach with a simpler
        single-version configuration that aligns with the tool.oarepo-cli section.
        """
        version = self.raw.get("tool", {}).get("oarepo-cli", {}).get("version")
        if version is not None:
            return [int(version)]
        return []

    @property
    def default_extras(self) -> list[str]:
        """Default extras to always install, from [tool.oarepo].default_extras."""
        return self.raw.get("tool", {}).get("oarepo", {}).get("default_extras", [])


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
