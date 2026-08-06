# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Shared fixtures for library lint/format/check integration tests."""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

CLEAN_MODULE = """\
# Copyright (c) 2026 Example Org.
#
# This file is a part of cleanlib.

\"\"\"Sample clean module.\"\"\"

from __future__ import annotations


def greet() -> str:
    \"\"\"Return a greeting message.\"\"\"
    return "hello"
"""

PYPROJECT_TOML = """\
[project]
name = "{name}"
version = "0.1.0"
requires-python = ">=3.14,<3.15"
dependencies = ["oarepo>=14.0.0,<15.0.0"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
"""

MULTI_MODULE_PYPROJECT_TOML = """\
[project]
name = "{name}"
version = "0.1.0"
requires-python = ">=3.14,<3.15"
dependencies = ["oarepo>=14.0.0,<15.0.0"]

[tool.uv.build-backend]
module-root = ""
module-name = ["common", "i18n"]

[build-system]
requires = ["uv_build>=0.8.7,<0.9.0"]
build-backend = "uv_build"
"""


@pytest.fixture
def lint_project(tmp_path: Path) -> Path:
    """Create a minimal, lint-clean library project with a real venv.

    Set up as a real git repo with `.venv/` gitignored: ruff (like the
    original bash script's `run_linters`) is invoked with `--exclude
    pyproject.toml` on the CLI, which overrides ruff's built-in default
    excludes, so `.venv/`'s own files would otherwise get linted too --
    exactly as in a real project, this relies on `--respect-gitignore`
    (ruff's default) picking .venv back up from the repo's .gitignore.
    """
    root = tmp_path / "cleanlib"
    (root / "src" / "cleanlib").mkdir(parents=True)
    (root / "pyproject.toml").write_text(PYPROJECT_TOML.format(name="cleanlib"))
    (root / "src" / "cleanlib" / "__init__.py").write_text(CLEAN_MODULE)
    (root / ".gitignore").write_text(".venv/\n")

    subprocess.run(
        ["git", "init"],  # noqa: S607 git is ok
        cwd=root,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["uv", "venv", "--python", "3.14", "--seed", ".venv"],  # noqa: S607 uv is ok
        cwd=root,
        check=True,
        capture_output=True,
    )

    return root


@pytest.fixture
def lint_project_multi_module(tmp_path: Path) -> Path:
    """Create a minimal, lint-clean repository project with a real venv.

    Laid out like a real uv_build repository (tests/testrepo): several
    top-level module directories declared in [tool.uv.build-backend]
    instead of a single src/ -- unlike lint_project's
    library-style single-source-dir layout. See lint_project's own
    docstring for the .gitignore/--exclude pyproject.toml rationale,
    identical here.
    """
    root = tmp_path / "cleanrepo"
    (root / "common").mkdir(parents=True)
    (root / "i18n").mkdir(parents=True)
    (root / "pyproject.toml").write_text(MULTI_MODULE_PYPROJECT_TOML.format(name="cleanrepo"))
    (root / "common" / "__init__.py").write_text(CLEAN_MODULE)
    (root / "i18n" / "__init__.py").write_text(CLEAN_MODULE)
    (root / ".gitignore").write_text(".venv/\n")

    subprocess.run(
        ["git", "init"],  # noqa: S607 git is ok
        cwd=root,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["uv", "venv", "--python", "3.14", "--seed", ".venv"],  # noqa: S607 uv is ok
        cwd=root,
        check=True,
        capture_output=True,
    )

    return root
