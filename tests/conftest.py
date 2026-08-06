# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Top-level pytest fixtures for oarepo-cli tests."""

from __future__ import annotations

import contextlib
import os
import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

from oarepo_cli.cli.main import app
from oarepo_cli.core.config import CliConfig, ServicesConfig, TestingConfig
from oarepo_cli.core.context import ProjectContext
from oarepo_cli.services.services_lifecycle import ServicesLifecycleManager

# Rich/Click's help-text renderer falls back to os.get_terminal_size() on the
# real stdout/stderr file descriptors, which typer.testing.CliRunner.invoke()
# doesn't redirect (it only swaps the Python-level sys.stdout object) -- so
# on a CI runner whose job step has no controlling terminal (or one reporting
# a degenerate size), `--help` output can wrap down to almost nothing --
# observed on GitHub Actions as help panels rendering as an empty box with no
# visible option text at all (COLUMNS/LINES of "1" reproduces this exactly
# locally). Rich/Click both prefer the COLUMNS/LINES env vars over that OS
# query when set, so pinning them here makes every CliRunner-rendered help
# text deterministic across environments -- unconditionally, not just
# `setdefault`, since a CI environment that already exports a degenerate
# COLUMNS/LINES value is exactly the failure case this works around.
os.environ["COLUMNS"] = "200"
os.environ["LINES"] = "50"


def _cleanup_testlib(project_path: Path, stop_services: bool = True) -> None:
    """Clean up testlib project directory.

    Args:
        project_path: Path to the testlib project
        stop_services: Whether to stop running services first

    """
    if stop_services:
        _stop_services(project_path)

    # Remove artifacts
    _remove_venv(project_path / ".venv")
    _remove_if_exists(project_path / ".env-services")
    _remove_if_exists(project_path / "uv.lock")
    _remove_coverage_files(project_path)
    _remove_if_exists(project_path / "htmlcov")
    _remove_if_exists(project_path / "dist")
    _remove_if_exists(project_path / "build")
    _remove_test_venvs(project_path)
    _remove_pycache_directories(project_path)


def _stop_services(project_path: Path) -> None:
    """Stop services if they are running.

    Args:
        project_path: Path to the project

    """
    config = CliConfig()
    config.services = ServicesConfig(skip=False)
    services_mgr = ServicesLifecycleManager(config=config, project_root=project_path)

    if services_mgr.are_services_running():
        with contextlib.suppress(Exception):
            services_mgr.stop_services()


def _remove_venv(venv_path: Path) -> None:
    """Remove venv directory if it exists.

    Args:
        venv_path: Path to the venv directory

    """
    if venv_path.exists():
        shutil.rmtree(venv_path)


def _remove_if_exists(path: Path) -> None:
    """Remove a file or directory if it exists.

    Args:
        path: Path to remove

    """
    if path.exists():
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()


def _remove_coverage_files(project_path: Path) -> None:
    """Remove coverage files from project directory.

    Args:
        project_path: Path to the project

    """
    for f in project_path.glob(".coverage*"):
        f.unlink()


def _remove_test_venvs(project_path: Path) -> None:
    """Remove test venv directories.

    Args:
        project_path: Path to the project

    """
    test_venvs = [
        project_path.parent / "testlib_test_venv",
        project_path.parent / "testlib_cleanup_test_venv",
        project_path.parent / "testlib_full_cleanup_venv",
        project_path.parent / "testlib_failure_test_venv",
        project_path.parent / "testlib_full_test_venv",
    ]
    for venv_dir in test_venvs:
        _remove_venv(venv_dir)


def _remove_pycache_directories(project_path: Path) -> None:
    """Remove __pycache__ directories recursively.

    Args:
        project_path: Path to the project

    """
    for pycache in project_path.rglob("__pycache__"):
        shutil.rmtree(pycache)


REPOSITORY_CONFIG_YAML = """\
repository_human_name: Test Repository
repository_description: Integration test repository for oarepo-cli
languages: cs
use_ccmm: false
"""


@pytest.fixture
def testlib_project() -> Path:
    """Path to the testlib fixture project."""
    return Path(__file__).parent / "testlib"


@pytest.fixture
def clean_testlib(testlib_project: Path) -> Iterator[Path]:
    """Clean up testlib before and after each test.

    Removes:
    - .venv directory (inside testlib)
    - .env-services file
    - uv.lock file
    - .coverage files
    - __pycache__ directories
    - Any other test artifacts

    Also ensures services are stopped if running.
    """
    # Setup: stop services and clean up before test
    _cleanup_testlib(testlib_project, stop_services=True)

    yield testlib_project

    # Teardown: clean up after test
    _cleanup_testlib(testlib_project, stop_services=True)


@pytest.fixture
def test_context(clean_testlib: Path) -> ProjectContext:
    """Create a test project context using testlib with .venv inside testlib."""
    config = CliConfig()
    config.test = TestingConfig(coverage=False, skip_services=False)
    config.services = ServicesConfig(skip=False)

    # Use .venv inside testlib directory (cleaned up by clean_testlib fixture)
    venv_path = clean_testlib / ".venv"

    return ProjectContext(
        root_directory=clean_testlib,
        pyproject_path=clean_testlib / "pyproject.toml",
        venv_path=venv_path,
        python_binary=venv_path / "bin" / "python",
        oarepo_version=14,
        config=config,
    )


@pytest.fixture(scope="session")
def testrepo_project() -> Path:
    """Path to a real, scaffolded Invenio RDM repository for repository-install tests.

    Unlike ``testlib_project`` (a small, hand-written fixture committed to
    the repo), a real repository is too large and heavyweight (its own
    nested git repo, generated docker/i18n/UI assets) to commit. Instead
    it's created on demand, once, via ``oarepo-cli new`` itself -- the same
    scaffolding operation (``nrp-app-copier`` template through ``copier``)
    a user would run, exercised in-process through ``CliRunner`` rather
    than downloading and shelling out to ``repository_installer.sh``. If
    ``tests/testrepo`` already exists (from a previous run), creation is
    skipped entirely and the cached scaffold is reused, since generation
    itself is slow (network + copier) even before ``repository install``
    runs anything.
    """
    root = Path(__file__).parent / "testrepo"
    if (root / "pyproject.toml").exists():
        return root

    root.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        config_file = Path(tmp) / "repo_config.yaml"
        config_file.write_text(REPOSITORY_CONFIG_YAML)

        cwd = Path.cwd()
        os.chdir(root.parent)
        try:
            result = CliRunner().invoke(
                app,
                ["new", "--config", str(config_file), root.name],
                catch_exceptions=False,
            )
        finally:
            os.chdir(cwd)

    if result.exit_code != 0:
        msg = f"Failed to create testrepo fixture via 'oarepo-cli new':\n{result.output}"
        raise RuntimeError(msg)

    return root


def reset_testrepo_state(testrepo_project: Path) -> None:
    """Remove everything a `repository install`/`services` run generates.

    Removes ``.venv``, ``uv.lock``, ``.invenio.private``, the rendered
    Invenio instance directory, ``.env-services``, and the ``docker/.env``
    symlink invenio-cli's install step creates -- while leaving the real
    scaffolded project (``pyproject.toml``, ``invenio.cfg``, ``variables``,
    docker compose files, ...) untouched. Plain function (not a fixture) so
    it can be reused at whatever fixture scope a given test module needs --
    see ``clean_testrepo`` (function scope) and
    ``tests/integration/test_repository_install.py``'s ``installed_repo``
    (module scope, since a full install is too slow to redo per test).
    """
    venv_path = testrepo_project / ".venv"
    uv_lock = testrepo_project / "uv.lock"
    invenio_private = testrepo_project / ".invenio.private"
    env_services = testrepo_project / ".env-services"
    docker_env = testrepo_project / "docker" / ".env"

    config = CliConfig()
    config.services = ServicesConfig(skip=False)
    services_mgr = ServicesLifecycleManager(config=config, project_root=testrepo_project)
    if services_mgr.are_services_running():
        with contextlib.suppress(Exception):
            services_mgr.stop_services()

    if venv_path.exists():
        shutil.rmtree(venv_path)
    if uv_lock.exists():
        uv_lock.unlink()
    if invenio_private.exists():
        invenio_private.unlink()
    if env_services.exists():
        env_services.unlink()
    if docker_env.exists() or docker_env.is_symlink():
        docker_env.unlink()
    for pycache in testrepo_project.rglob("__pycache__"):
        shutil.rmtree(pycache, ignore_errors=True)


@pytest.fixture
def clean_testrepo(testrepo_project: Path) -> Iterator[Path]:
    """Reset testrepo_project's install-generated state before and after each test.

    See ``reset_testrepo_state`` for exactly what's removed.
    """
    reset_testrepo_state(testrepo_project)
    yield testrepo_project
    reset_testrepo_state(testrepo_project)


@pytest.fixture(scope="session")
def reset_testrepo_state_fn() -> Callable[[Path], None]:
    """Session-scoped fixture handle for ``reset_testrepo_state``.

    Lets test modules that need a broader-than-function fixture scope (e.g.
    a module-scoped "run this expensive command once" fixture, which can't
    depend on the function-scoped ``clean_testrepo``) reuse the same reset
    logic via normal fixture injection, instead of ``from tests.conftest
    import reset_testrepo_state`` -- an absolute ``tests.*`` import that
    breaks pytest's rootdir-based collection once combined with the nested
    ``tests/testlib/tests/`` directory (both resolve to a top-level `tests`
    package/namespace, and Python's import system doesn't like it: manifests
    as ``ModuleNotFoundError: No module named 'tests.test_sample'``).
    """
    return reset_testrepo_state
