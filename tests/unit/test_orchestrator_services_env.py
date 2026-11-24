# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Unit tests for TestOrchestrator's service environment handling."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import Mock

if TYPE_CHECKING:
    from pathlib import Path

from oarepo_cli.core.config import CliConfig
from oarepo_cli.core.context import ProjectContext
from oarepo_cli.services.services_lifecycle import ServicesLifecycleManager
from oarepo_cli.services.test_orchestrator import TestOrchestrator


def _orchestrator(tmp_path: Path) -> TestOrchestrator:
    """Build an orchestrator over a minimal project with a mocked services manager."""
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "test-lib"\n')
    context = Mock(spec=ProjectContext)
    context.root_directory = tmp_path
    context.pyproject_path = tmp_path / "pyproject.toml"
    context.config = CliConfig()
    orchestrator = TestOrchestrator(context)
    orchestrator._services_manager = Mock(spec=ServicesLifecycleManager)
    return orchestrator


def test_setup_passes_existing_env_services_when_skipping_services(tmp_path: Path) -> None:
    """An existing .env-services reaches pytest even with --skip-services."""
    orchestrator = _orchestrator(tmp_path)
    orchestrator._services_manager.load_service_env.return_value = {
        "DATABASE_URL": "postgresql://localhost:5432/db",
    }

    services_started, console, env = orchestrator._setup_test_environment(skip_services=True)

    assert services_started is False
    assert console is None
    assert env == {"DATABASE_URL": "postgresql://localhost:5432/db"}
    orchestrator._services_manager.load_service_env.assert_called_once()
    orchestrator._services_manager.start_services_if_needed.assert_not_called()


def test_setup_passes_no_env_when_skipping_services_without_file(tmp_path: Path) -> None:
    """Skipping services with no .env-services passes no extra env vars."""
    orchestrator = _orchestrator(tmp_path)
    orchestrator._services_manager.load_service_env.return_value = {}

    _, _, env = orchestrator._setup_test_environment(skip_services=True)

    assert env == {}


def test_setup_loads_running_services_env_when_not_skipping(tmp_path: Path) -> None:
    """Without --skip-services, already-running services' env is loaded, not restarted."""
    orchestrator = _orchestrator(tmp_path)
    orchestrator._services_manager.are_services_running.return_value = True
    orchestrator._services_manager.start_services_if_needed.return_value = {
        "SEARCH_URL": "opensearch://localhost:9200",
    }

    services_started, _, env = orchestrator._setup_test_environment(skip_services=False)

    assert services_started is False
    assert env == {"SEARCH_URL": "opensearch://localhost:9200"}
