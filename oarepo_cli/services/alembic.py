# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Alembic migration management for OARepo libraries."""

from __future__ import annotations

from typing import TYPE_CHECKING

import tomlkit

from oarepo_cli.core.errors import ValidationError
from oarepo_cli.services.pyproject_reader import PyProjectReader
from oarepo_cli.ui import ConsoleOutput  # noqa: TC001 (used at runtime, not just type hints)

if TYPE_CHECKING:
    from pathlib import Path

    from tomlkit import TOMLDocument

    from oarepo_cli.core.context import ProjectContext


class AlembicManager:
    """Manages Alembic migrations for OARepo library projects.

    Handles initialization of Alembic directories and entrypoints in pyproject.toml.
    """

    def __init__(self, context: ProjectContext, console: ConsoleOutput) -> None:
        """Initialize the alembic manager.

        Args:
            context: Project context with paths and configuration
            console: Console output handler for status messages

        """
        self._context = context
        self._console = console

    def init(self) -> None:
        """Initialize Alembic support for the library.

        Performs the following checks and operations:
        1. Verifies invenio_db.models entrypoint exists
        2. Creates alembic/ directory in the first code directory if needed
        3. Adds invenio_db.alembic entrypoint if missing

        Raises:
            ValidationError: If required entrypoints are missing

        """
        # Step 1: Check for invenio_db.models entrypoint
        self._check_db_models_entrypoint()

        # Step 2: Check/create alembic directory
        alembic_path = self._ensure_alembic_directory()

        # Step 3: Check/create invenio_db.alembic entrypoint
        self._ensure_alembic_entrypoint(alembic_path)

        self._console.success("\n✓ Alembic initialization completed successfully!")

    def _check_db_models_entrypoint(self) -> None:
        """Check if invenio_db.models entrypoint exists.

        Raises:
            ValidationError: If the entrypoint doesn't exist

        """
        pyproject_data = PyProjectReader().read(self._context.pyproject_path)
        entrypoints = pyproject_data.raw.get("project", {}).get("entry-points", {})
        db_models = entrypoints.get("invenio_db.models", {})

        if not db_models:
            package_name = pyproject_data.name.replace("-", "_")
            error_msg = (
                "Error: No 'invenio_db.models' entrypoint found.\n\n"
                "Please add an entrypoint to your pyproject.toml:\n\n"
                '[project.entry-points."invenio_db.models"]\n'
                f'{package_name} = "{package_name}.records.models"\n'
            )
            raise ValidationError(error_msg)

        self._console.info("✓ Found invenio_db.models entrypoint")

    def _ensure_alembic_directory(self) -> Path:
        """Ensure alembic directory exists in the first code directory.

        Returns:
            Path to the alembic directory

        """
        code_dirs = self._context.code_directories_without_tests
        pyproject_data = PyProjectReader().read(self._context.pyproject_path)
        package_name = pyproject_data.name.replace("-", "_")

        # Check if alembic directory already exists in any code directory
        for code_dir in code_dirs:
            # Check if alembic exists directly in code_dir (flat layout)
            alembic_dir = code_dir / "alembic"
            if alembic_dir.exists():
                self._console.info(f"✓ Found existing alembic directory: {alembic_dir}")
                return alembic_dir

            # Check if alembic exists in package subdirectory (src layout)
            package_alembic_dir = code_dir / package_name / "alembic"
            if package_alembic_dir.exists():
                self._console.info(f"✓ Found existing alembic directory: {package_alembic_dir}")
                return package_alembic_dir

        # Create alembic directory in the first code directory
        first_code_dir = code_dirs[0]

        # For src layout, create inside the package directory
        # For flat layout, code_dir is already the package directory
        if first_code_dir.name == "src":
            # src layout: create in src/package_name/alembic
            alembic_dir = first_code_dir / package_name / "alembic"
        else:
            # flat layout: create in package_name/alembic
            alembic_dir = first_code_dir / "alembic"

        alembic_dir.mkdir(parents=True, exist_ok=True)
        self._console.info(f"✓ Created alembic directory: {alembic_dir}")

        return alembic_dir

    def _ensure_alembic_entrypoint(self, alembic_path: Path) -> None:
        """Ensure invenio_db.alembic entrypoint exists.

        Args:
            alembic_path: Path to the alembic directory

        """
        pyproject_data = PyProjectReader().read(self._context.pyproject_path)
        package_name = pyproject_data.name.replace("-", "_")

        # Calculate the entrypoint value (package:alembic)
        # Find the relative path from root to alembic parent (the package directory)
        alembic_parent = alembic_path.parent
        try:
            relative_parent = alembic_parent.relative_to(self._context.root_directory)
            # Convert path to module notation
            module_path = str(relative_parent).replace("/", ".")
            # Remove 'src.' prefix if present
            module_path = module_path.removeprefix("src.")
            entrypoint_value = f"{module_path}:alembic"
        except ValueError:
            # Fallback if path calculation fails
            entrypoint_value = f"{package_name}:alembic"

        # Check if entrypoint already exists
        entrypoints = pyproject_data.raw.get("project", {}).get("entry-points", {})
        alembic_entrypoints = entrypoints.get("invenio_db.alembic", {})

        if package_name in alembic_entrypoints:
            existing_value = alembic_entrypoints[package_name]
            self._console.info(f'✓ Found existing invenio_db.alembic entrypoint: {package_name} = "{existing_value}"')
            return

        # Add the entrypoint
        self._add_alembic_entrypoint(package_name, entrypoint_value)
        self._console.info(f'✓ Added invenio_db.alembic entrypoint: {package_name} = "{entrypoint_value}"')

    def _add_alembic_entrypoint(self, package_name: str, entrypoint_value: str) -> None:
        """Add invenio_db.alembic entrypoint to pyproject.toml.

        Args:
            package_name: The package name for the entrypoint key
            entrypoint_value: The entrypoint value (e.g., "package:alembic")

        """
        document = self._read_document()

        # Navigate/create the nested structure
        project = document.setdefault("project", tomlkit.table())
        entrypoints = project.setdefault("entry-points", tomlkit.table())
        alembic_ep = entrypoints.setdefault("invenio_db.alembic", tomlkit.table())

        # Add the entrypoint
        alembic_ep[package_name] = entrypoint_value

        self._write_document(document)

    def _read_document(self) -> TOMLDocument:
        """Read and parse the project's pyproject.toml file.

        Returns:
            Parsed TOML document as a tomlkit object

        """
        return tomlkit.parse(self._context.pyproject_path.read_text(encoding="utf-8"))

    def _write_document(self, document: TOMLDocument) -> None:
        """Write the TOML document back to pyproject.toml.

        Args:
            document: The TOML document to write

        """
        self._context.pyproject_path.write_text(tomlkit.dumps(document), encoding="utf-8")
