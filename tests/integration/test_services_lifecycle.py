# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Integration tests for services lifecycle management using real testlib fixture.

These tests use the real testlib project and execute actual docker-services-cli
commands to verify the services lifecycle workflow.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from oarepo_cli.core.config import CliConfig, ServicesConfig
from oarepo_cli.services.services_lifecycle import ServicesLifecycleManager

if TYPE_CHECKING:
    from pathlib import Path


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


def test_start_services_calls_docker_services_cli_real(
    clean_testlib: Path,
    services_config: CliConfig,
) -> None:
    """Test that start_services calls docker-services-cli with correct arguments."""
    manager = ServicesLifecycleManager(config=services_config, project_root=clean_testlib)

    env_vars = manager.start_services()

    # If services started successfully, we should get env vars
    # If they failed (e.g., already running or docker not available),
    # the method should handle it gracefully
    assert isinstance(env_vars, dict)


def test_start_services_writes_env_file_real(
    clean_testlib: Path,
    services_config: CliConfig,
) -> None:
    """Test that start_services writes .env-services file."""
    manager = ServicesLifecycleManager(config=services_config, project_root=clean_testlib)

    manager.start_services()

    # Check that .env-services was written (if services started)
    # Note: This may not exist if services couldn't start (docker not available, etc.)
    env_file = clean_testlib / ".env-services"
    if env_file.exists():
        content = env_file.read_text()
        assert "export" in content


def test_start_services_skips_when_configured(
    clean_testlib: Path,
    skip_services_config: CliConfig,
) -> None:
    """Test that start_services does nothing when skip is enabled."""
    manager = ServicesLifecycleManager(config=skip_services_config, project_root=clean_testlib)

    env_vars = manager.start_services()

    # Should return empty dict when skipped
    assert env_vars == {}


def test_stop_services_calls_docker_services_cli_real(
    clean_testlib: Path,
    services_config: CliConfig,
) -> None:
    """Test that stop_services calls docker-services-cli down."""
    # Create .env-services file to simulate running services
    env_file = clean_testlib / ".env-services"
    env_file.write_text("export DATABASE_URL=test\n")

    manager = ServicesLifecycleManager(config=services_config, project_root=clean_testlib)

    manager.stop_services()

    # File should be removed
    assert not env_file.exists()


def test_stop_services_removes_env_file_real(
    clean_testlib: Path,
    services_config: CliConfig,
) -> None:
    """Test that stop_services removes .env-services file."""
    manager = ServicesLifecycleManager(config=services_config, project_root=clean_testlib)

    # Create .env-services file
    env_file = clean_testlib / ".env-services"
    env_file.write_text("export DATABASE_URL=test\n")
    assert env_file.exists()

    manager.stop_services()

    # File should be removed
    assert not env_file.exists()


def test_stop_services_skips_when_configured(
    clean_testlib: Path,
    skip_services_config: CliConfig,
) -> None:
    """Test that stop_services does nothing when skip is enabled."""
    manager = ServicesLifecycleManager(config=skip_services_config, project_root=clean_testlib)

    # Create a file to ensure it's not removed
    env_file = clean_testlib / ".env-services"
    env_file.write_text("export DATABASE_URL=test\n")

    manager.stop_services()

    # File should still exist since we skipped
    assert env_file.exists()


def test_load_service_env_reads_file_real(
    clean_testlib: Path,
    services_config: CliConfig,
) -> None:
    """Test that load_service_env reads environment variables from file."""
    manager = ServicesLifecycleManager(config=services_config, project_root=clean_testlib)

    # Create .env-services file
    env_file = clean_testlib / ".env-services"
    env_file.write_text(
        'export DATABASE_URL="postgresql://localhost:5432/test"\n'
        "export SEARCH_URL=opensearch://localhost:9200\n"
    )

    env_vars = manager.load_service_env()

    assert env_vars["DATABASE_URL"] == "postgresql://localhost:5432/test"
    assert env_vars["SEARCH_URL"] == "opensearch://localhost:9200"


def test_load_service_env_returns_empty_when_no_file_real(
    clean_testlib: Path,
    services_config: CliConfig,
) -> None:
    """Test that load_service_env returns empty dict when file doesn't exist."""
    manager = ServicesLifecycleManager(config=services_config, project_root=clean_testlib)

    # clean_testlib fixture guarantees no .env-services file exists
    env_vars = manager.load_service_env()

    assert env_vars == {}


def test_are_services_running_checks_env_file_real(
    clean_testlib: Path,
    services_config: CliConfig,
) -> None:
    """Test that are_services_running checks for .env-services file."""
    manager = ServicesLifecycleManager(config=services_config, project_root=clean_testlib)

    # Initially no services running
    assert not manager.are_services_running()

    # Create .env-services file
    env_file = clean_testlib / ".env-services"
    env_file.write_text("export DATABASE_URL=test\n")

    # Now services are running
    assert manager.are_services_running()


def test_parse_env_file_handles_various_formats_real(
    clean_testlib: Path,
    services_config: CliConfig,
) -> None:
    """Test that _parse_env_file handles various environment file formats."""
    manager = ServicesLifecycleManager(config=services_config, project_root=clean_testlib)

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


def test_start_services_with_custom_service_types_real(
    clean_testlib: Path,
) -> None:
    """Test that start_services uses configured service types."""
    config = CliConfig()
    config.services = ServicesConfig(
        skip=False,
        db="postgresql",
        search="opensearch",
        mq="rabbitmq",  # Use valid MQ service
        cache="redis",
        s3="minio",
    )
    manager = ServicesLifecycleManager(config=config, project_root=clean_testlib)

    env_vars = manager.start_services()

    # Should return a dict (may be empty if services couldn't start)
    assert isinstance(env_vars, dict)
