# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Top-level pytest fixtures for oarepo-cli tests."""

from __future__ import annotations

import contextlib
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

from oarepo_cli.core.config import CliConfig, ServicesConfig, TestingConfig
from oarepo_cli.core.context import ProjectContext
from oarepo_cli.core.platform import get_platform_detector
from oarepo_cli.services.services_lifecycle import ServicesLifecycleManager

# https://raw.githubusercontent.com/oarepo/oarepo/refs/heads/main/tools/repository_installer.sh
# creates a real repository from the nrp-app-copier template, as documented at
# https://nrp-cz.github.io/docs/installation/create_instance
REPOSITORY_INSTALLER_URL = (
    "https://raw.githubusercontent.com/oarepo/oarepo/refs/heads/main/tools/repository_installer.sh"
)

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
    venv_path = testlib_project / ".venv"
    env_services = testlib_project / ".env-services"
    uv_lock = testlib_project / "uv.lock"
    coverage_files = list(testlib_project.glob(".coverage*"))
    htmlcov = testlib_project / "htmlcov"
    dist = testlib_project / "dist"
    build = testlib_project / "build"

    # Various test venv directories that may be created by tests (cleanup these too)
    test_venvs = [
        testlib_project.parent / "testlib_test_venv",
        testlib_project.parent / "testlib_cleanup_test_venv",
        testlib_project.parent / "testlib_full_cleanup_venv",
        testlib_project.parent / "testlib_failure_test_venv",
        testlib_project.parent / "testlib_full_test_venv",
    ]

    # Stop services if running
    config = CliConfig()
    config.services = ServicesConfig(skip=False)
    services_mgr = ServicesLifecycleManager(config=config, project_root=testlib_project)

    if services_mgr.are_services_running():
        with contextlib.suppress(Exception):
            services_mgr.stop_services()

    # Remove artifacts
    if venv_path.exists():
        shutil.rmtree(venv_path)
    if env_services.exists():
        env_services.unlink()
    if uv_lock.exists():
        uv_lock.unlink()
    for f in coverage_files:
        f.unlink()
    if htmlcov.exists():
        shutil.rmtree(htmlcov)
    if dist.exists():
        shutil.rmtree(dist)
    if build.exists():
        shutil.rmtree(build)
    for venv_dir in test_venvs:
        if venv_dir.exists():
            shutil.rmtree(venv_dir)

    # Remove __pycache__ directories
    for pycache in testlib_project.rglob("__pycache__"):
        shutil.rmtree(pycache)

    yield testlib_project

    # Clean up after test
    if venv_path.exists():
        shutil.rmtree(venv_path)
    if env_services.exists():
        env_services.unlink()
    if uv_lock.exists():
        uv_lock.unlink()
    for f in testlib_project.glob(".coverage*"):
        f.unlink()
    if htmlcov.exists():
        shutil.rmtree(htmlcov)
    for venv_dir in test_venvs:
        if venv_dir.exists():
            shutil.rmtree(venv_dir)


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
    it's created on demand, once, via the real installer described at
    https://nrp-cz.github.io/docs/installation/create_instance -- the same
    ``repository_installer.sh`` a user would run, driving the
    ``nrp-app-copier`` template through ``copier``. If ``tests/testrepo``
    already exists (from a previous run), creation is skipped entirely and
    the cached scaffold is reused, since generation itself is slow
    (network + copier) even before ``repository install`` runs anything.
    """
    root = Path(__file__).parent / "testrepo"
    if (root / "pyproject.toml").exists():
        return root

    root.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        installer = tmp_path / "repository_installer.sh"
        subprocess.run(
            ["curl", "-fsSL", "-o", str(installer), REPOSITORY_INSTALLER_URL],
            check=True,
        )
        installer.chmod(0o755)

        config_file = tmp_path / "repo_config.yaml"
        config_file.write_text(REPOSITORY_CONFIG_YAML)

        # macOS ships bash 3.2 as /bin/bash (frozen for licensing reasons),
        # which mishandles the script's `"${@}"` expansion under `set -u`
        # when called with zero arguments. Same issue and fix as
        # PlatformDetector.get_default_shell().
        subprocess.run(
            [
                get_platform_detector().get_default_shell(),
                str(installer),
                "--python",
                "python3.14",
                "--config",
                str(config_file),
                root.name,
            ],
            cwd=root.parent,
            check=True,
        )

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
