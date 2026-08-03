# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Local, editable package management via ``[tool.uv.sources]``."""

from __future__ import annotations

from typing import TYPE_CHECKING

import tomlkit
from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name

from oarepo_cli.core.errors import ConfigurationError
from oarepo_cli.services.pyproject_reader import PyProjectReader
from oarepo_cli.services.repository import upgrade_repository
from oarepo_cli.ui import ConsoleOutput

if TYPE_CHECKING:
    from pathlib import Path

    from tomlkit import TOMLDocument
    from tomlkit.items import Array, Table

    from oarepo_cli.core.context import ProjectContext


class LocalPackageManager:
    """Adds/removes locally-developed packages as editable ``[tool.uv.sources]`` entries.

    Mirrors ``repository_runner.sh``'s ``local_sources_cmd``'s ``add`` case
    (``uv add <path> --editable``, followed by an unconditional
    ``upgrade_repository`` -- unlike ``ModelManager.create_model()``'s
    conditional reinstall), but edits ``pyproject.toml`` directly with
    ``tomlkit`` instead of shelling out to ``uv add``: unlike ``tomllib``
    (read-only, used by ``PyProjectReader``) or ``tomli-w`` (write-only,
    full-dict dump, used by copier's own templates), ``tomlkit`` is
    round-trip-preserving, so comments/key order/formatting elsewhere in a
    real, hand-edited ``pyproject.toml`` survive.

    ``remove_package()`` has no bash equivalent -- ``repository_runner.sh``'s
    ``local remove`` was never implemented (it just tells the user to edit
    ``pyproject.toml`` by hand and run ``upgrade``); this fills that gap,
    per ``00-main-architecture.md``'s compatibility matrix, which lists
    ``local remove <name>`` as a command the rewrite must actually support.
    """

    def __init__(self, context: ProjectContext, *, quiet: bool = False) -> None:
        """Initialize the local package manager.

        Args:
            context: Project context with paths and configuration
            quiet: If True, suppress status/progress messages
        """
        self._context = context
        self._quiet = quiet

    def add_package(self, path: Path) -> None:
        """Add a local, editable package to ``[tool.uv.sources]``.

        Mirrors ``repository_runner.sh``'s ``local add <path>``: validates
        ``path`` contains a ``pyproject.toml``, reads its package name from
        there, then adds/updates a ``name = { path = ..., editable = true }``
        entry in ``[tool.uv.sources]`` and appends ``name`` to
        ``[project].dependencies`` (skipped if already present, matching
        ``uv add``'s own idempotency). Re-adding an already-present package
        (e.g. with a different path) overwrites its ``[tool.uv.sources]``
        entry in place.

        Args:
            path: Path to the local package's own project directory

        Raises:
            ConfigurationError: If ``path`` has no ``pyproject.toml``
        """
        package_pyproject = path / "pyproject.toml"
        if not package_pyproject.exists():
            raise ConfigurationError(f"No pyproject.toml in {path}")

        name = canonicalize_name(PyProjectReader().read(package_pyproject).name)

        console = ConsoleOutput(quiet=self._quiet)
        console.info(f"→ Adding local package '{name}' from {path}\n")

        document = self._read_document()

        dependencies = document["project"]["dependencies"]
        if not _has_dependency(dependencies, name):
            dependencies.append(name)

        source = tomlkit.inline_table()
        source["path"] = self._relative_to_root(path)
        source["editable"] = True
        self._uv_sources_table(document)[name] = source

        self._write_document(document)

        console.info("→ Upgrading repository with the new local package\n")
        upgrade_repository(self._context, quiet=self._quiet)

        console.success(f"✓ Local package '{name}' added successfully.\n")

    def remove_package(self, name: str) -> None:
        """Remove a local package from ``[tool.uv.sources]``.

        Args:
            name: Package name (as it appears in ``[tool.uv.sources]``;
                normalized the same way ``uv``/``add_package`` do)

        Raises:
            ConfigurationError: If ``name`` isn't a known local package
        """
        canonical_name = canonicalize_name(name)
        document = self._read_document()

        sources = document.get("tool", {}).get("uv", {}).get("sources", {})
        if canonical_name not in sources:
            raise ConfigurationError(
                f"No local package named '{canonical_name}' found in [tool.uv.sources]."
            )

        console = ConsoleOutput(quiet=self._quiet)
        console.info(f"→ Removing local package '{canonical_name}'\n")

        del sources[canonical_name]
        if not sources:
            del document["tool"]["uv"]["sources"]

        _remove_dependency(document["project"]["dependencies"], canonical_name)

        self._write_document(document)

        console.info("→ Upgrading repository after removing the local package\n")
        upgrade_repository(self._context, quiet=self._quiet)

        console.success(f"✓ Local package '{canonical_name}' removed successfully.\n")

    def _read_document(self) -> TOMLDocument:
        return tomlkit.parse(self._context.pyproject_path.read_text(encoding="utf-8"))

    def _write_document(self, document: TOMLDocument) -> None:
        self._context.pyproject_path.write_text(tomlkit.dumps(document), encoding="utf-8")

    def _uv_sources_table(self, document: TOMLDocument) -> Table:
        tool = document.setdefault("tool", tomlkit.table())
        uv = tool.setdefault("uv", tomlkit.table())
        return uv.setdefault("sources", tomlkit.table())

    def _relative_to_root(self, path: Path) -> str:
        """Convert path to be relative to the project root, like a real ``uv add`` would.

        ``walk_up=True`` handles a local package living outside the project
        root too (e.g. a sibling directory), matching
        ``services.models._relative_to_root``'s same rationale.
        """
        return str(path.resolve().relative_to(self._context.root_directory.resolve(), walk_up=True))


def _dependency_name(dependency_spec: str) -> str | None:
    """Return the canonicalized package name of a PEP 508 dependency specifier, or None."""
    try:
        return canonicalize_name(Requirement(dependency_spec).name)
    except InvalidRequirement:
        return None


def _has_dependency(dependencies: Array, name: str) -> bool:
    return any(_dependency_name(dep) == name for dep in dependencies)


def _remove_dependency(dependencies: Array, name: str) -> None:
    for index, dep in enumerate(list(dependencies)):
        if _dependency_name(dep) == name:
            del dependencies[index]
