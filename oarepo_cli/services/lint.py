# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Linting and formatting orchestration for OARepo library projects."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pathspec
import typer

if TYPE_CHECKING:
    from oarepo_cli.core.context import ProjectContext

from oarepo_cli.configuration import resources
from oarepo_cli.services import process
from oarepo_cli.services.process import ProcessOutputMode


# Linters/type checkers are installed as regular oarepo-cli dependencies (see
# pyproject.toml) and resolved next to the running interpreter rather than
# fetched on demand via `uvx`, so each `library lint`/`library format` call
# skips uv's per-invocation resolve/download.
def _tool_path(name: str) -> str:
    """Resolve a linter/type-checker binary installed alongside oarepo-cli.

    Args:
        name: Console script name (e.g. "ruff", "ty")

    Returns:
        Absolute path to the binary if found next to the current
        interpreter, otherwise the bare name (resolved via PATH by the
        subprocess call).

    """
    candidate = Path(sys.executable).parent / name
    return str(candidate) if candidate.exists() else name


def _find_gitignore_root(start: Path) -> Path | None:
    """Locate the directory holding the project's root ``.gitignore``, if any.

    Walks upward from `start` looking for a `.gitignore`. The search stops
    as soon as it reaches the library/repository root - identified by a
    `.gitignore` file itself, or a `.git` entry if there's no `.gitignore`
    there - so a stray `.gitignore` further up an unrelated ancestor
    directory (e.g. the user's home directory) is never picked up.

    Args:
        start: Directory to start searching from

    Returns:
        The directory containing the `.gitignore`, or None if none was found

    """
    for directory in (start, *start.parents):
        if (directory / ".gitignore").exists():
            return directory
        if (directory / ".git").exists():
            break
    return None


def _iter_python_files(directories: list[Path]) -> list[Path]:
    """Find all *.py files under the given directories, honoring .gitignore.

    Args:
        directories: Directories to search recursively

    Returns:
        Sorted list of Python file paths, excluding any matched by the
        library's/repository's root `.gitignore` and any file under a
        directory named `alembic` (migration scripts)

    """
    files: list[Path] = []
    # Keyed by the directory holding the .gitignore, not by `directory`
    # below: distinct code directories (src/, tests/, ...) commonly share
    # the same root .gitignore, so this avoids re-reading/re-parsing it
    # once per code directory.
    spec_cache: dict[Path, pathspec.PathSpec] = {}
    for directory in directories:
        gitignore_root = _find_gitignore_root(directory)
        spec_info: tuple[Path, pathspec.PathSpec] | None = None
        if gitignore_root is not None:
            if gitignore_root not in spec_cache:
                lines = (gitignore_root / ".gitignore").read_text(encoding="utf-8", errors="replace").splitlines()
                spec_cache[gitignore_root] = pathspec.PathSpec.from_lines("gitignore", lines)
            spec_info = (gitignore_root, spec_cache[gitignore_root])
        for file in directory.rglob("*.py"):
            if "alembic" in file.parts:
                continue
            if spec_info is not None:
                root, spec = spec_info
                if spec.match_file(file.relative_to(root).as_posix()):
                    continue
            files.append(file)
    return sorted(files)


def check_license_headers(directories: list[Path]) -> list[Path]:
    """Find Python files missing a license header.

    Mirrors ``library_runner.sh``'s ``check_license_headers``: a file passes
    if it contains "SPDX-License-Identifier" (case-insensitive) anywhere in its text.

    Args:
        directories: Directories to search for Python files

    Returns:
        List of files missing a license header

    """
    missing = []
    for file in _iter_python_files(directories):
        content = file.read_text(encoding="utf-8", errors="replace")
        if "spdx-license-identifier" not in content.lower():
            missing.append(file)
    return missing


def check_future_annotations(directories: list[Path]) -> list[Path]:
    """Find Python files missing ``from __future__ import annotations``.

    Mirrors ``library_runner.sh``'s ``check_future_annotations``, excluding
    files under ``.venv/``.

    Args:
        directories: Directories to search for Python files

    Returns:
        List of files missing the future annotations import

    """
    missing = []
    for file in _iter_python_files(directories):
        if ".venv" in file.parts:
            continue
        content = file.read_text(encoding="utf-8", errors="replace")
        if not any("from __future__" in line and "annotations" in line for line in content.splitlines()):
            missing.append(file)
    return missing


class LintRunner:
    """Orchestrates linting and formatting for an OARepo library project.

    Reproduces ``library_runner.sh``'s ``run_linters``/``format_code``
    fail-fast behavior: each step runs in order and the first failure's
    result (and exit code) is returned immediately.
    """

    def __init__(self, context: ProjectContext, *, quiet: bool = False) -> None:
        """Initialize the lint runner.

        Args:
            context: Project context with paths and configuration
            quiet: If True, suppress real-time subprocess output

        """
        self._context = context
        self._quiet = quiet

    def _print_step(self, label: str) -> None:
        """Print a header naming the check about to run (skipped when quiet).

        Each step below shares the "All checks passed!"/similar wording with
        its underlying tool's own stdout, so without a header it's not clear
        from the output alone which tool a given "All checks passed!" belongs to.

        Args:
            label: Name of the step about to run (e.g. "ruff check")

        """
        if not self._quiet:
            typer.secho(f"→ {label}", fg=typer.colors.CYAN, bold=True)

    def _print_ok(self, label: str) -> None:
        """Print a pass marker for a step that has no stdout of its own.

        Args:
            label: Name of the step that just passed

        """
        if not self._quiet:
            typer.secho(f"  ✓ {label} passed", fg=typer.colors.GREEN)

    def run_lint(self, *, fix: bool = True) -> process.ProcessResult:
        """Run the full lint suite: ruff, license headers, future annotations, ty.

        Args:
            fix: If True (the default), auto-fix what ruff and ty can fix
                (``ruff check --fix``, ``ruff format``, ``ty check --fix``)
                instead of only reporting. The license header check and future
                annotations check are always read-only regardless of this
                flag - inserting headers/imports is `license-headers`' job.

        Returns:
            ProcessResult of the first failing step, or a success result if all pass

        """
        root = self._context.root_directory
        code_directories = self._context.code_directories

        _write_config(root / ".ruff.toml", resources.read_text("ruff.toml.tmpl"))

        ruff = _tool_path("ruff")
        fix_flag = ["--fix"] if fix else []
        self._print_step("ruff check")
        result = process.run(
            [ruff, "check", *fix_flag, "--exclude", "pyproject.toml"],
            cwd=root,
            check=False,
            output_mode=ProcessOutputMode.INTERACTIVE if not self._quiet else ProcessOutputMode.CAPTURE,
        )
        if not result.success:
            return result

        # When fix=True, actually reformat the code; when fix=False, only check
        format_mode = [] if fix else ["--check"]
        self._print_step("ruff format" if fix else "ruff format --check")
        result = process.run(
            [ruff, "format", *format_mode, "--exclude", "pyproject.toml"],
            cwd=root,
            check=False,
            output_mode=ProcessOutputMode.INTERACTIVE if not self._quiet else ProcessOutputMode.CAPTURE,
        )
        if not result.success:
            return result

        self._print_step("license headers")
        missing_headers = check_license_headers(code_directories)
        if missing_headers:
            return _synthetic_failure(
                root,
                [f"Missing license header in {f}" for f in missing_headers]
                + [f"{len(missing_headers)} file(s) are missing license headers."],
            )
        self._print_ok("license headers")

        self._print_step("future annotations")
        missing_annotations = check_future_annotations(code_directories)
        if missing_annotations:
            return _synthetic_failure(
                root,
                [f"Missing 'from __future__ import annotations' in {f}" for f in missing_annotations]
                + [f"{len(missing_annotations)} file(s) are missing future annotations."],
            )
        self._print_ok("future annotations")

        _write_config(root / "ty.toml", resources.read_text("ty.toml.tmpl"))

        # Every source directory, not just the first: a library's
        # code_directories only ever has one (plus tests/), but a
        # multi-module repository (see ProjectContext.code_directories) has
        # several, and ty needs to see all of them, not just the first.
        source_directories = [d for d in code_directories if d.name != "tests"]

        venv_python = self._context.venv_path / "bin" / "python"
        self._print_step("ty check")
        return process.run(
            [
                _tool_path("ty"),
                "check",
                *fix_flag,
                "--python",
                str(venv_python),
                *(str(d) for d in source_directories),
            ],
            cwd=root,
            check=False,
            output_mode=ProcessOutputMode.INTERACTIVE if not self._quiet else ProcessOutputMode.CAPTURE,
        )

    def run_format(self, *, fix: bool = True, extra_args: list[str] | None = None) -> process.ProcessResult:
        """Format code with ruff.

        Args:
            fix: If True (the default), rewrite files: ``ruff format`` then
                ``ruff check --fix``. If False, only report what would
                change: ``ruff format --check`` alone (``ruff check --fix``
                is skipped entirely, since there'd be nothing left to
                preview once formatting itself doesn't run).
            extra_args: Additional arguments passed through to the ruff
                invocation(s) (e.g. a path to restrict formatting to, or
                ruff flags like ``--diff``). Note: ``--unsafe-fixes`` is
                only passed to ``ruff check --fix``, not to ``ruff format``.

        Returns:
            ProcessResult of the first failing step, or the final result

        """
        root = self._context.root_directory
        ruff = _tool_path("ruff")
        extra_args = extra_args or []

        ruff_toml = root / ".ruff.toml"
        if not ruff_toml.exists():
            _write_config(ruff_toml, resources.read_text("ruff.toml.tmpl"))

        # Separate --unsafe-fixes for ruff check (it's not valid for ruff format)
        format_args = [arg for arg in extra_args if arg != "--unsafe-fixes"]
        check_args = extra_args  # --unsafe-fixes is valid for ruff check --fix

        if not fix:
            self._print_step("ruff format --check")
            return process.run(
                [ruff, "format", "--check", "--exclude", "pyproject.toml", *format_args],
                cwd=root,
                check=False,
                output_mode=ProcessOutputMode.INTERACTIVE if not self._quiet else ProcessOutputMode.CAPTURE,
            )

        self._print_step("ruff format")
        result = process.run(
            [ruff, "format", "--exclude", "pyproject.toml", *format_args],
            cwd=root,
            check=False,
            output_mode=ProcessOutputMode.INTERACTIVE if not self._quiet else ProcessOutputMode.CAPTURE,
        )
        if not result.success:
            return result

        self._print_step("ruff check --fix")
        return process.run(
            [ruff, "check", "--fix", "--exclude", "pyproject.toml", *check_args],
            cwd=root,
            check=False,
            output_mode=ProcessOutputMode.INTERACTIVE if not self._quiet else ProcessOutputMode.CAPTURE,
        )


def _write_config(path: Path, content: str) -> None:
    """Write a generated config file, overwriting any existing one.

    Args:
        path: Destination file path
        content: File contents to write

    """
    path.write_text(content, encoding="utf-8")


def _synthetic_failure(root: Path, messages: list[str]) -> process.ProcessResult:
    """Build a ProcessResult for a check that failed without running a subprocess.

    Args:
        root: Project root, used as the result's cwd
        messages: Lines to print to stderr and include in the result

    Returns:
        A failed ProcessResult (return_code=1) carrying the given messages

    """
    text = "\n".join(messages)
    return process.ProcessResult(
        return_code=1,
        stdout="",
        stderr=text,
        command=[],
        cwd=root,
        duration_ms=0,
    )
