# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Services lifecycle management for OARepo projects."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from oarepo_cli.core.config import CliConfig

from oarepo_cli.services import process


class ServicesLifecycleManager:
    """Manages Docker services lifecycle via docker-services-cli.

    Handles starting and stopping Docker services (PostgreSQL, OpenSearch,
    RabbitMQ, Redis, MinIO) for development and testing. Writes environment
    variables to .env-services file for use by the application.
    """

    def __init__(self, config: CliConfig, project_root: Path) -> None:
        """Initialize the services lifecycle manager.

        Args:
            config: CLI configuration with service settings
            project_root: Root directory of the project (where .env-services is written)
        """
        self._config = config
        self._project_root = project_root
        self._env_file = project_root / ".env-services"

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

        # Run and capture output
        result = process.run(cmd, cwd=self._project_root, check=True, capture_output=True)

        # Write output to .env-services file
        self._env_file.write_text(result.stdout)

        # Parse environment variables from output
        env_vars = self._parse_env_file(result.stdout)

        return env_vars

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

        process.run(cmd, cwd=self._project_root, check=True, capture_output=True)

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

        for line in content.strip().split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            # Handle export statements
            if line.startswith("export "):
                line = line[7:]  # Remove "export " prefix

            # Split on first =
            if "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()

            # Remove quotes if present
            if (
                value.startswith('"')
                and value.endswith('"')
                or value.startswith("'")
                and value.endswith("'")
            ):
                value = value[1:-1]

            env_vars[key] = value

        return env_vars
