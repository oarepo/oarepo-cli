# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Tests for oarepo_cli.core.config."""

from __future__ import annotations

from pathlib import Path

import pytest

from oarepo_cli.configuration.constants import VENV_DIR, ServiceType
from oarepo_cli.core.config import (
    BuildConfig,
    CeleryConfig,
    CliConfig,
    PythonConfig,
    TestingConfig,
    VenvConfig,
)
from oarepo_cli.core.errors import ValidationError


def test_default_values_for_all_configs() -> None:
    """Test that all config classes have sensible default values."""
    config = CliConfig()

    assert config.build.editable is True
    assert config.test.coverage is False
    assert config.test.skip_services is False
    assert config.venv.path == Path(VENV_DIR)
    assert config.python.binary is None
    assert config.oarepo.version is None
    assert config.services.skip is False
    assert config.services.db == ServiceType.POSTGRESQL
    assert config.services.search == ServiceType.OPENSEARCH
    assert config.services.mq == ServiceType.RABBITMQ
    assert config.services.cache == ServiceType.REDIS
    assert config.services.s3 == ServiceType.MINIO
    assert config.model.template_url == "https://github.com/oarepo/nrp-model-copier"
    assert config.model.template_version == "rdm-14"
    assert config.translations.overlay_dir is None
    assert config.celery.pool_type == "threads"
    assert config.celery.concurrency == 10
    assert config.license.organization == "CESNET z.s.p.o"
    assert config.security.demo_user_password == "123456"


def test_environment_variable_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that environment variables override defaults."""
    monkeypatch.setenv("OAREPO_BUILD_EDITABLE", "false")
    monkeypatch.setenv("OAREPO_TEST_COVERAGE", "true")
    monkeypatch.setenv("OAREPO_VENV_PATH", "/custom/venv")
    monkeypatch.setenv("OAREPO_PYTHON_BINARY", "python3.11")
    monkeypatch.setenv("OAREPO_VERSION", "14")
    monkeypatch.setenv("OAREPO_SERVICES_SKIP", "true")
    monkeypatch.setenv("OAREPO_SERVICES_DB", "mysql")
    monkeypatch.setenv("OAREPO_CELERY_CONCURRENCY", "20")
    monkeypatch.setenv("OAREPO_LICENSE_ORG", "Test Org")

    config = CliConfig.from_env()

    assert config.build.editable is False
    assert config.test.coverage is True
    assert config.venv.path == Path("/custom/venv")
    assert config.python.binary == "python3.11"
    assert config.oarepo.version == 14
    assert config.services.skip is True
    assert config.services.db == "mysql"
    assert config.celery.concurrency == 20
    assert config.license.organization == "Test Org"


def test_pyproject_toml_overrides(tmp_path: Path) -> None:
    """Test that pyproject.toml overrides defaults."""
    (tmp_path / "pyproject.toml").write_text(
        """
[tool.oarepo-cli]
build = { editable = false }
test = { coverage = true, skip_services = true }
venv = { path = "/custom/venv" }
python = { binary = "python3.11" }
oarepo = { version = 14 }
services = { skip = true, db = "mysql", search = "elasticsearch" }
model = { template_url = "https://custom/template", template_version = "custom-v1" }
translations = { overlay_dir = "/overlay" }
celery = { pool_type = "prefork", concurrency = 20 }
license = { organization = "Test Org" }
security = { demo_user_password = "secure-password" }
"""
    )

    config = CliConfig.from_pyproject(tmp_path)

    assert config.build.editable is False
    assert config.test.coverage is True
    assert config.test.skip_services is True
    assert config.venv.path == Path("/custom/venv")
    assert config.python.binary == "python3.11"
    # [tool.oarepo-cli].oarepo.version is deliberately ignored (deprecated --
    # see PyProjectData.oarepo_versions): the version comes from
    # [project].dependencies instead, with OAREPO_VERSION as the only
    # remaining override.
    assert config.oarepo.version is None
    assert config.services.skip is True
    assert config.services.db == "mysql"
    assert config.services.search == "elasticsearch"
    assert config.model.template_url == "https://custom/template"
    assert config.model.template_version == "custom-v1"
    assert config.translations.overlay_dir == Path("/overlay")
    assert config.celery.pool_type == "prefork"
    assert config.celery.concurrency == 20
    assert config.license.organization == "Test Org"
    assert config.security.demo_user_password == "secure-password"


def test_missing_pyproject_returns_defaults(tmp_path: Path) -> None:
    """Test that missing pyproject.toml returns defaults."""
    config = CliConfig.from_pyproject(tmp_path)

    assert config.build.editable is True
    assert config.venv.path == Path(".venv")
    assert config.python.binary is None


def test_invalid_toml_raises_validation_error(tmp_path: Path) -> None:
    """Test that invalid TOML raises ValidationError."""
    (tmp_path / "pyproject.toml").write_text("invalid [[[[ syntax")

    with pytest.raises(ValidationError) as exc_info:
        CliConfig.from_pyproject(tmp_path)

    assert "Invalid TOML" in str(exc_info.value)


def test_merge_precedence_order() -> None:
    """Test that merge respects precedence order (rightmost wins for non-default values)."""
    defaults = CliConfig()
    from_pyproject = CliConfig(
        build=BuildConfig(editable=False),
        venv=VenvConfig(path=Path("/pyproject-venv")),
    )
    from_env = CliConfig(
        # Note: editable=True is the default, so it won't override pyproject's False
        # Only non-default values from env will override
        venv=VenvConfig(path=Path("/env-venv")),
        python=PythonConfig(binary="python3.12"),
        test=TestingConfig(coverage=True),  # True != False (default)
    )

    merged = CliConfig.merge([defaults, from_pyproject, from_env])

    # from_env overrides non-default values, but editable=True equals default so pyproject's False wins
    assert merged.build.editable is False  # from_pyproject (since from_env's True equals default)
    assert merged.venv.path == Path("/env-venv")  # from_env wins
    assert merged.python.binary == "python3.12"  # from_env wins
    assert merged.test.coverage is True  # from_env wins


def test_invalid_python_binary_raises_validation_error() -> None:
    """Test that invalid Python binary name raises ValidationError."""
    config = CliConfig(python=PythonConfig(binary="not-python"))

    with pytest.raises(ValidationError) as exc_info:
        config.validate()

    assert "Invalid Python binary name" in str(exc_info.value)


def test_invalid_celery_concurrency_raises_validation_error() -> None:
    """Test that invalid Celery concurrency raises ValidationError."""
    config = CliConfig(celery=CeleryConfig(concurrency=0))

    with pytest.raises(ValidationError) as exc_info:
        config.validate()

    assert "Celery concurrency must be at least 1" in str(exc_info.value)


def test_partial_pyproject_config(tmp_path: Path) -> None:
    """Test that partial pyproject.toml config merges with defaults."""
    (tmp_path / "pyproject.toml").write_text(
        """
[tool.oarepo-cli]
services = { db = "mysql" }
"""
    )

    config = CliConfig.from_pyproject(tmp_path)

    # Only db should be overridden
    assert config.services.db == "mysql"
    assert config.services.search == ServiceType.OPENSEARCH  # Default
    assert config.build.editable is True  # Default


def test_optional_values_in_pyproject(tmp_path: Path) -> None:
    """Test handling of optional values in pyproject.toml."""
    (tmp_path / "pyproject.toml").write_text(
        """
[tool.oarepo-cli]
python = {}
translations = {}
"""
    )

    config = CliConfig.from_pyproject(tmp_path)

    assert config.python.binary is None
    assert config.translations.overlay_dir is None


def test_nested_empty_sections_in_pyproject(tmp_path: Path) -> None:
    """Test handling of empty nested sections in pyproject.toml."""
    (tmp_path / "pyproject.toml").write_text(
        """
[tool.oarepo-cli]
build = {}
test = {}
"""
    )

    config = CliConfig.from_pyproject(tmp_path)

    assert config.build.editable is True  # Default
    assert config.test.coverage is False  # Default
