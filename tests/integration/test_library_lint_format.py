# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Integration tests for library lint/format commands using real ruff/ty."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from oarepo_cli.cli.main import app
from oarepo_cli.services.lint import check_future_annotations, check_license_headers

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def runner() -> CliRunner:
    """Provide a Typer CLI runner."""
    return CliRunner()


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
    assert (lint_project / "ty.toml").exists()
    # ty replaced mypy/pyright entirely (Step 3.9.1) - no .mypy.ini should
    # ever get generated anymore.
    assert not (lint_project / ".mypy.ini").exists()


def test_lint_does_not_swallow_non_oareporerror_exceptions(
    runner: CliRunner, lint_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A non-OARepoError raised by LintRunner propagates instead of being turned into a
    clean "exit 1" -- regression test for narrowing library.py's except clauses from
    the previous blanket `except Exception` to `except OARepoError` (Step 4.12). The
    shared lint/format/check command body now lives in cli/lint_commands.py (Step
    4.18), reused by both `library lint` and `repository lint`."""
    monkeypatch.chdir(lint_project)

    def _raise_value_error(_self: object, **_kwargs: object) -> None:
        raise ValueError("boom")

    monkeypatch.setattr("oarepo_cli.cli.lint_commands.LintRunner.run_lint", _raise_value_error)

    result = runner.invoke(app, ["library", "lint", "--quiet"])

    assert isinstance(result.exception, ValueError)
    assert "❌ Error running linters" not in result.output


def test_lint_fixes_autofixable_violation_by_default(
    runner: CliRunner, lint_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that 'library lint' (default --fix) auto-fixes what ruff can fix."""
    monkeypatch.chdir(lint_project)

    # Introduce an unused import in a *non*-__init__.py module - ruff treats
    # unused-import removal in __init__.py as an unsafe fix (re-export
    # convention), so --fix wouldn't apply it there.
    module = lint_project / "src" / "cleanlib" / "extra.py"
    dirty = (
        "# Copyright (c) 2026 Example Org.\n"
        "#\n"
        "# This file is a part of cleanlib.\n\n"
        '"""Extra module."""\n\n'
        "from __future__ import annotations\n\n"
        "import os\n\n\n"
        "def farewell() -> str:\n"
        '    """Return a farewell message."""\n'
        '    return "bye"\n'
    )
    module.write_text(dirty)

    result = runner.invoke(app, ["library", "lint", "--quiet"], catch_exceptions=False)

    assert result.exit_code == 0
    fixed = module.read_text()
    assert fixed != dirty
    assert "import os" not in fixed


def test_lint_fixes_formatting_issues_by_default(
    runner: CliRunner, lint_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that 'library lint' (default --fix) also fixes formatting issues."""
    monkeypatch.chdir(lint_project)

    # Introduce formatting issues (spacing, quote style) - no lint violations,
    # just formatting that ruff format would fix.
    module = lint_project / "src" / "cleanlib" / "__init__.py"
    dirty = (
        "# Copyright (c) 2026 Example Org.\n"
        "#\n"
        "# This file is a part of cleanlib.\n\n"
        '"""Sample clean module."""\n\n'
        "from __future__ import annotations\n\n\n"
        "def greet(  ) ->str:\n"
        '    """Return a greeting message."""\n'
        "    return   'hello'\n"
    )
    module.write_text(dirty)

    result = runner.invoke(app, ["library", "lint", "--quiet"], catch_exceptions=False)

    assert result.exit_code == 0
    fixed = module.read_text()
    assert fixed != dirty
    # Verify formatting was applied
    assert 'return "hello"' in fixed
    assert "def greet() -> str:" in fixed
    assert "return   'hello'" not in fixed


def test_lint_no_fix_fails_on_dirty_code_without_modifying(
    runner: CliRunner, lint_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that 'library lint --no-fix' reports an issue without touching the file."""
    monkeypatch.chdir(lint_project)

    # Introduce an unused import - a ruff violation.
    module = lint_project / "src" / "cleanlib" / "__init__.py"
    dirty = module.read_text() + "\nimport os\n"
    module.write_text(dirty)

    result = runner.invoke(app, ["library", "lint", "--no-fix", "--quiet"], catch_exceptions=False)

    assert result.exit_code != 0
    assert module.read_text() == dirty


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


def test_lint_fails_on_type_error(
    runner: CliRunner, lint_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that 'library lint' exits non-zero when ty finds a real type error.

    Exercises the ty check step specifically (Step 3.9.1's mypy/pyright ->
    ty migration): the return type doesn't match the annotation, which
    ruff/license/future-annotations checks don't catch, only a type checker
    does.
    """
    monkeypatch.chdir(lint_project)

    module = lint_project / "src" / "cleanlib" / "__init__.py"
    module.write_text(
        "# Copyright (c) 2026 Example Org.\n"
        "#\n"
        "# This file is a part of cleanlib.\n\n"
        '"""Sample clean module."""\n\n'
        "from __future__ import annotations\n\n\n"
        "def greet() -> int:\n"
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

    # Only formatting is off here (spacing, quote style) - no un-autofixable
    # lint violations under the generated .ruff.toml's `select = ["ALL"]`,
    # so this isolates the formatting behavior under test.
    module = lint_project / "src" / "cleanlib" / "__init__.py"
    dirty = (
        "# Copyright (c) 2026 Example Org.\n"
        "#\n"
        "# This file is a part of cleanlib.\n\n"
        '"""Sample clean module."""\n\n'
        "from __future__ import annotations\n\n\n"
        "def greet(  ) ->str:\n"
        '    """Return a greeting message."""\n'
        "    return   'hello'\n"
    )
    module.write_text(dirty)

    assert not (lint_project / ".ruff.toml").exists()

    result = runner.invoke(app, ["library", "format", "--quiet"], catch_exceptions=False)

    assert result.exit_code == 0
    formatted = module.read_text()
    assert formatted != dirty
    assert 'return "hello"' in formatted
    assert "def greet() -> str:" in formatted
    # First-time `format` (with no prior `lint` run) must still generate
    # .ruff.toml, otherwise ruff falls back to its built-in defaults instead
    # of this project's style (docstring formatting, line length, etc.).
    assert (lint_project / ".ruff.toml").exists()


def test_format_no_fix_previews_without_modifying(
    runner: CliRunner, lint_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that 'library format --no-fix' reports formatting issues without rewriting."""
    monkeypatch.chdir(lint_project)

    module = lint_project / "src" / "cleanlib" / "__init__.py"
    dirty = (
        "# Copyright (c) 2026 Example Org.\n"
        "#\n"
        "# This file is a part of cleanlib.\n\n"
        '"""Sample clean module."""\n\n'
        "from __future__ import annotations\n\n\n"
        "def greet(  ) ->str:\n"
        '    """Return a greeting message."""\n'
        "    return   'hello'\n"
    )
    module.write_text(dirty)

    result = runner.invoke(
        app, ["library", "format", "--no-fix", "--quiet"], catch_exceptions=False
    )

    assert result.exit_code != 0
    assert module.read_text() == dirty


def test_format_does_not_overwrite_existing_ruff_toml(
    runner: CliRunner, lint_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that 'library format' leaves a pre-existing .ruff.toml untouched."""
    monkeypatch.chdir(lint_project)

    custom_config = 'line-length = 79\n[format]\nquote-style = "single"\n'
    (lint_project / ".ruff.toml").write_text(custom_config)

    result = runner.invoke(app, ["library", "format", "--quiet"], catch_exceptions=False)

    assert result.exit_code == 0
    assert (lint_project / ".ruff.toml").read_text() == custom_config


def test_format_passes_through_extra_args_to_ruff(
    runner: CliRunner, lint_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that unknown arguments to 'library format' reach both ruff invocations.

    A path argument restricts both `ruff format` and `ruff check --fix` to
    that file, so passing one of two dirty files' paths through should
    format only that file and leave the other untouched - directly
    exercising that pass-through, not just that formatting happens.
    """
    monkeypatch.chdir(lint_project)

    dirty = (
        "# Copyright (c) 2026 Example Org.\n"
        "#\n"
        "# This file is a part of cleanlib.\n\n"
        '"""{docstring}"""\n\n'
        "from __future__ import annotations\n\n\n"
        "def {func}(  ) ->str:\n"
        '    """Return a message."""\n'
        "    return   '{word}'\n"
    )
    formatted_module = lint_project / "src" / "cleanlib" / "__init__.py"
    formatted_module.write_text(
        dirty.format(docstring="Sample clean module.", func="greet", word="hello")
    )
    untouched_module = lint_project / "src" / "cleanlib" / "other.py"
    untouched_dirty = dirty.format(docstring="Other module.", func="farewell", word="bye")
    untouched_module.write_text(untouched_dirty)

    result = runner.invoke(
        app,
        ["library", "format", "--quiet", "src/cleanlib/__init__.py"],
        catch_exceptions=False,
    )

    assert result.exit_code == 0
    assert 'return "hello"' in formatted_module.read_text()
    assert untouched_module.read_text() == untouched_dirty


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
