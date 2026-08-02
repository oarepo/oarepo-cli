# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Integration tests for library lint/format commands using real ruff/mypy/pyright."""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from oarepo_cli.cli.main import app
from oarepo_cli.services.lint import check_future_annotations, check_license_headers

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

[tool.oarepo-cli]
oarepo = {{ version = 14 }}

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
"""


@pytest.fixture
def runner() -> CliRunner:
    """Provide a Typer CLI runner."""
    return CliRunner()


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


def test_lint_help_displays(runner: CliRunner) -> None:
    """Test that 'library lint --help' displays help text."""
    result = runner.invoke(app, ["library", "lint", "--help"])

    assert result.exit_code == 0
    assert "lint" in result.stdout.lower()


def test_format_help_displays(runner: CliRunner) -> None:
    """Test that 'library format --help' displays help text."""
    result = runner.invoke(app, ["library", "format", "--help"])

    assert result.exit_code == 0
    assert "format" in result.stdout.lower()


def test_lint_passes_on_clean_code(
    runner: CliRunner, lint_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that 'library lint' exits 0 on a clean project."""
    monkeypatch.chdir(lint_project)

    result = runner.invoke(app, ["library", "lint", "--quiet"], catch_exceptions=False)

    assert result.exit_code == 0
    assert (lint_project / ".ruff.toml").exists()
    assert (lint_project / ".mypy.ini").exists()


def test_lint_fails_on_dirty_code(
    runner: CliRunner, lint_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that 'library lint' exits non-zero when ruff finds an issue."""
    monkeypatch.chdir(lint_project)

    # Introduce an unused import - a ruff violation.
    module = lint_project / "src" / "cleanlib" / "__init__.py"
    module.write_text(module.read_text() + "\nimport os\n")

    result = runner.invoke(app, ["library", "lint", "--quiet"], catch_exceptions=False)

    assert result.exit_code != 0


def test_lint_fails_when_license_header_missing(
    runner: CliRunner, lint_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that 'library lint' exits non-zero when a file has no license header."""
    monkeypatch.chdir(lint_project)

    module = lint_project / "src" / "cleanlib" / "__init__.py"
    module.write_text(
        '"""Sample clean module."""\n\nfrom __future__ import annotations\n\n\ndef greet() -> str:\n'
        '    """Return a greeting message."""\n    return "hello"\n'
    )

    result = runner.invoke(app, ["library", "lint", "--quiet"], catch_exceptions=False)

    assert result.exit_code != 0


def test_lint_fails_when_future_annotations_missing(
    runner: CliRunner, lint_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that 'library lint' exits non-zero when a file lacks future annotations."""
    monkeypatch.chdir(lint_project)

    module = lint_project / "src" / "cleanlib" / "__init__.py"
    module.write_text(
        "# Copyright (c) 2026 Example Org.\n\n"
        '"""Sample clean module."""\n\n\n'
        "def greet() -> str:\n"
        '    """Return a greeting message."""\n'
        '    return "hello"\n'
    )

    result = runner.invoke(app, ["library", "lint", "--quiet"], catch_exceptions=False)

    assert result.exit_code != 0


def test_format_fixes_issues(
    runner: CliRunner, lint_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that 'library format' rewrites badly-formatted code via ruff."""
    monkeypatch.chdir(lint_project)

    module = lint_project / "src" / "cleanlib" / "__init__.py"
    dirty = (
        "# Copyright (c) 2026 Example Org.\n\n"
        '"""Sample module."""\n\n'
        "from __future__ import annotations\n\n\n"
        "def greet(  ) ->str:\n"
        "    x='hello'\n"
        "    return x\n"
    )
    module.write_text(dirty)

    result = runner.invoke(app, ["library", "format", "--quiet"], catch_exceptions=False)

    assert result.exit_code == 0
    formatted = module.read_text()
    assert formatted != dirty
    assert 'x = "hello"' in formatted
    assert "def greet() -> str:" in formatted


def test_license_header_check_detects_missing(tmp_path: Path) -> None:
    """Test check_license_headers flags files without a license header."""
    (tmp_path / "src").mkdir()
    missing_file = tmp_path / "src" / "no_header.py"
    missing_file.write_text('"""No header here."""\n')
    has_header_file = tmp_path / "src" / "has_header.py"
    has_header_file.write_text('# Copyright (c) 2026 Example Org.\n\n"""Has a header."""\n')

    missing = check_license_headers([tmp_path / "src"])

    assert missing == [missing_file]


def test_license_header_check_passes_with_header(tmp_path: Path) -> None:
    """Test check_license_headers returns nothing when all files have a header."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "ok.py").write_text("# Copyright (c) 2026 Example Org.\n")

    assert check_license_headers([tmp_path / "src"]) == []


def test_future_annotations_check_detects_missing(tmp_path: Path) -> None:
    """Test check_future_annotations flags files without the future import."""
    (tmp_path / "src").mkdir()
    missing_file = tmp_path / "src" / "no_future.py"
    missing_file.write_text('"""No future import."""\n')
    ok_file = tmp_path / "src" / "ok.py"
    ok_file.write_text('"""OK."""\n\nfrom __future__ import annotations\n')

    missing = check_future_annotations([tmp_path / "src"])

    assert missing == [missing_file]


def test_future_annotations_check_ignores_venv(tmp_path: Path) -> None:
    """Test check_future_annotations skips files under .venv/."""
    venv_dir = tmp_path / ".venv" / "lib"
    venv_dir.mkdir(parents=True)
    (venv_dir / "vendored.py").write_text('"""No future import, but vendored."""\n')

    assert check_future_annotations([tmp_path / ".venv"]) == []


def test_lint_requires_pyproject(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that 'library lint' fails gracefully without pyproject.toml."""
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    monkeypatch.chdir(empty_dir)

    result = runner.invoke(app, ["library", "lint"])

    assert result.exit_code != 0
