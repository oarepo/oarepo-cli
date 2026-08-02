# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Top-level pytest fixtures for oarepo-cli tests."""

from __future__ import annotations

import contextlib
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator

from oarepo_cli.core.config import CliConfig, ServicesConfig, TestingConfig
from oarepo_cli.core.context import ProjectContext
from oarepo_cli.services.services_lifecycle import ServicesLifecycleManager


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
    - .coverage files
    - __pycache__ directories
    - Any other test artifacts

    Also ensures services are stopped if running.
    """
    venv_path = testlib_project / ".venv"
    env_services = testlib_project / ".env-services"
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
