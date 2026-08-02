# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Startup checks for third-party dependencies that require CESNET patches."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from packaging.version import InvalidVersion, Version

from oarepo_cli.configuration.constants import CESNET_PYPI_INDEX_URL
from oarepo_cli.core.errors import VersionMismatchError

# The CESNET-patched build publishes a PEP 440 local version segment that
# starts with "oarepo", e.g. "1.12.0+oarepo.1.cgeloxoaidcutj32".
INVENIO_CLI_LOCAL_VERSION_PREFIX = "oarepo"


def check_invenio_cli_version() -> None:
    """Ensure the installed invenio-cli is the CESNET-patched build.

    oarepo-cli depends on CESNET-specific patches to invenio-cli (docker
    environment handling, extension hooks, custom cert paths, ...) that are
    not part of the upstream PyPI release. If the vanilla upstream package
    ends up installed instead (e.g. resolved from PyPI rather than the
    CESNET registry), those features silently misbehave, so this is checked
    at startup rather than left to fail later in unrelated commands.

    Raises:
        VersionMismatchError: If invenio-cli is missing or is not a
            CESNET-patched build.
    """
    try:
        installed_version = version("invenio-cli")
    except PackageNotFoundError as exc:
        raise VersionMismatchError(
            "invenio-cli is not installed. Install the CESNET-patched build "
            f"from {CESNET_PYPI_INDEX_URL}"
        ) from exc

    try:
        parsed_version = Version(installed_version)
    except InvalidVersion:
        parsed_version = None

    local_segment = parsed_version.local if parsed_version else None
    if local_segment and local_segment.startswith(INVENIO_CLI_LOCAL_VERSION_PREFIX):
        return

    raise VersionMismatchError(
        f"Installed invenio-cli version '{installed_version}' is the upstream PyPI "
        "build, but oarepo-cli requires the CESNET-patched build (its version looks "
        f"like '1.12.0+{INVENIO_CLI_LOCAL_VERSION_PREFIX}.1.cgeloxoaidcutj32'). "
        f"Install it from {CESNET_PYPI_INDEX_URL}"
    )
