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


@pytest.fixture
def lint_project(tmp_path: Path) -> Path:
    """A minimal, lint-clean library project with a real venv.

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

    subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
    subprocess.run(
        ["uv", "venv", "--python", "3.14", "--seed", ".venv"],
        cwd=root,
        check=True,
        capture_output=True,
    )

    return root
