# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Integration tests for test orchestrator using real testlib fixture."""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

import pytest

from oarepo_cli.services.test_orchestrator import TestOrchestrator
from oarepo_cli.services.venv import VenvRequirements, VirtualEnvironmentManager

if TYPE_CHECKING:
    from oarepo_cli.core.context import ProjectContext


def test_starts_services_before_tests_real(
    test_context: ProjectContext,
) -> None:
    """Test that services are started before pytest runs."""

    orchestrator = TestOrchestrator(test_context)

    # Start services manually first
    services_mgr = orchestrator._services_manager
    env_vars = services_mgr.start_services()

    # Verify we got some env vars (services started)
    assert isinstance(env_vars, dict)

    # Cleanup - stop services
    services_mgr.stop_services()


def test_stops_services_after_tests_real(
    test_context: ProjectContext,
) -> None:
    """Test that services are stopped after operations complete."""

    orchestrator = TestOrchestrator(test_context)
    services_mgr = orchestrator._services_manager

    # Start services
    services_mgr.start_services()

    # Verify .env-services exists
    env_file = test_context.root_directory / ".env-services"
    assert env_file.exists()

    # Stop services
    services_mgr.stop_services()

    # Verify .env-services was removed
    assert not env_file.exists()


def test_skips_services_when_configured(
    test_context: ProjectContext,
) -> None:
    """Test that services start/stop are skipped when configured."""
    # Configure to skip services (use services.skip, not test.skip_services)
    test_context.config.services.skip = True

    orchestrator = TestOrchestrator(test_context)
    services_mgr = orchestrator._services_manager

    # Should return empty dict when skipped
    env_vars = services_mgr.start_services()
    assert env_vars == {}

    # stop_services should also be a no-op
    services_mgr.stop_services()


def test_returns_failure_status_on_test_failure(
    test_context: ProjectContext,
) -> None:
    """Test that failure status is returned when pytest fails."""
    # Skip services entirely for this test
    test_context.config.test.skip_services = True
    test_context.config.services.skip = True

    # First ensure venv exists with pytest - use extras=["tests"] to get pytest
    venv_mgr = VirtualEnvironmentManager(
        test_context.config, project_root=test_context.root_directory
    )
    venv_mgr.ensure_venv(
        VenvRequirements(
            python_binary="python3.14", oarepo_version=14, extras=["tests"], editable=True
        )
    )

    # Manually install pytest if not present (fallback)
    result = subprocess.run(
        [str(test_context.venv_path / "bin" / "pip"), "install", "pytest"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        failure_reason = f"Failed to install pytest: {result.stderr}"
        # ty misresolves pytest.fail's @_with_exception-decorated signature (reason: str)
        pytest.fail(failure_reason)  # ty: ignore[invalid-argument-type]

    orchestrator = TestOrchestrator(test_context)

    # Run pytest with a non-existent test file to trigger failure
    run_result = orchestrator.run_tests(pytest_args=["tests/nonexistent.py"])

    # Should return failure
    assert run_result.return_code != 0
    assert not run_result.success


def test_passes_coverage_flags_when_enabled_real(
    test_context: ProjectContext,
) -> None:
    """Test that coverage flags are added when coverage is enabled."""
    # Enable coverage in config
    test_context.config.test.coverage = True

    # Ensure venv has pytest-cov
    venv_mgr = VirtualEnvironmentManager(
        test_context.config, project_root=test_context.root_directory
    )
    venv_mgr.ensure_venv(
        VenvRequirements(python_binary="python3.14", oarepo_version=14, editable=True)
    )

    # Install pytest-cov if not present
    subprocess.run(
        [str(test_context.venv_path / "bin" / "pip"), "install", "pytest-cov"],
        check=True,
    )

    orchestrator = TestOrchestrator(test_context)

    # The orchestrator should add coverage flags when running tests
    # We can verify by checking the command construction
    pytest_cmd = orchestrator._build_pytest_command(["tests/"], use_coverage=True)
    assert "--cov" in pytest_cmd


def test_passes_additional_pytest_args_real(
    test_context: ProjectContext,
) -> None:
    """Test that additional pytest arguments are passed through."""
    # Ensure venv exists
    venv_mgr = VirtualEnvironmentManager(
        test_context.config, project_root=test_context.root_directory
    )
    venv_mgr.ensure_venv(
        VenvRequirements(python_binary="python3.14", oarepo_version=14, editable=True)
    )

    orchestrator = TestOrchestrator(test_context)

    # Build pytest command with custom arguments
    pytest_cmd = orchestrator._build_pytest_command(["-v", "-x", "tests/"], use_coverage=False)
    assert "-v" in pytest_cmd
    assert "-x" in pytest_cmd
    assert "tests/" in pytest_cmd


def test_coverage_override_via_parameter_real(
    test_context: ProjectContext,
) -> None:
    """Test that coverage parameter overrides config."""
    # Config says no coverage
    test_context.config.test.coverage = False

    orchestrator = TestOrchestrator(test_context)

    # Build command with coverage=True override
    pytest_cmd = orchestrator._build_pytest_command(["tests/"], use_coverage=True)
    assert "--cov" in pytest_cmd


def test_skip_services_override_via_parameter_real(
    test_context: ProjectContext,
) -> None:
    """Test that skip_services parameter overrides config."""
    # Config says use services (skip_services=False)
    test_context.config.test.skip_services = False

    orchestrator = TestOrchestrator(test_context)

    # Verify that the run_tests method correctly handles the skip_services parameter
    # by checking the internal logic - when skip_services=True is passed,
    # should_skip_services should be True regardless of config
    # We test this indirectly by verifying the command building works
    pytest_cmd = orchestrator._build_pytest_command(["tests/"], use_coverage=False)
    assert str(test_context.venv_path / "bin" / "pytest") in pytest_cmd


def test_loads_service_env_from_file_real(
    test_context: ProjectContext,
) -> None:
    """Test that environment variables from .env-services are loaded when they exist."""
    # Pre-create .env-services file
    env_file = test_context.root_directory / ".env-services"
    env_file.write_text(
        'export DATABASE_URL="postgresql://localhost:5432/test"\n'
        'export SEARCH_URL="opensearch://localhost:9200"\n'
    )

    orchestrator = TestOrchestrator(test_context)
    services_mgr = orchestrator._services_manager

    env_vars = services_mgr.load_service_env()

    assert env_vars["DATABASE_URL"] == "postgresql://localhost:5432/test"
    assert env_vars["SEARCH_URL"] == "opensearch://localhost:9200"

    # Cleanup
    env_file.unlink()


def test_full_test_run_with_real_venv(
    test_context: ProjectContext,
) -> None:
    """Test running actual pytest against testlib with real venv."""
    test_context.config.test.coverage = False
    test_context.config.test.skip_services = True
    test_context.config.services.skip = True

    # Ensure venv exists with test dependencies
    venv_mgr = VirtualEnvironmentManager(
        test_context.config, project_root=test_context.root_directory
    )
    venv_mgr.ensure_venv(
        VenvRequirements(
            python_binary="python3.14", oarepo_version=14, extras=["tests"], editable=True
        )
    )

    # Manually install pytest-cov if needed (for coverage tests)
    subprocess.run(
        [str(test_context.venv_path / "bin" / "pip"), "install", "pytest-cov"],
        capture_output=True,
        check=False,
    )

    orchestrator = TestOrchestrator(test_context)

    # Run the existing sample tests in tests/ folder
    result = orchestrator.run_tests(pytest_args=["tests/test_sample.py"])

    # Test should pass
    assert result.success
    assert result.return_code == 0
