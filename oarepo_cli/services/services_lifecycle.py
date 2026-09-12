# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Services lifecycle management for OARepo projects."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from oarepo_cli.core.config import CliConfig

from oarepo_cli.configuration.constants import ENV_SERVICES_FILE
from oarepo_cli.core.errors import ConfigurationError
from oarepo_cli.services import process


def _check_s3_service_supported(s3_service: str) -> None:
    """Fail early if the installed docker-services-cli can't provide ``s3_service``.

    RustFS support (``ServiceType.RUSTFS``, the default) isn't in any
    published docker-services-cli release yet -- only a fork carries it (see
    pyproject.toml's ``[tool.uv.sources]``). Whoever ends up with a plain
    upstream install (a different lockfile, a manual override, ...) would
    otherwise only find out via a much less clear ``click.BadParameter``
    raised deep inside the ``docker-services-cli`` subprocess.

    Args:
        s3_service: The configured s3 service name (``config.services.s3``)

    Raises:
        ConfigurationError: If the installed docker-services-cli doesn't
            list ``s3_service`` as an available s3 service

    """
    from docker_services_cli.config import SERVICE_TYPES

    available = SERVICE_TYPES.get("s3", [])
    if s3_service not in available:
        raise ConfigurationError(
            f"The installed docker-services-cli does not support {s3_service!r} as an s3 "
            f"service (available: {', '.join(available) or 'none'}). Install a "
            "docker-services-cli build with RustFS support, e.g. "
            '`uv add "docker-services-cli @ git+https://github.com/mesemus/docker-services-cli@rustfs"`, '
            "or set services.s3 to a supported value (OAREPO_SERVICES_S3 or "
            "[tool.oarepo-cli.services].s3 in pyproject.toml)."
        )


def _docker_services_cli_path() -> str:
    """Resolve the docker-services-cli binary installed alongside oarepo-cli's own venv.

    docker-services-cli is a regular oarepo-cli dependency (see
    pyproject.toml), not a target-project dependency, so it's resolved next
    to the running interpreter rather than via PATH -- ``process.run``
    strips the oarepo-cli venv's own bin directory from PATH by default to
    keep it from leaking into target-project subprocesses, which would
    otherwise make this bundled binary unresolvable. Mirrors
    ``services.lint._tool_path``/``services.invenio_cli._invenio_cli_path``'s
    identical rationale.

    Returns:
        Absolute path to the binary if found next to the current
        interpreter, otherwise the bare name (resolved via PATH by the
        subprocess call).

    """
    candidate = Path(sys.executable).parent / "docker-services-cli"
    return str(candidate) if candidate.exists() else "docker-services-cli"


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
            ConfigurationError: If the installed docker-services-cli doesn't
                support the configured s3 service
            ProcessExecutionError: If docker-services-cli fails

        """
        if self._config.services.skip:
            return {}

        _check_s3_service_supported(self._config.services.s3)

        # Build docker-services-cli command
        cmd = [
            _docker_services_cli_path(),
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
            _docker_services_cli_path(),
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

    def destroy_services(self) -> None:
        """Stop Docker services and clean up.

        Uses docker-services-cli to stop all running services and removes
        the .env-services file. Note: This does not destroy persistent volumes;
        it only stops the containers.

        Raises:
            ProcessExecutionError: If docker-services-cli fails

        """
        if self._config.services.skip:
            return

        # Run docker-services-cli down
        cmd = [
            _docker_services_cli_path(),
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
