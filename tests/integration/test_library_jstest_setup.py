# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Integration tests for `library jstest` setup (both `--setup` and `setup`).

Exercise the CLI wiring end to end -- flag parsing, service handling and the
route into ``setup_jstests`` -- with the heavy webpack/Jest work itself
stubbed. A real setup run needs an installed venv plus node/webpack, too
heavy for this suite (the same reason the underlying `jstest` run path is only
smoke-tested; see test_repository_jslint_jstest.py). The setup logic itself is
unit-tested in tests/unit/test_js_tools.py.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from oarepo_cli.cli.main import app
from oarepo_cli.services import process

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def runner() -> CliRunner:
    """Provide a Typer CLI runner."""
    return CliRunner()


@pytest.mark.parametrize(
    "setup_arg",
    ["--setup", "setup"],
    ids=["flag", "positional"],
)
def test_jstest_setup_routes_to_setup_jstests(
    runner: CliRunner, lint_project: Path, monkeypatch: pytest.MonkeyPatch, setup_arg: str
) -> None:
    """`library jstest {--setup,setup}` runs setup_jstests, not the Jest run path.

    Both spellings must reach setup: the `--setup` flag, and the bare positional
    `setup` alias (kept for now so the shared oarepo CI action can call
    `./run.sh jstest setup`). The positional form used to be swallowed as an
    extra arg and silently ran the Jest run path instead.
    """
    monkeypatch.chdir(lint_project)

    setup_calls: list[bool] = []

    def fake_setup(context: object, *, quiet: bool = False) -> process.ProcessResult:
        setup_calls.append(quiet)
        return process.ProcessResult(return_code=0, stdout="", stderr="", command=[], cwd=lint_project, duration_ms=0)

    monkeypatch.setattr("oarepo_cli.services.js_tools.setup_jstests", fake_setup)
    # Avoid touching Docker services in the test.
    monkeypatch.setattr(
        "oarepo_cli.services.services_lifecycle.ServicesLifecycleManager.load_service_env",
        lambda _self: {},
    )

    result = runner.invoke(app, ["library", "jstest", setup_arg, "--skip-services"], catch_exceptions=False)

    # setup_jstests being called (exactly once) is what proves the setup request
    # reached the setup path rather than being swallowed into the Jest run path.
    assert result.exit_code == 0
    assert setup_calls == [False]
