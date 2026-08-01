# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Workflow tests for services lifecycle management."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from oarepo_cli.core.config import CliConfig, ServicesConfig
from oarepo_cli.services.services_lifecycle import ServicesLifecycleManager

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_subprocess import FakeProcess


@pytest.fixture
def services_config() -> CliConfig:
    """Provide a CLI config with default services settings."""
    config = CliConfig()
    config.services = ServicesConfig(
        skip=False,
        db="postgresql",
        search="opensearch",
        mq="rabbitmq",
        cache="redis",
        s3="minio",
    )
    return config


@pytest.fixture
def skip_services_config() -> CliConfig:
    """Provide a CLI config with services skipped."""
    config = CliConfig()
    config.services = ServicesConfig(skip=True)
    return config


def test_start_services_calls_docker_services_cli(
    tmp_path: Path,
    services_config: CliConfig,
    fake_process: FakeProcess,
) -> None:
    """Test that start_services calls docker-services-cli with correct arguments."""
    manager = ServicesLifecycleManager(config=services_config, project_root=tmp_path)

    # Register the expected command
    fake_process.register(
        [
            "uvx",
            "--with",
            "setuptools",
            "docker-services-cli",
            "up",
            "--db",
            "postgresql",
            "--search",
            "opensearch",
            "--mq",
            "rabbitmq",
            "--cache",
            "redis",
            "--s3",
            "minio",
            "--env",
        ],
        stdout="export DATABASE_URL=postgresql://localhost:5432/test\nexport SEARCH_URL=opensearch://localhost:9200\n",
    )

    env_vars = manager.start_services()

    # Should return parsed env vars
    assert "DATABASE_URL" in env_vars
    assert env_vars["DATABASE_URL"] == "postgresql://localhost:5432/test"


def test_start_services_writes_env_file(
    tmp_path: Path,
    services_config: CliConfig,
    fake_process: FakeProcess,
) -> None:
    """Test that start_services writes .env-services file."""
    manager = ServicesLifecycleManager(config=services_config, project_root=tmp_path)

    env_content = "export DATABASE_URL=postgresql://localhost:5432/test\n"
    fake_process.register(
        [
            "uvx",
            "--with",
            "setuptools",
            "docker-services-cli",
            "up",
            fake_process.any(),
        ],
        stdout=env_content,
    )

    manager.start_services()

    # Check that .env-services was written
    env_file = tmp_path / ".env-services"
    assert env_file.exists()
    assert env_file.read_text() == env_content


def test_start_services_skips_when_configured(
    tmp_path: Path,
    skip_services_config: CliConfig,
) -> None:
    """Test that start_services does nothing when skip is enabled."""
    manager = ServicesLifecycleManager(config=skip_services_config, project_root=tmp_path)

    # Don't register any commands - should not be called

    env_vars = manager.start_services()

    # Should return empty dict
    assert env_vars == {}
    # Should not have created any subprocess calls
    # (fake_process.calls would be empty if no matching commands were registered)


def test_stop_services_calls_docker_services_cli(
    tmp_path: Path,
    services_config: CliConfig,
    fake_process: FakeProcess,
) -> None:
    """Test that stop_services calls docker-services-cli down."""
    manager = ServicesLifecycleManager(config=services_config, project_root=tmp_path)

    # Create .env-services file
    env_file = tmp_path / ".env-services"
    env_file.write_text("export DATABASE_URL=test\n")

    # Register the expected command
    fake_process.register(
        [
            "uvx",
            "--with",
            "setuptools",
            "docker-services-cli",
            "down",
            "--env",
        ],
        stdout="",
    )

    manager.stop_services()

    # File should be removed
    assert not env_file.exists()


def test_stop_services_removes_env_file(
    tmp_path: Path,
    services_config: CliConfig,
    fake_process: FakeProcess,
) -> None:
    """Test that stop_services removes .env-services file."""
    manager = ServicesLifecycleManager(config=services_config, project_root=tmp_path)

    # Create .env-services file
    env_file = tmp_path / ".env-services"
    env_file.write_text("export DATABASE_URL=test\n")
    assert env_file.exists()

    # Register the command
    fake_process.register(
        ["uvx", "--with", "setuptools", "docker-services-cli", "down", "--env"],
        stdout="",
    )

    manager.stop_services()

    # File should be removed
    assert not env_file.exists()


def test_stop_services_skips_when_configured(
    tmp_path: Path,
    skip_services_config: CliConfig,
) -> None:
    """Test that stop_services does nothing when skip is enabled."""
    manager = ServicesLifecycleManager(config=skip_services_config, project_root=tmp_path)

    manager.stop_services()

    # Should not have raised any errors (services.skip prevents calls)


def test_load_service_env_reads_file(tmp_path: Path, services_config: CliConfig) -> None:
    """Test that load_service_env reads environment variables from file."""
    manager = ServicesLifecycleManager(config=services_config, project_root=tmp_path)

    # Create .env-services file
    env_file = tmp_path / ".env-services"
    env_file.write_text(
        'export DATABASE_URL="postgresql://localhost:5432/test"\n'
        "export SEARCH_URL=opensearch://localhost:9200\n"
    )

    env_vars = manager.load_service_env()

    assert env_vars["DATABASE_URL"] == "postgresql://localhost:5432/test"
    assert env_vars["SEARCH_URL"] == "opensearch://localhost:9200"


def test_load_service_env_returns_empty_when_no_file(
    tmp_path: Path,
    services_config: CliConfig,
) -> None:
    """Test that load_service_env returns empty dict when file doesn't exist."""
    manager = ServicesLifecycleManager(config=services_config, project_root=tmp_path)

    env_vars = manager.load_service_env()

    assert env_vars == {}


def test_are_services_running_checks_env_file(
    tmp_path: Path,
    services_config: CliConfig,
) -> None:
    """Test that are_services_running checks for .env-services file."""
    manager = ServicesLifecycleManager(config=services_config, project_root=tmp_path)

    # Initially no services running
    assert not manager.are_services_running()

    # Create .env-services file
    env_file = tmp_path / ".env-services"
    env_file.write_text("export DATABASE_URL=test\n")

    # Now services are running
    assert manager.are_services_running()


def test_parse_env_file_handles_various_formats(
    tmp_path: Path,
    services_config: CliConfig,
) -> None:
    """Test that _parse_env_file handles various environment file formats."""
    manager = ServicesLifecycleManager(config=services_config, project_root=tmp_path)

    content = """
# Comment line
export VAR1="value1"
export VAR2='value2'
VAR3=value3
export VAR4=value4

# Another comment
"""

    env_vars = manager._parse_env_file(content)

    assert env_vars["VAR1"] == "value1"
    assert env_vars["VAR2"] == "value2"
    assert env_vars["VAR3"] == "value3"
    assert env_vars["VAR4"] == "value4"


def test_start_services_with_custom_service_types(
    tmp_path: Path,
    fake_process: FakeProcess,
) -> None:
    """Test that start_services uses configured service types."""
    config = CliConfig()
    config.services = ServicesConfig(
        skip=False,
        db="mysql",
        search="elasticsearch",
        mq="kafka",
        cache="memcached",
        s3="localstack",
    )
    manager = ServicesLifecycleManager(config=config, project_root=tmp_path)

    # Register command with custom service types
    fake_process.register(
        [
            "uvx",
            "--with",
            "setuptools",
            "docker-services-cli",
            "up",
            "--db",
            "mysql",
            "--search",
            "elasticsearch",
            "--mq",
            "kafka",
            "--cache",
            "memcached",
            "--s3",
            "localstack",
            "--env",
        ],
        stdout="export DATABASE_URL=mysql://localhost:3306/test\n",
    )

    env_vars = manager.start_services()

    # Should return parsed env vars with correct service URL
    assert "DATABASE_URL" in env_vars
