# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Typed parsing of pyproject.toml via tomllib (no grep/sed/awk)."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

from oarepo_cli.configuration.constants import OAREPO_VERSION_RE


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
        r"""OARepo major versions, extracted from optional-dependencies.

        Looks for keys like `oarepo13`, `oarepo14` in `optional-dependencies`
        and returns the sorted, deduplicated major versions found (e.g. `[13, 14]`).

        This matches the bash script's behavior:
        `egrep "^oarepo[0-9]{2}\s*=" pyproject.toml`
        """
        versions = set()
        # Look for oarepoXX keys in optional-dependencies
        for key in self.optional_dependencies:
            if match := OAREPO_VERSION_RE.match(key):
                versions.add(int(match.group(1)))
        return sorted(versions)

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
