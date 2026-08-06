# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Typed configuration from environment variables and pyproject.toml."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from oarepo_cli.configuration.constants import VENV_DIR, ServiceType


@dataclass
class BuildConfig:
    """Build configuration."""

    editable: bool = True


@dataclass
class TestingConfig:
    """Testing configuration."""

    coverage: bool = False
    skip_services: bool = False


@dataclass
class VenvConfig:
    """Virtual environment configuration."""

    path: Path = field(default_factory=lambda: Path(VENV_DIR))


@dataclass
class PythonConfig:
    """Python interpreter configuration."""

    binary: str | None = None  # None = auto-detect


@dataclass
class OARepoConfig:
    """OARepo version configuration."""

    version: int | None = None  # None = first from pyproject.toml


@dataclass
class ServicesConfig:
    """Services configuration."""

    skip: bool = False
    db: str = ServiceType.POSTGRESQL
    search: str = ServiceType.OPENSEARCH
    mq: str = ServiceType.RABBITMQ
    cache: str = ServiceType.REDIS
    s3: str = ServiceType.MINIO


@dataclass
class ModelConfig:
    """Model manager configuration."""

    template_url: str = "https://github.com/oarepo/nrp-model-copier"
    template_version: str = "rdm-14"


@dataclass
class TranslationsConfig:
    """Translations configuration."""

    overlay_dir: Path | None = None


@dataclass
class CeleryConfig:
    """Celery worker configuration."""

    pool_type: str = "threads"  # macOS workaround
    concurrency: int = 10


@dataclass
class LicenseConfig:
    """License header configuration."""

    organization: str = "CESNET z.s.p.o"


@dataclass
class SecurityConfig:
    """Security configuration."""

    demo_user_password: str = "123456"  # Warn if not changed


def _get_bool(env_var: str, default: bool) -> bool:
    """Get boolean from environment variable."""
    return os.getenv(env_var, str(default).lower()).lower() == "true"


def _get_int(env_var: str, default: int) -> int:
    """Get integer from environment variable."""
    try:
        return int(os.getenv(env_var, str(default)))
    except ValueError:
        return default


def _get_str(env_var: str, default: str) -> str:
    """Get string from environment variable."""
    return os.getenv(env_var, default) or default


@dataclass
class CliConfig:
    """Complete CLI configuration.

    Configuration is loaded from multiple sources with the following precedence:
    defaults < pyproject.toml < environment variables < CLI flags
    """

    build: BuildConfig = field(default_factory=BuildConfig)
    test: TestingConfig = field(default_factory=TestingConfig)
    venv: VenvConfig = field(default_factory=VenvConfig)
    python: PythonConfig = field(default_factory=PythonConfig)
    oarepo: OARepoConfig = field(default_factory=OARepoConfig)
    services: ServicesConfig = field(default_factory=ServicesConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    translations: TranslationsConfig = field(default_factory=TranslationsConfig)
    celery: CeleryConfig = field(default_factory=CeleryConfig)
    license: LicenseConfig = field(default_factory=LicenseConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)

    @classmethod
    def from_env(cls) -> CliConfig:
        """Create configuration from environment variables only.

        Returns:
            CliConfig with values from environment variables or defaults

        """
        return cls(
            build=BuildConfig(editable=_get_bool("OAREPO_BUILD_EDITABLE", True)),
            test=TestingConfig(
                coverage=_get_bool("OAREPO_TEST_COVERAGE", False),
                skip_services=_get_bool("OAREPO_TEST_SKIP_SERVICES", False),
            ),
            venv=VenvConfig(path=Path(_get_str("OAREPO_VENV_PATH", VENV_DIR))),
            python=PythonConfig(binary=_get_str("OAREPO_PYTHON_BINARY", "") or None),
            oarepo=OARepoConfig(
                version=_get_int("OAREPO_VERSION", 0) or None,
            ),
            services=ServicesConfig(
                skip=_get_bool("OAREPO_SERVICES_SKIP", False),
                db=_get_str("OAREPO_SERVICES_DB", ServiceType.POSTGRESQL),
                search=_get_str("OAREPO_SERVICES_SEARCH", ServiceType.OPENSEARCH),
                mq=_get_str("OAREPO_SERVICES_MQ", ServiceType.RABBITMQ),
                cache=_get_str("OAREPO_SERVICES_CACHE", ServiceType.REDIS),
                s3=_get_str("OAREPO_SERVICES_S3", ServiceType.MINIO),
            ),
            model=ModelConfig(
                template_url=_get_str(
                    "OAREPO_MODEL_TEMPLATE_URL",
                    "https://github.com/oarepo/nrp-model-copier",
                ),
                template_version=_get_str("OAREPO_MODEL_TEMPLATE_VERSION", "rdm-14"),
            ),
            translations=TranslationsConfig(
                overlay_dir=(
                    Path(_get_str("OAREPO_TRANSLATIONS_OVERLAY", ""))
                    if os.getenv("OAREPO_TRANSLATIONS_OVERLAY")
                    else None
                )
            ),
            celery=CeleryConfig(
                pool_type=_get_str("OAREPO_CELERY_POOL_TYPE", "threads"),
                concurrency=_get_int("OAREPO_CELERY_CONCURRENCY", 10),
            ),
            license=LicenseConfig(organization=_get_str("OAREPO_LICENSE_ORG", "CESNET z.s.p.o")),
            security=SecurityConfig(
                demo_user_password=_get_str("DEMO_USER_PASSWORD", "123456"),
            ),
        )

    @classmethod
    def from_pyproject(cls, root: Path) -> CliConfig:
        """Create configuration from pyproject.toml [tool.oarepo-cli] section.

        Args:
            root: Root directory containing pyproject.toml

        Returns:
            CliConfig with values from pyproject.toml or defaults

        """
        pyproject_path = root / "pyproject.toml"

        if not pyproject_path.exists():
            return cls()

        content = pyproject_path.read_text(encoding="utf-8")

        try:
            data = tomllib.loads(content)
        except tomllib.TOMLDecodeError as exc:
            from oarepo_cli.core.errors import ValidationError

            raise ValidationError(f"Invalid TOML in {pyproject_path}: {exc}") from exc

        tool_data = data.get("tool", {}).get("oarepo-cli", {})

        def get_nested(d: dict[str, Any], *keys: str, default: Any = None) -> Any:
            """Get nested dictionary value safely."""
            for key in keys:
                if isinstance(d, dict):
                    d = d.get(key, {})
                else:
                    return default
            return d if d is not None else default

        # Build config
        build_data = get_nested(tool_data, "build", default={})
        build = BuildConfig(editable=build_data.get("editable", True))

        # Testing config
        test_data = get_nested(tool_data, "test", default={})
        test = TestingConfig(
            coverage=test_data.get("coverage", False),
            skip_services=test_data.get("skip_services", False),
        )

        # Venv config
        venv_data = get_nested(tool_data, "venv", default={})
        venv_path = venv_data.get("path", VENV_DIR)
        venv = VenvConfig(path=Path(venv_path) if venv_path else Path(VENV_DIR))

        # Python config
        python_data = get_nested(tool_data, "python", default={})
        python_binary = python_data.get("binary")
        python = PythonConfig(binary=python_binary or None)

        # OARepo version is deliberately never read from pyproject.toml here:
        # [tool.oarepo-cli].oarepo.version is deprecated (see
        # PyProjectData.oarepo_versions's own warning) -- the version is
        # extracted from [project].dependencies instead, with OAREPO_VERSION
        # (from_env(), merged over this) as the only remaining override.
        oarepo = OARepoConfig()

        # Services config
        services_data = get_nested(tool_data, "services", default={})
        services = ServicesConfig(
            skip=services_data.get("skip", False),
            db=services_data.get("db", ServiceType.POSTGRESQL),
            search=services_data.get("search", ServiceType.OPENSEARCH),
            mq=services_data.get("mq", ServiceType.RABBITMQ),
            cache=services_data.get("cache", ServiceType.REDIS),
            s3=services_data.get("s3", ServiceType.MINIO),
        )

        # Model config
        model_data = get_nested(tool_data, "model", default={})
        model = ModelConfig(
            template_url=model_data.get("template_url", "https://github.com/oarepo/nrp-model-copier"),
            template_version=model_data.get("template_version", "rdm-14"),
        )

        # Translations config
        translations_data = get_nested(tool_data, "translations", default={})
        overlay_dir = translations_data.get("overlay_dir")
        translations = TranslationsConfig(overlay_dir=Path(overlay_dir) if overlay_dir else None)

        # Celery config
        celery_data = get_nested(tool_data, "celery", default={})
        celery = CeleryConfig(
            pool_type=celery_data.get("pool_type", "threads"),
            concurrency=int(celery_data.get("concurrency", 10)),
        )

        # License config
        license_data = get_nested(tool_data, "license", default={})
        license_config = LicenseConfig(organization=license_data.get("organization", "CESNET z.s.p.o"))

        # Security config
        security_data = get_nested(tool_data, "security", default={})
        security = SecurityConfig(
            demo_user_password=security_data.get("demo_user_password", "123456"),
        )

        return cls(
            build=build,
            test=test,
            venv=venv,
            python=python,
            oarepo=oarepo,
            services=services,
            model=model,
            translations=translations,
            celery=celery,
            license=license_config,
            security=security,
        )

    @classmethod
    def merge(cls, configs: list[CliConfig]) -> CliConfig:
        """Merge multiple configurations with rightmost taking precedence.

        Args:
            configs: List of configurations to merge (lowest to highest priority)

        Returns:
            Merged CliConfig

        """
        if not configs:
            return cls()

        # Pre-compute default values for comparison
        default_build = BuildConfig()
        default_test = TestingConfig()
        default_venv = VenvConfig()
        default_services = ServicesConfig()
        default_model = ModelConfig()
        default_celery = CeleryConfig()
        default_license = LicenseConfig()
        default_security = SecurityConfig()

        # Start with defaults
        result = cls()

        for config in configs:
            # Merge each nested config - prefer non-default values from config
            result = CliConfig(
                build=BuildConfig(
                    editable=config.build.editable
                    if config.build.editable != default_build.editable
                    else result.build.editable,
                ),
                test=TestingConfig(
                    coverage=config.test.coverage
                    if config.test.coverage != default_test.coverage
                    else result.test.coverage,
                    skip_services=config.test.skip_services
                    if config.test.skip_services != default_test.skip_services
                    else result.test.skip_services,
                ),
                venv=VenvConfig(
                    path=config.venv.path if config.venv.path != default_venv.path else result.venv.path,
                ),
                python=PythonConfig(
                    binary=config.python.binary if config.python.binary is not None else result.python.binary,
                ),
                oarepo=OARepoConfig(
                    version=config.oarepo.version if config.oarepo.version is not None else result.oarepo.version,
                ),
                services=ServicesConfig(
                    skip=config.services.skip
                    if config.services.skip != default_services.skip
                    else result.services.skip,
                    db=config.services.db if config.services.db != default_services.db else result.services.db,
                    search=config.services.search
                    if config.services.search != default_services.search
                    else result.services.search,
                    mq=config.services.mq if config.services.mq != default_services.mq else result.services.mq,
                    cache=config.services.cache
                    if config.services.cache != default_services.cache
                    else result.services.cache,
                    s3=config.services.s3 if config.services.s3 != default_services.s3 else result.services.s3,
                ),
                model=ModelConfig(
                    template_url=config.model.template_url
                    if config.model.template_url != default_model.template_url
                    else result.model.template_url,
                    template_version=config.model.template_version
                    if config.model.template_version != default_model.template_version
                    else result.model.template_version,
                ),
                translations=TranslationsConfig(
                    overlay_dir=config.translations.overlay_dir
                    if config.translations.overlay_dir is not None
                    else result.translations.overlay_dir,
                ),
                celery=CeleryConfig(
                    pool_type=config.celery.pool_type
                    if config.celery.pool_type != default_celery.pool_type
                    else result.celery.pool_type,
                    concurrency=config.celery.concurrency
                    if config.celery.concurrency != default_celery.concurrency
                    else result.celery.concurrency,
                ),
                license=LicenseConfig(
                    organization=config.license.organization
                    if config.license.organization != default_license.organization
                    else result.license.organization,
                ),
                security=SecurityConfig(
                    demo_user_password=config.security.demo_user_password
                    if config.security.demo_user_password != default_security.demo_user_password
                    else result.security.demo_user_password,
                ),
            )

        return result

    def validate(self) -> None:
        """Validate the configuration.

        Raises:
            ValidationError: If any configuration value is invalid

        """
        from oarepo_cli.core.errors import ValidationError

        # Validate Python binary name if specified
        if self.python.binary and not self.python.binary.startswith("python"):
            raise ValidationError(
                f"Invalid Python binary name: {self.python.binary}. Should start with 'python' (e.g., 'python3.12')"
            )

        # Validate Celery concurrency
        if self.celery.concurrency < 1:
            raise ValidationError(f"Celery concurrency must be at least 1, got {self.celery.concurrency}")

        # Warn about default demo password (not an error, just validation)
        if self.security.demo_user_password == "123456":
            import warnings

            warnings.warn(
                "Using default demo user password. Consider changing DEMO_USER_PASSWORD",
                UserWarning,
                stacklevel=2,
            )
