# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

from __future__ import annotations

from importlib.metadata import PackageNotFoundError

import pytest

from oarepo_cli.core.dependency_check import check_invenio_cli_version
from oarepo_cli.core.errors import VersionMismatchError


def test_accepts_cesnet_patched_version(mocker) -> None:
    mocker.patch(
        "oarepo_cli.core.dependency_check.version",
        return_value="1.12.0+oarepo.1.cgeloxoaidcutj32",
    )
    check_invenio_cli_version()


def test_rejects_upstream_pypi_version(mocker) -> None:
    mocker.patch(
        "oarepo_cli.core.dependency_check.version",
        return_value="1.12.0",
    )
    with pytest.raises(VersionMismatchError, match="upstream PyPI build"):
        check_invenio_cli_version()


def test_rejects_local_version_with_unrelated_prefix(mocker) -> None:
    mocker.patch(
        "oarepo_cli.core.dependency_check.version",
        return_value="1.12.0+somethingelse.1",
    )
    with pytest.raises(VersionMismatchError, match="upstream PyPI build"):
        check_invenio_cli_version()


def test_rejects_uninstalled_package(mocker) -> None:
    mocker.patch(
        "oarepo_cli.core.dependency_check.version",
        side_effect=PackageNotFoundError("invenio-cli"),
    )
    with pytest.raises(VersionMismatchError, match="is not installed"):
        check_invenio_cli_version()


def test_rejects_unparseable_version(mocker) -> None:
    mocker.patch(
        "oarepo_cli.core.dependency_check.version",
        return_value="not-a-version",
    )
    with pytest.raises(VersionMismatchError, match="upstream PyPI build"):
        check_invenio_cli_version()


def test_error_message_points_to_cesnet_registry(mocker) -> None:
    mocker.patch(
        "oarepo_cli.core.dependency_check.version",
        return_value="1.12.0",
    )
    with pytest.raises(VersionMismatchError, match="gitlab.cesnet.cz"):
        check_invenio_cli_version()
