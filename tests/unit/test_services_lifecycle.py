# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Unit tests for oarepo_cli.services.services_lifecycle."""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

from oarepo_cli.core.config import CliConfig, ServicesConfig
from oarepo_cli.services.services_lifecycle import ServicesLifecycleManager

if TYPE_CHECKING:
    from pathlib import Path
    from unittest.mock import MagicMock

    from pytest_mock import MockerFixture


def _mock_run(mocker: MockerFixture, stdout: str = "export DB_URL=postgresql://\n") -> MagicMock:
    """Patch process.run used by the lifecycle manager to return ``stdout``."""
    return mocker.patch(
        "oarepo_cli.services.services_lifecycle.process.run",
        return_value=subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr=""),
    )


def test_start_services_with_s3_disabled_omits_s3_option(tmp_path: Path, mocker: MockerFixture) -> None:
    """Test that a disabled service type is not passed to docker-services-cli."""
    run = _mock_run(mocker)
    check_s3 = mocker.patch("oarepo_cli.services.services_lifecycle._check_s3_service_supported")
    config = CliConfig(services=ServicesConfig(s3=None))

    env = ServicesLifecycleManager(config, tmp_path).start_services()

    cmd = run.call_args.args[0]
    assert cmd[1:] == [
        "up",
        "--db",
        "postgresql",
        "--search",
        "opensearch",
        "--mq",
        "rabbitmq",
        "--cache",
        "redis",
        "--env",
    ]
    check_s3.assert_not_called()
    assert env == {"DB_URL": "postgresql://"}


def test_start_services_with_defaults_passes_all_service_types(tmp_path: Path, mocker: MockerFixture) -> None:
    """Test that every service type is passed when none is disabled."""
    run = _mock_run(mocker)
    check_s3 = mocker.patch("oarepo_cli.services.services_lifecycle._check_s3_service_supported")

    ServicesLifecycleManager(CliConfig(), tmp_path).start_services()

    cmd = run.call_args.args[0]
    assert cmd[1:] == [
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
        "rustfs",
        "--env",
    ]
    check_s3.assert_called_once_with("rustfs")


def test_start_services_with_all_service_types_disabled_runs_nothing(tmp_path: Path, mocker: MockerFixture) -> None:
    """Test that docker-services-cli isn't run (it would start everything) when all types are disabled."""
    run = _mock_run(mocker)
    config = CliConfig(services=ServicesConfig(db=None, search=None, mq=None, cache=None, s3=None))

    env = ServicesLifecycleManager(config, tmp_path).start_services()

    run.assert_not_called()
    assert env == {}
    assert not (tmp_path / ".env-services").exists()
