# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Services lifecycle management for OARepo projects."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from oarepo_cli.core.config import CliConfig

from oarepo_cli.configuration.constants import ENV_SERVICES_FILE
from oarepo_cli.services import process


class ServicesLifecycleManager:
    """Manages Docker services lifecycle via docker-services-cli.

    Handles starting and stopping Docker services (PostgreSQL, OpenSearch,
    RabbitMQ, Redis, MinIO) for development and testing. Writes environment
    variables to .env-services file for use by the application.
    """

    def __init__(self, config: CliConfig, project_root: Path, *, quiet: bool = False) -> None:
        """Initialize the services lifecycle manager.

        Args:
            config: CLI configuration with service settings
            project_root: Root directory of the project (where .env-services is written)
            quiet: If True, suppress docker-services-cli output

        """
        self._config = config
        self._project_root = project_root
        self._env_file = project_root / ENV_SERVICES_FILE
        self._quiet = quiet

    def start_services(self) -> dict[str, str]:
        """Start Docker services and return environment variables.

        Uses docker-services-cli to start the configured services and captures
        the environment variables needed to connect to them.

        Returns:
            Dictionary of environment variables for connecting to services

        Raises:
            ProcessExecutionError: If docker-services-cli fails

        """
        if self._config.services.skip:
            return {}

        # Build docker-services-cli command
        cmd = [
            "uvx",
            "--with",
            "setuptools",
            "docker-services-cli",
            "up",
            "--db",
            self._config.services.db,
            "--search",
            self._config.services.search,
            "--mq",
            self._config.services.mq,
            "--cache",
            self._config.services.cache,
            "--s3",
            self._config.services.s3,
            "--env",
        ]

        # Add --quiet flag if requested
        if self._quiet:
            cmd.append("--quiet")

        # Run and capture output
        result = process.run(cmd, cwd=self._project_root, check=True)

        # Write output to .env-services file
        self._env_file.write_text(result.stdout)

        # Parse environment variables from output
        return self._parse_env_file(result.stdout)

    def start_services_if_needed(self) -> dict[str, str]:
        """Start services unless already running, and return connection env vars.

        If .env-services already exists, services are presumably already
        running: skip re-invoking docker-services-cli (slow, hits Docker)
        and just load the existing environment variables instead. Intended
        for commands that just need connection details available on every
        invocation (shell, invenio, test) rather than restarting services
        each time.

        Returns:
            Dictionary of environment variables for connecting to services

        Raises:
            ProcessExecutionError: If docker-services-cli fails

        """
        if self.are_services_running():
            return self.load_service_env()
        return self.start_services()

    def stop_services(self) -> None:
        """Stop Docker services and clean up.

        Uses docker-services-cli to stop all running services and removes
        the .env-services file.

        Raises:
            ProcessExecutionError: If docker-services-cli fails

        """
        if self._config.services.skip:
            return

        # Run docker-services-cli down
        cmd = [
            "uvx",
            "--with",
            "setuptools",
            "docker-services-cli",
            "down",
            "--env",
        ]

        # Add --quiet flag if requested
        if self._quiet:
            cmd.append("--quiet")

        process.run(cmd, cwd=self._project_root, check=True)

        # Remove .env-services file if it exists
        if self._env_file.exists():
            self._env_file.unlink()

    def load_service_env(self) -> dict[str, str]:
        """Load environment variables from .env-services file.

        Returns:
            Dictionary of environment variables from the file,
            or empty dict if file doesn't exist

        Raises:
            ValueError: If .env-services file is malformed

        """
        if not self._env_file.exists():
            return {}

        content = self._env_file.read_text()
        return self._parse_env_file(content)

    def are_services_running(self) -> bool:
        """Check if services are currently running.

        Returns:
            True if .env-services file exists, False otherwise

        """
        return self._env_file.exists()

    def _parse_env_file(self, content: str) -> dict[str, str]:
        """Parse environment variables from env file content.

        Args:
            content: Content of the .env file

        Returns:
            Dictionary of environment variables

        Raises:
            ValueError: If content is malformed

        """
        env_vars = {}

        for raw_line in content.strip().split("\n"):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            # Handle export statements
            line = line.removeprefix("export ")  # Remove "export " prefix

            # Split on first =
            if "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()

            # Remove quotes if present
            if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
                value = value[1:-1]

            env_vars[key] = value

        return env_vars
