# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Unit tests for `library venv`/`library install`'s --no-editable argument handling.

The old bash `library_runner.sh` treated `--no-editable` as a flag that
could appear anywhere in argv (`./run.sh --no-editable venv`), not just
after the subcommand name. Typer/Click only accept a command group's own
options before the subcommand name, so `library_callback` (cli/library.py)
also declares `--no-editable` at the group level and `library_venv`/
`library_install` OR it with their own flag. These tests exercise that
argument wiring directly (mocking `_library_venv_impl`, the real venv
creation is covered by tests/integration/test_library_venv.py) rather than
the group-vs-command precedence.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from oarepo_cli.cli.main import app

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

runner = CliRunner()


@pytest.mark.parametrize(
    ("args", "expected_no_editable"),
    [
        (["library", "venv"], False),
        (["library", "venv", "--no-editable"], True),
        (["library", "--no-editable", "venv"], True),
        (["library", "install"], False),
        (["library", "install", "--no-editable"], True),
        (["library", "--no-editable", "install"], True),
    ],
)
def test_no_editable_accepted_before_or_after_subcommand(
    mocker: MockerFixture,
    args: list[str],
    expected_no_editable: bool,
) -> None:
    """Test --no-editable works whether given before or after 'venv'/'install'."""
    impl = mocker.patch("oarepo_cli.cli.library._library_venv_impl")

    result = runner.invoke(app, args, catch_exceptions=False)

    assert result.exit_code == 0, result.stdout
    impl.assert_called_once_with(force=False, no_editable=expected_no_editable, quiet=False)
