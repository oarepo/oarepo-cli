# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Tests for oarepo_cli.core.dependency_check."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError

import pytest

from oarepo_cli.core.dependency_check import check_invenio_cli_version
from oarepo_cli.core.errors import VersionMismatchError


def test_accepts_cesnet_patched_version(mocker) -> None:
    """A CESNET-patched invenio-cli version (the expected local segment) passes."""
    mocker.patch(
        "oarepo_cli.core.dependency_check.version",
        return_value="1.12.0+oarepo.1.cgeloxoaidcutj32",
    )
    check_invenio_cli_version()


def test_rejects_upstream_pypi_version(mocker) -> None:
    """A plain upstream invenio-cli version (no CESNET local segment) is rejected."""
    mocker.patch(
        "oarepo_cli.core.dependency_check.version",
        return_value="1.12.0",
    )
    with pytest.raises(VersionMismatchError, match="upstream PyPI build"):
        check_invenio_cli_version()


def test_rejects_local_version_with_unrelated_prefix(mocker) -> None:
    """A local version segment that isn't the "oarepo" prefix is still rejected."""
    mocker.patch(
        "oarepo_cli.core.dependency_check.version",
        return_value="1.12.0+somethingelse.1",
    )
    with pytest.raises(VersionMismatchError, match="upstream PyPI build"):
        check_invenio_cli_version()


def test_rejects_uninstalled_package(mocker) -> None:
    """A missing invenio-cli install is reported clearly, not as a raw ImportError."""
    mocker.patch(
        "oarepo_cli.core.dependency_check.version",
        side_effect=PackageNotFoundError("invenio-cli"),
    )
    with pytest.raises(VersionMismatchError, match="is not installed"):
        check_invenio_cli_version()


def test_rejects_unparseable_version(mocker) -> None:
    """A version string packaging.version can't parse is treated as not CESNET-patched."""
    mocker.patch(
        "oarepo_cli.core.dependency_check.version",
        return_value="not-a-version",
    )
    with pytest.raises(VersionMismatchError, match="upstream PyPI build"):
        check_invenio_cli_version()


def test_error_message_points_to_cesnet_registry(mocker) -> None:
    """The rejection error tells the user where to install the correct build from."""
    mocker.patch(
        "oarepo_cli.core.dependency_check.version",
        return_value="1.12.0",
    )
    with pytest.raises(VersionMismatchError, match="gitlab.cesnet.cz"):
        check_invenio_cli_version()
