# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Application-wide constants."""

from __future__ import annotations

import re

# CESNET GitLab PyPI registry hosting OARepo packages and CESNET-patched
# third-party builds (e.g. invenio-cli with docker-environment patches)
CESNET_PYPI_INDEX_URL = "https://gitlab.cesnet.cz/api/v4/projects/1408/packages/pypi/simple"

# Python versions supported by the CLI (highest first for efficiency)
KNOWN_PYTHON_VERSIONS = ["3.14"]

# OARepo version to compatible Python versions mapping
# Based on the old library_runner.sh implementation
OAREPO_PYTHON_COMPATIBILITY = {
    14: ["3.14"],
    # Add more versions as they become available:
    # 13: ["3.12", "3.13"],
    # 12: ["3.10", "3.11", "3.12"],
}

# Default environment variables for package installation and OARepo operations
# These match the values from the original bash scripts
# Note: Environment variables already set take precedence (not overwritten)
OAREPO_ENV_DEFAULTS = {
    # UV/PIP extra index for OARepo packages (CESNET GitLab PyPI)
    "UV_EXTRA_INDEX_URL": CESNET_PYPI_INDEX_URL,
    "PIP_EXTRA_INDEX_URL": CESNET_PYPI_INDEX_URL,
    # Invenio configuration
    "INVENIO_APP_THEME": '["semantic-ui"]',
    "INVENIO_WEBPACKEXT_NPM_PKG_CLS": "pynpm.package:PNPMPackage",
    "INVENIO_JAVASCRIPT_PACKAGES_MANAGER": "pnpm",
    "INVENIO_ASSETS_BUILDER": "rspack",
    "INVENIO_THEME_FRONTPAGE": "False",
    "INVENIO_THEME_CSS_TEMPLATE": "oarepo_ui/css.html",
    "FLASK_DEBUG": "1",
    # Locale settings
    "LC_TIME": "en_US.UTF-8",
}

# Regex pattern for extracting OARepo major versions from dependency specifiers
OAREPO_VERSION_RE = re.compile(r"oarepo(\d+)")

# File and directory names
ENV_SERVICES_FILE = ".env-services"
VENV_DIR = ".venv"
PYPROJECT_FILE = "pyproject.toml"
UV_LOCK_FILE = "uv.lock"
INVENIO_PRIVATE_FILE = ".invenio.private"


class ServiceType:
    """Service type identifiers for docker-services-cli."""

    POSTGRESQL = "postgresql"
    OPENSEARCH = "opensearch"
    RABBITMQ = "rabbitmq"
    REDIS = "redis"
    MINIO = "minio"
    MYSQL = "mysql"  # Alternative to postgresql
    ELASTICSEARCH = "elasticsearch"  # Alternative to opensearch
