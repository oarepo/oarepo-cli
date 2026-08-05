# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Test orchestration service for OARepo projects."""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from oarepo_cli.core.context import ProjectContext

from oarepo_cli.services import process
from oarepo_cli.services.process import ProcessOutputMode
from oarepo_cli.services.services_lifecycle import ServicesLifecycleManager
from oarepo_cli.services.venv import VenvRequirements, VirtualEnvironmentManager


class TestOrchestrator:
    """Orchestrates pytest execution with services lifecycle management.

    Manages the complete test execution workflow:
    1. Start Docker services (unless skipped)
    2. Install pytest and coverage dependencies if needed
    3. Run pytest with appropriate arguments
    4. Stop services after tests complete
    5. Return structured result
    """

    def __init__(self, context: ProjectContext, *, quiet: bool = False) -> None:
        """Initialize the test orchestrator.

        Args:
            context: Project context with configuration and paths
            quiet: If True, suppress service start/stop messages
        """
        self._context = context
        self._quiet = quiet
        self._services_manager = ServicesLifecycleManager(
            config=context.config, project_root=context.root_directory, quiet=quiet
        )
        # Cache pyproject data to avoid multiple reads
        from oarepo_cli.services.pyproject_reader import PyProjectReader

        reader = PyProjectReader()
        self._pyproject_data = reader.read(context.pyproject_path)

    def run_tests(
        self,
        pytest_args: list[str] | None = None,
        coverage: bool | None = None,
        skip_services: bool | None = None,
    ) -> process.ProcessResult:
        """Run pytest tests with services orchestration.

        Args:
            pytest_args: Additional arguments to pass to pytest
            coverage: Enable coverage reporting (overrides config if provided)
            skip_services: Skip starting/stopping services (overrides config if provided)

        Returns:
            ProcessResult with test execution details

        Raises:
            ProcessExecutionError: If pytest execution fails (when check=True)
        """
        pytest_args = pytest_args or []

        # Determine if we should use coverage (CLI arg > config)
        use_coverage = coverage if coverage is not None else self._context.config.test.coverage

        # Determine if we should skip services (CLI arg > config)
        should_skip_services = (
            skip_services if skip_services is not None else self._context.config.test.skip_services
        )

        services_started = False
        console = None
        service_env_vars = {}

        try:
            # Start services if not skipped, unless already running (fast
            # path: just load the existing connection details in that case)
            if not should_skip_services:
                already_running = self._services_manager.are_services_running()

                if not already_running and not self._quiet:
                    from oarepo_cli.ui import ConsoleOutput

                    console = ConsoleOutput(quiet=False)
                    console.info("🚀 Starting services...", fg=None, bold=True)

                service_env_vars = self._services_manager.start_services_if_needed()
                services_started = not already_running

                if services_started and not self._quiet and console:
                    console.info("  ✓ Services started", fg=None)

            # Ensure venv exists before trying to install dependencies (fast
            # path: skip reinstalling - and validating requirements - if the
            # venv directory is already there)
            venv_existed = self._context.venv_path.exists()
            if not venv_existed:
                if not self._quiet:
                    if console is None:
                        from oarepo_cli.ui import ConsoleOutput

                        console = ConsoleOutput(quiet=False)
                    console.info("🔨 Creating virtual environment...", fg=None, bold=True)

                requirements = VenvRequirements(
                    python_binary=str(self._context.python_binary),
                    oarepo_version=self._context.oarepo_version,
                    extras=[],
                    editable=True,
                )
                venv_mgr = VirtualEnvironmentManager(
                    config=self._context.config, project_root=self._context.root_directory
                )
                venv_mgr.ensure_venv_exists(requirements, quiet=self._quiet)

                if not self._quiet and console:
                    console.info("  ✓ Virtual environment created", fg=None)

            # Ensure pytest and coverage are installed if needed
            self._ensure_test_dependencies(use_coverage)

            # Build pytest command
            pytest_cmd = self._build_pytest_command(pytest_args, use_coverage)

            # Run pytest (don't check=True so we can always clean up services)
            result = process.run(
                pytest_cmd,
                cwd=self._context.root_directory,
                env=service_env_vars if service_env_vars else None,
                check=False,
                output_mode=ProcessOutputMode.INTERACTIVE,
            )

            return result

        finally:
            # Always stop services if we started them
            if services_started:
                if not self._quiet:
                    if console is None:
                        from oarepo_cli.ui import ConsoleOutput

                        console = ConsoleOutput(quiet=False)
                    console.info("🛑 Stopping services...", fg=None, bold=True)

                with contextlib.suppress(Exception):
                    # Don't let service cleanup errors mask test failures
                    self._services_manager.stop_services()

                if not self._quiet and console:
                    console.info("  ✓ Services stopped", fg=None)

    def _ensure_test_dependencies(self, use_coverage: bool) -> None:
        """Ensure pytest and coverage dependencies are installed.

        Args:
            use_coverage: Whether coverage reporting is enabled
        """
        # Use uv pip to install in the project venv
        python_bin = self._context.venv_path / "bin" / "python"

        # Check if we're in a project with tests extra
        extras_to_install = []

        if "tests" in self._pyproject_data.raw.get("project", {}).get("optional-dependencies", {}):
            extras_to_install.append("tests")

        # Install the project with tests extra if available
        if extras_to_install:
            install_cmd = [
                "uv",
                "pip",
                "install",
                "-e",
                f".[{','.join(extras_to_install)}]",
            ]
            process.run(
                install_cmd,
                cwd=self._context.root_directory,
                check=True,
            )

        # Install pytest-cov if coverage is enabled and not already installed
        if use_coverage:
            # Check if pytest-cov is available
            check_cov_cmd = [str(python_bin), "-c", "import pytest_cov"]
            result = process.run(
                check_cov_cmd,
                cwd=self._context.root_directory,
                check=False,
            )

            if result.return_code != 0:
                # Install pytest-cov
                install_cov_cmd = ["uv", "pip", "install", "pytest-cov"]
                process.run(
                    install_cov_cmd,
                    cwd=self._context.root_directory,
                    check=True,
                )

    def _build_pytest_command(self, pytest_args: list[str], use_coverage: bool) -> list[str]:
        """Build the pytest command with appropriate arguments.

        Args:
            pytest_args: Additional arguments to pass to pytest
            use_coverage: Whether to enable coverage reporting

        Returns:
            Complete pytest command as list of arguments
        """
        # Use the venv's pytest
        pytest_bin = self._context.venv_path / "bin" / "pytest"

        cmd = [str(pytest_bin)]

        # Add coverage flags if enabled
        if use_coverage:
            package_name = self._pyproject_data.raw.get("project", {}).get("name", "")
            if package_name:
                # Convert package name to module name (replace hyphens with underscores)
                module_name = package_name.replace("-", "_")
                cmd.extend(["--cov", module_name])
                cmd.append("--cov-report=html")
                cmd.append("--cov-report=term")

        # Add user-provided args
        cmd.extend(pytest_args)

        return cmd
