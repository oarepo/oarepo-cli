# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Integration tests for `repository upgrade` against a real scaffolded repository.

``test_upgrade_removes_venv_and_lock`` and ``test_upgrade_cleans_uv_cache_with_force``
mock out ``repository.install_repository`` (already covered end-to-end by
``test_repository_install.py``) and the actual ``uv cache clean`` invocation
(global, machine-wide state -- not something to exercise for real on every
run) so they run fast and deterministically, per AGENTS.md's guidance to use
fakes for slow external tools rather than real invocations at this layer.
``test_upgrade_reinstalls_successfully`` is the real, slow, end-to-end check
that a full install-then-upgrade cycle actually works.

See tests/conftest.py:testrepo_project for how the fixture repository is
created (via the real ``repository_installer.sh``, as documented at
https://nrp-cz.github.io/docs/installation/create_instance).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from oarepo_cli.cli.main import app
from oarepo_cli.services import process

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator


def test_upgrade_removes_venv_and_lock(
    clean_testrepo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`repository upgrade` removes the existing .venv and uv.lock before reinstalling."""
    monkeypatch.chdir(clean_testrepo)
    monkeypatch.setattr(
        "oarepo_cli.services.repository.install_repository", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(
        "oarepo_cli.services.repository.process.run",
        lambda cmd, **_kwargs: process.ProcessResult(
            return_code=0, stdout="", stderr="", command=cmd, cwd=clean_testrepo, duration_ms=0
        ),
    )

    venv_marker = clean_testrepo / ".venv" / "marker.txt"
    venv_marker.parent.mkdir(parents=True)
    venv_marker.write_text("old venv")
    (clean_testrepo / "uv.lock").write_text("old lock")

    runner = CliRunner()
    result = runner.invoke(app, ["repository", "upgrade", "--quiet"], catch_exceptions=False)

    assert result.exit_code == 0, result.output
    assert not venv_marker.exists()
    assert not (clean_testrepo / "uv.lock").exists()


def test_upgrade_cleans_uv_cache_with_force(
    clean_testrepo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`repository upgrade` runs `uv cache clean --force` (unlike `library upgrade`,
    which omits --force), mirroring repository_runner.sh's upgrade_repository."""
    monkeypatch.chdir(clean_testrepo)
    monkeypatch.setattr(
        "oarepo_cli.services.repository.install_repository", lambda *_args, **_kwargs: None
    )

    calls: list[list[str]] = []

    def spy_run(cmd, **_kwargs):
        calls.append(list(cmd))
        return process.ProcessResult(
            return_code=0, stdout="", stderr="", command=cmd, cwd=clean_testrepo, duration_ms=0
        )

    monkeypatch.setattr("oarepo_cli.services.repository.process.run", spy_run)

    runner = CliRunner()
    result = runner.invoke(app, ["repository", "upgrade", "--quiet"], catch_exceptions=False)

    assert result.exit_code == 0, result.output
    assert ["uv", "cache", "clean", "--force"] in calls


@pytest.fixture(scope="module")
def upgraded_repo(
    testrepo_project: Path, reset_testrepo_state_fn: Callable[[Path], None]
) -> Iterator[Path]:
    """Run a real install then a real `repository upgrade`, once for this module."""
    reset_testrepo_state_fn(testrepo_project)
    previous_cwd = Path.cwd()
    os.chdir(testrepo_project)
    try:
        runner = CliRunner()
        install_result = runner.invoke(app, ["repository", "install"], catch_exceptions=False)
        assert install_result.exit_code == 0, install_result.output

        upgrade_result = runner.invoke(app, ["repository", "upgrade"], catch_exceptions=False)
        assert upgrade_result.exit_code == 0, upgrade_result.output
        yield testrepo_project
    finally:
        os.chdir(previous_cwd)
        reset_testrepo_state_fn(testrepo_project)


def test_upgrade_reinstalls_successfully(upgraded_repo: Path) -> None:
    """Integration test: a full install-then-upgrade cycle completes successfully."""
    assert (upgraded_repo / ".venv" / "bin" / "python").exists()
    assert (upgraded_repo / "uv.lock").exists()
    assert (upgraded_repo / ".invenio.private").exists()
