# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Test orchestration service for OARepo projects."""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from oarepo_cli.core.context import ProjectContext

from oarepo_cli.services import process
from oarepo_cli.services.services_lifecycle import ServicesLifecycleManager


class TestOrchestrator:
    """Orchestrates pytest execution with services lifecycle management.

    Manages the complete test execution workflow:
    1. Start Docker services (unless skipped)
    2. Install pytest and coverage dependencies if needed
    3. Run pytest with appropriate arguments
    4. Stop services after tests complete
    5. Return structured result
    """

    def __init__(self, context: ProjectContext) -> None:
        """Initialize the test orchestrator.

        Args:
            context: Project context with configuration and paths
        """
        self._context = context
        self._services_manager = ServicesLifecycleManager(
            config=context.config, project_root=context.root_directory
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

        try:
            # Start services if not skipped
            if not should_skip_services:
                self._services_manager.start_services()
                services_started = True

            # Ensure pytest and coverage are installed if needed
            self._ensure_test_dependencies(use_coverage)

            # Build pytest command
            pytest_cmd = self._build_pytest_command(pytest_args, use_coverage)

            # Run pytest (don't check=True so we can always clean up services)
            result = process.run(
                pytest_cmd,
                cwd=self._context.root_directory,
                check=False,
                interactive=True,  # Real-time output for tests
            )

            return result

        finally:
            # Always stop services if we started them
            if services_started:
                with contextlib.suppress(Exception):
                    # Don't let service cleanup errors mask test failures
                    self._services_manager.stop_services()

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
                capture_output=True,
            )

        # Install pytest-cov if coverage is enabled and not already installed
        if use_coverage:
            # Check if pytest-cov is available
            check_cov_cmd = [str(python_bin), "-c", "import pytest_cov"]
            result = process.run(
                check_cov_cmd,
                cwd=self._context.root_directory,
                check=False,
                capture_output=True,
            )

            if result.return_code != 0:
                # Install pytest-cov
                install_cov_cmd = ["uv", "pip", "install", "pytest-cov"]
                process.run(
                    install_cov_cmd,
                    cwd=self._context.root_directory,
                    check=True,
                    capture_output=True,
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
