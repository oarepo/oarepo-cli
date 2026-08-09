# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Alembic migration management for OARepo libraries."""

from __future__ import annotations

import textwrap
from typing import TYPE_CHECKING

import tomlkit

from oarepo_cli.core.errors import ValidationError
from oarepo_cli.services import process
from oarepo_cli.services.pyproject_reader import PyProjectReader
from oarepo_cli.services.services_lifecycle import ServicesLifecycleManager
from oarepo_cli.services.venv import VirtualEnvironmentManager
from oarepo_cli.ui import ConsoleOutput  # noqa: TC001 (used at runtime, not just type hints)

if TYPE_CHECKING:
    from tomlkit import TOMLDocument

    from oarepo_cli.core.context import ProjectContext

# Minimum number of Python files to consider alembic initialized
_MIN_INITIALIZED_FILES = 2


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

    def init(
        self,
        alembic_path: Path | None = None,
        verify_model_entrypoint: bool = True,
    ) -> None:
        """Initialize Alembic support for the library.

        Performs the following checks and operations:
        1. Verifies invenio_db.models entrypoint exists
        2. Creates alembic/ directory in the first code directory if needed
        3. Adds invenio_db.alembic entrypoint if missing
        4. Checks if alembic is already initialized (2+ python files)
        5. Syncs the project to register entrypoints
        6. Starts/restarts services
        7. Checks that alembic state is clean (no uncommitted changes)
        8. Creates initial branch migration if needed
        9. Runs alembic upgrade heads
        10. Creates migration for initial tables

        Args:
            alembic_path: optional path to the alembic directory
            verify_model_entrypoint: whether to verify the invenio_db.models entrypoint

        Raises:
            ValidationError: If required entrypoints are missing or alembic state is not clean

        """
        # Step 1: Check for invenio_db.models entrypoint
        if verify_model_entrypoint:
            self._check_db_models_entrypoint()

        # Step 2: Check/create alembic directory
        alembic_path = self._ensure_alembic_directory(alembic_path).resolve()

        # Step 3: Check/create invenio_db.alembic entrypoint
        self._ensure_alembic_entrypoint(alembic_path)

        # Step 4: Check if already initialized
        if self._is_already_initialized(alembic_path):
            self._console.success("\n✓ Alembic is already initialized (found migrations)")
            return

        # Step 5: Sync project to register entrypoints
        self._sync_project()

        # Step 6: Start/restart services
        self._restart_services()

        # Step 7: Create branch migration if no python files exist
        if not self._has_python_files(alembic_path):
            self._create_branch_migration(alembic_path)

        # Step 8: Upgrade to heads
        self._upgrade_heads()

        # Step 9: Create initial tables migration
        self._create_tables_migration()

        self._console.success("\n✓ Alembic initialization completed successfully!")
        self._console.warning(
            "\n⚠️  IMPORTANT: Please carefully review the generated migration file in the alembic directory.",
            fg=None,
        )
        self._console.warning(
            "   Verify that it contains only the intended table changes for your models.",
            fg=None,
        )

    def revision(self, message: str, alembic_path: Path | None = None) -> bool:
        """Create an Alembic revision with the given message.

        Args:
            message: Revision message to use
            alembic_path: Optional path to the alembic directory

        Returns:
            True if revision was created successfully, False otherwise

        """
        self._console.info(f"✓ Creating revision: {message}")

        # Step 1: Get alembic directory
        alembic_directory = alembic_path if alembic_path is not None else self._get_alembic_directory()
        if alembic_directory is None:
            self._console.error("✗ No alembic directory found")
            return False

        # Step 2: Ensure alembic directory exists and contains at least 2 files (initial + tables)
        if self._count_python_files(alembic_directory) < _MIN_INITIALIZED_FILES:
            self._console.error("✗ Alembic directory is not initialized - run 'alembic init' first")
            return False

        # Step 3: Restart services
        self._restart_services()

        # Step 4: Upgrade to heads
        self._upgrade_heads()

        # Step 5: Create a new revision
        self._create_revision(message)

        # Destroy services after completion
        services_mgr = ServicesLifecycleManager(
            config=self._context.config,
            project_root=self._context.root_directory,
            quiet=self._console.is_quiet,
        )
        services_mgr.destroy_services()

        return True

    def apply(self) -> None:
        """Apply all pending migrations by running 'invenio alembic upgrade heads'.

        This command upgrades the database to the latest migration head.
        It restarts Docker services to ensure a clean state before applying migrations.

        """
        self._console.info("→ Applying all pending migrations...")

        # Restart services to ensure clean state
        self._restart_services()

        # Run upgrade heads
        self._upgrade_heads()

        self._console.success("\n✓ All migrations applied successfully!")

    def stamp(self, revision: str) -> None:
        """Stamp the database with the specified revision without applying migrations.

        This command sets the current database schema version to the specified revision
        without actually running any migration scripts. Useful for syncing the database
        state with the codebase when migrations have been applied manually or externally.

        Args:
            revision: The revision identifier to stamp (e.g., 'head', 'base', or a specific revision ID)

        """
        self._console.info(f"→ Stamping database with revision: {revision}...")

        invenio_path = self._get_venv_invenio_path()
        cmd_env = self._build_invenio_env()

        cmd = [str(invenio_path), "alembic", "stamp", revision]
        process.run(
            cmd,
            cwd=self._context.root_directory,
            env=cmd_env,
            check=True,
            output_mode=process.ProcessOutputMode.FORWARD,
        )

        self._console.success(f"\n✓ Database stamped with revision: {revision}")

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

    def _get_alembic_directory(self) -> Path | None:
        """Get the path to the alembic directory.

        Returns:
            Path to alembic directory if found, None otherwise

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
        return None

    def _ensure_alembic_directory(self, alembic_path: Path | None) -> Path:
        """Ensure alembic directory exists in the first code directory.

        Returns:
            Path to the alembic directory

        """
        code_dirs = self._context.code_directories_without_tests
        pyproject_data = PyProjectReader().read(self._context.pyproject_path)
        package_name = pyproject_data.name.replace("-", "_")

        alembic_directory = alembic_path if alembic_path is not None else self._get_alembic_directory()
        if alembic_directory is not None:
            alembic_directory.mkdir(parents=True, exist_ok=True)
            return alembic_directory

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

    def _is_already_initialized(self, alembic_path: Path) -> bool:
        """Check if alembic is already initialized.

        Args:
            alembic_path: Path to the alembic directory

        Returns:
            True if there are at least 2 Python files in the alembic directory

        """
        if not alembic_path.exists():
            return False

        python_files = list(alembic_path.glob("*.py"))
        return len(python_files) >= _MIN_INITIALIZED_FILES

    def _count_python_files(self, alembic_path: Path) -> int:
        """Count the number of Python files in the alembic directory."""
        if not alembic_path.exists():
            return 0
        return len(list(alembic_path.glob("*.py")))

    def _has_python_files(self, alembic_path: Path) -> bool:
        """Check if alembic directory has any Python files.

        Args:
            alembic_path: Path to the alembic directory

        Returns:
            True if there's at least one Python file

        """
        return self._count_python_files(alembic_path) > 0

    def _sync_project(self) -> None:
        """Sync project to register entrypoints."""
        self._console.info("→ Syncing project to register entrypoints...")

        # Use --upgrade to ensure the latest version is installed from CESNET index
        cmd = ["uv", "pip", "install", "--upgrade", "--no-deps", "--prerelease", "allow", "-e", "."]
        process.run(
            cmd,
            cwd=self._context.root_directory,
            check=True,
            output_mode=process.ProcessOutputMode.CAPTURE,
        )

        self._console.info("✓ Project synced")

    def _get_package_name(self) -> str:
        """Get the package name from pyproject.toml.

        Returns:
            Package name with hyphens replaced by underscores

        """
        pyproject_data = PyProjectReader().read(self._context.pyproject_path)
        return pyproject_data.name.replace("-", "_")

    def _get_venv_invenio_path(self) -> Path:
        """Get path to invenio executable in the virtual environment.

        Returns:
            Path to invenio binary

        Raises:
            ValidationError: If invenio is not found in venv

        """
        from oarepo_cli.core.platform import get_platform_detector

        venv_mgr = VirtualEnvironmentManager(config=self._context.config, project_root=self._context.root_directory)
        # Access internal venv path directly
        venv_path = venv_mgr._venv_path  # noqa: SLF001

        if not venv_path or not venv_path.exists():
            raise ValidationError("Virtual environment not found. Run 'oarepo-cli library install' first.")

        platform = get_platform_detector()
        bin_dir = platform.get_venv_bin_dir()
        invenio_path = venv_path / bin_dir / "invenio"

        if not invenio_path.exists():
            raise ValidationError(
                "invenio command not found in virtual environment. "
                "Ensure invenio is installed in your project dependencies."
            )

        return invenio_path

    def _get_service_env(self) -> dict[str, str]:
        """Get environment variables from services.

        Returns:
            Dictionary of environment variables

        """
        services_mgr = ServicesLifecycleManager(
            config=self._context.config,
            project_root=self._context.root_directory,
            quiet=self._console.is_quiet,
        )
        return services_mgr.load_service_env()

    def _build_invenio_env(self) -> dict[str, str]:
        """Build environment for running invenio commands.

        Returns:
            Dictionary of environment variables with INVENIO_SQLALCHEMY_DATABASE_URI set

        """
        # Get base environment with service variables
        service_env = self._get_service_env()
        cmd_env = process.build_subprocess_env()
        cmd_env.update(service_env)

        # Map SQLALCHEMY_DATABASE_URI to INVENIO_SQLALCHEMY_DATABASE_URI
        if "SQLALCHEMY_DATABASE_URI" in cmd_env:
            cmd_env["INVENIO_SQLALCHEMY_DATABASE_URI"] = cmd_env["SQLALCHEMY_DATABASE_URI"]

        return cmd_env

    def _create_branch_migration(self, alembic_path: Path) -> None:  # noqa: ARG002
        """Create initial branch migration.

        Args:
            alembic_path: Path to the alembic directory (not used, kept for API compatibility)

        """
        package_name = self._get_package_name()
        # Branch name should match the entrypoint name (package_name)
        branch_name = package_name

        self._console.info(f"→ Creating branch migration '{branch_name}'...")

        invenio_path = self._get_venv_invenio_path()
        cmd_env = self._build_invenio_env()

        cmd = [
            str(invenio_path),
            "alembic",
            "revision",
            f"Create {package_name} branch.",
            "-b",
            branch_name,
            "-p",
            "dbdbc1b19cf2",
            "--empty",
        ]

        process.run(
            cmd,
            cwd=self._context.root_directory,
            env=cmd_env,
            check=True,
            output_mode=process.ProcessOutputMode.FORWARD,
        )

        self._console.info(f"✓ Branch migration '{branch_name}' created")

    def _restart_services(self) -> None:
        """Restart Docker services (stop and start)."""
        services_mgr = ServicesLifecycleManager(
            config=self._context.config,
            project_root=self._context.root_directory,
            quiet=self._console.is_quiet,
        )

        self._console.info("→ Restarting services...")

        # Stop services if running
        if services_mgr.are_services_running():
            services_mgr.stop_services()

        # Start services
        services_mgr.start_services()

        self._console.info("✓ Services started")

    def _upgrade_heads(self) -> None:
        """Run invenio alembic upgrade heads."""
        self._console.info("→ Running alembic upgrade heads...")

        invenio_path = self._get_venv_invenio_path()
        cmd_env = self._build_invenio_env()

        cmd = [str(invenio_path), "alembic", "upgrade", "heads"]
        process.run(
            cmd,
            cwd=self._context.root_directory,
            env=cmd_env,
            check=True,
            output_mode=process.ProcessOutputMode.FORWARD,
        )

        self._console.info("✓ Alembic upgrade completed")

    def _create_tables_migration(self) -> None:
        """Create migration for initial tables."""
        package_name = self._get_package_name()

        self._create_revision(f"Create {package_name} tables.")

    def _create_revision(self, message: str) -> None:
        """Create an Alembic revision with the given message.

        Args:
            message (str): The revision message to use.

        """
        package_name = self._get_package_name()
        # Branch name should match the entrypoint name (package_name)
        branch_name = package_name

        self._console.info(f"→ Creating revision {message} for {package_name}...")

        invenio_path = self._get_venv_invenio_path()
        cmd_env = self._build_invenio_env()

        cmd = [
            str(invenio_path),
            "alembic",
            "revision",
            message,
            "-b",
            branch_name,
        ]

        process.run(
            cmd,
            cwd=self._context.root_directory,
            env=cmd_env,
            check=True,
            output_mode=process.ProcessOutputMode.FORWARD,
        )

        self._console.info(f"✓ Created alembic revision: {message}")

    def _check_alembic_differences(self) -> None:
        """Check if alembic state is clean (no uncommitted database changes).

        Runs invenio shell with a script that checks for differences between
        the database schema and the alembic migrations.

        Raises:
            ValidationError: If alembic state is not clean (has uncommitted changes)

        """
        self._console.info("→ Checking alembic state...")

        # Python script to check alembic differences
        check_script = textwrap.dedent(
            """
            from flask import current_app
            ext = current_app.extensions["invenio-db"]
            alembic = ext.alembic
            if alembic.compare_metadata():
                print("Alembic state not clean:")
                print(alembic.compare_metadata())
            """
        )

        invenio_path = self._get_venv_invenio_path()
        cmd_env = self._build_invenio_env()

        cmd = [
            str(invenio_path),
            "shell",
            "-c",
            check_script,
        ]

        result = process.run(
            cmd,
            cwd=self._context.root_directory,
            env=cmd_env,
            check=True,
            output_mode=process.ProcessOutputMode.CAPTURE,
        )

        # Check if output contains "Alembic state not clean"
        if "Alembic state not clean" in result.stdout:
            self._console.error("❌ Alembic state is not clean!")
            self._console.error("\nUncommitted database changes detected:")
            self._console.error(result.stdout)
            raise ValidationError(
                "Alembic state is not clean. There are uncommitted database schema changes. "
                "Please ensure your database schema matches your migrations before running alembic init."
            )

        self._console.info("✓ Alembic state is clean")

    def check(self, sql: bool = False) -> int:
        """Check for pending database migrations.

        Runs the check_migrations.py script to compare the current database schema
        against the model metadata and detect any pending migrations.

        Args:
            sql: If True, output SQL statements instead of JSON

        Returns:
            Exit code: 0 if no migrations needed, 1 if pending migrations detected

        """
        import os
        import tempfile
        from importlib.resources import files
        from pathlib import Path

        # Get the script content and write it to a temporary file
        script_content = files("oarepo_cli.configuration").joinpath("check_migrations.py").read_text()

        # Create a temporary file that persists after closing (delete=False)
        # We manually manage the lifecycle to ensure the file exists during subprocess execution
        fd, temp_script_path = tempfile.mkstemp(suffix=".py")
        try:
            # Write script content to the temporary file
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(script_content)

            # Build the command to run the migration check script via invenio shell
            # This ensures Flask and Invenio are properly initialized
            cmd = [
                str(self._get_venv_invenio_path()),
                "shell",
                temp_script_path,
            ]
            if sql:
                cmd.append("sql")
            cmd_env = self._build_invenio_env()

            result = process.run(
                cmd,
                cwd=self._context.root_directory,
                env=cmd_env,
                check=True,
                output_mode=process.ProcessOutputMode.FORWARD,
            )

            # Parse the output to determine if there are pending migrations
            output = result.stdout.strip()

            # Forward mode doesn't actually forward, so we need to print manually
            if output:
                print(output)  # noqa: T201

            if sql:
                # For SQL mode, return 1 if there is any output (migrations needed)
                if output and output != "[]":
                    return 1  # Pending migrations
                return 0  # No migrations

            # JSON mode - parse and check if empty
            import json

            try:
                migrations = json.loads(output)
                if isinstance(migrations, list) and len(migrations) > 0:
                    # There are pending migrations
                    return 1
                return 0  # No pending migrations
            except json.JSONDecodeError:
                # If we can't parse JSON, assume there might be issues
                return 1
        finally:
            # Clean up temporary file
            Path(temp_script_path).unlink()

    def check_with_services(self, sql: bool = False) -> int:
        """Check for pending database migrations with service lifecycle management.

        This method starts Docker services, upgrades to heads, runs the migration
        check, and then destroys the services. Intended for library commands where
        services should not persist after the check.

        Args:
            sql: If True, output SQL statements instead of JSON

        Returns:
            Exit code: 0 if no migrations needed, 1 if pending migrations detected

        """
        try:
            # Start services
            self._console.info("→ Starting services...")
            services_mgr = ServicesLifecycleManager(
                config=self._context.config,
                project_root=self._context.root_directory,
                quiet=self._console.is_quiet,
            )
            services_mgr.start_services()
            self._console.info("✓ Services started")

            # Upgrade to heads to ensure database is up to date before checking
            self._upgrade_heads()

            # Run the check
            return self.check(sql=sql)
        finally:
            # Always destroy services after completion
            self._console.info("→ Destroying services...")
            services_mgr = ServicesLifecycleManager(
                config=self._context.config,
                project_root=self._context.root_directory,
                quiet=self._console.is_quiet,
            )
            services_mgr.destroy_services()
            self._console.info("✓ Services destroyed")
