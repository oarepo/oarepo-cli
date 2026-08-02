# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Integration tests for `repository install` against a real scaffolded repository.

Unlike the library integration tests, a full repository install pulls in
invenio-app-rdm and friends, so it is slow (several minutes). The
``installed_repo`` fixture below runs it exactly once per test session and
every test in this module asserts on a distinct side effect of that single
run, matching the checklist in docs/architecture/implementation-steps.md's
Step 4.1: venv synced, translations copied, instance path created,
``.invenio.private`` configured, and the run succeeding end-to-end.

See tests/conftest.py:testrepo_project for how the fixture repository
itself is created (via the real ``repository_installer.sh``, as documented
at https://nrp-cz.github.io/docs/installation/create_instance).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from oarepo_cli.cli.main import app

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator


@pytest.fixture(scope="module")
def installed_repo(
    testrepo_project: Path, reset_testrepo_state_fn: Callable[[Path], None]
) -> Iterator[Path]:
    """Run a real `oarepo-cli repository install` once, shared by this module's tests.

    Uses ``reset_testrepo_state_fn`` (session-scoped) rather than the
    function-scoped ``clean_testrepo``, since a full install is too slow to
    redo for every test function -- see that fixture's docstring.
    """
    reset_testrepo_state_fn(testrepo_project)
    previous_cwd = Path.cwd()
    os.chdir(testrepo_project)
    try:
        runner = CliRunner()
        result = runner.invoke(app, ["repository", "install"], catch_exceptions=False)
        assert result.exit_code == 0, result.output
        yield testrepo_project
    finally:
        os.chdir(previous_cwd)
        reset_testrepo_state_fn(testrepo_project)


def _site_packages(repo: Path) -> Path:
    lib_dir = repo / ".venv" / "lib"
    (python_dir,) = lib_dir.glob("python*")
    return python_dir / "site-packages"


def test_full_install_succeeds(installed_repo: Path) -> None:
    """Integration test: a full `repository install` run completes successfully."""
    assert (installed_repo / ".venv").exists()
    assert (installed_repo / ".venv" / "bin" / "python").exists()


def test_venv_synced(installed_repo: Path) -> None:
    """`uv sync` installed the project's dependencies into .venv, with a lockfile."""
    assert (installed_repo / ".venv" / "bin" / "python").exists()
    assert (installed_repo / "uv.lock").exists()

    # invenio-app-rdm (or an equivalent oarepo-provided package) must actually
    # be installed, not just an empty venv.
    site_packages = _site_packages(installed_repo)
    assert (site_packages / "invenio_app_rdm").is_dir() or (site_packages / "oarepo").is_dir()


def test_translations_copied(installed_repo: Path) -> None:
    """Collected OARepo translations were overlaid onto site-packages."""
    site_packages = _site_packages(installed_repo)
    overlay_source = site_packages / "oarepo" / "collected_translations"
    if not overlay_source.exists():
        pytest.skip("installed oarepo package has no collected_translations to overlay")

    overlaid_items = list(overlay_source.iterdir())
    assert overlaid_items, "collected_translations exists but is empty"
    for item in overlaid_items:
        assert (site_packages / item.name).exists()


def test_instance_path_created(installed_repo: Path) -> None:
    """The Invenio instance directory was created with invenio.cfg symlinked in."""
    instance_path = installed_repo / ".venv" / "var" / "instance"
    assert instance_path.is_dir()

    invenio_cfg_link = instance_path / "invenio.cfg"
    if (installed_repo / "invenio.cfg").exists():
        assert invenio_cfg_link.is_symlink()
        assert invenio_cfg_link.resolve() == (installed_repo / "invenio.cfg").resolve()


def test_invenio_private_configured(installed_repo: Path) -> None:
    """.invenio.private has the local service ports written by configure_local_ports()."""
    invenio_private = installed_repo / ".invenio.private"
    assert invenio_private.exists()

    content = invenio_private.read_text()
    for key in ("search_port", "db_port", "redis_port", "rabbitmq_port", "s3_port", "web_port"):
        assert f"{key} =" in content, f"{key} missing from .invenio.private:\n{content}"
