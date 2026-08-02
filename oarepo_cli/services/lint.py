# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Linting and formatting orchestration for OARepo library projects."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from oarepo_cli.core.context import ProjectContext

from oarepo_cli.services import process


# Linters/type checkers are installed as regular oarepo-cli dependencies (see
# pyproject.toml) and resolved next to the running interpreter rather than
# fetched on demand via `uvx`, so each `library lint`/`library format` call
# skips uv's per-invocation resolve/download.
def _tool_path(name: str) -> str:
    """Resolve a linter/type-checker binary installed alongside oarepo-cli.

    Args:
        name: Console script name (e.g. "ruff", "mypy", "pyright")

    Returns:
        Absolute path to the binary if found next to the current
        interpreter, otherwise the bare name (resolved via PATH by the
        subprocess call).
    """
    candidate = Path(sys.executable).parent / name
    return str(candidate) if candidate.exists() else name


RUFF_TOML = """\
target-version = "py314"
line-length = 120
indent-width = 4

[lint]
select = [ "ALL" ]
ignore = [
    "FIX002",  # exclude TODO comments
    "TD003",   # Missing issue link for this TODO
    "TD002",   # Missing author in TODO
    "N806",    # Variable name should be lowercase as we dynamically create classes
    "ANN204",  # Missing return type annotation for __init__
    "ANN401",  # Any in *args/**kwargs
    "TRY003",  # Avoid long exception messages
    "EM101",   # Avoid using string literal in exception
    "EM102",   # Avoid using f-string literal in exception
    "TRY301",  # Avoid raising/catching the same exception type
    "PLC0415",  # Place imports to the top of the file
    "PGH004",  # Use specific noqa for pylint
    "TID252",  # Prefer absolute imports
    "D203",    # Using D211
    "D213",    # Using D212 (multi-line-summary-first-line) instead
    "COM812",
    "FBT001",  # Avoid using boolean function parameters
    "FBT002",  # Avoid using boolean function parameters
]

[lint.per-file-ignores]
"__init__.py" = ["E402"]
"**/{tests,docs,tools}/*" = [
    "E402",
    "S101",
    "ANN001",
    "ARG001",
    "D103",
    "ANN201",
    "D100",
    "INP",
    "PLR",
    "PLC"
    ]

[format]
docstring-code-format = true
docstring-code-line-length = 40
"""

MYPY_INI = """\
[mypy]
warn_return_any = True
warn_unused_configs = True
warn_unreachable = True
follow_untyped_imports = True
"""


def _iter_python_files(directories: list[Path]) -> list[Path]:
    """Find all *.py files under the given directories.

    Args:
        directories: Directories to search recursively

    Returns:
        Sorted list of Python file paths
    """
    files: list[Path] = []
    for directory in directories:
        files.extend(directory.rglob("*.py"))
    return sorted(files)


def check_license_headers(directories: list[Path]) -> list[Path]:
    """Find Python files missing a license header.

    Mirrors ``library_runner.sh``'s ``check_license_headers``: a file passes
    if it contains "Copyright (c)" (case-insensitive) anywhere in its text.

    Args:
        directories: Directories to search for Python files

    Returns:
        List of files missing a license header
    """
    missing = []
    for file in _iter_python_files(directories):
        content = file.read_text(encoding="utf-8", errors="replace")
        if "copyright (c)" not in content.lower():
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
        if not any(
            "from __future__" in line and "annotations" in line for line in content.splitlines()
        ):
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

    def run_lint(self) -> process.ProcessResult:
        """Run the full lint suite: ruff, license headers, future annotations, mypy, pyright.

        Returns:
            ProcessResult of the first failing step, or a success result if all pass
        """
        root = self._context.root_directory
        code_directories = self._context.code_directories

        _write_config(root / ".ruff.toml", RUFF_TOML)

        ruff = _tool_path("ruff")
        result = process.run(
            [ruff, "check", "--exclude", "pyproject.toml"],
            cwd=root,
            check=False,
            interactive=not self._quiet,
        )
        if not result.success:
            return result

        result = process.run(
            [ruff, "format", "--check", "--exclude", "pyproject.toml"],
            cwd=root,
            check=False,
            interactive=not self._quiet,
        )
        if not result.success:
            return result

        missing_headers = check_license_headers(code_directories)
        if missing_headers:
            return _synthetic_failure(
                root,
                [f"Missing license header in {f}" for f in missing_headers]
                + [f"{len(missing_headers)} file(s) are missing license headers."],
            )

        missing_annotations = check_future_annotations(code_directories)
        if missing_annotations:
            return _synthetic_failure(
                root,
                [
                    f"Missing 'from __future__ import annotations' in {f}"
                    for f in missing_annotations
                ]
                + [f"{len(missing_annotations)} file(s) are missing future annotations."],
            )

        _write_config(root / ".mypy.ini", MYPY_INI)

        venv_python = self._context.venv_path / "bin" / "python"
        result = process.run(
            [
                _tool_path("mypy"),
                str(code_directories[0]),
                "--ignore-missing-imports",
                "--exclude",
                "os-v2",
            ],
            cwd=root,
            check=False,
            interactive=not self._quiet,
        )
        if not result.success:
            return result

        return process.run(
            [_tool_path("pyright"), "--pythonpath", str(venv_python), str(code_directories[0])],
            cwd=root,
            check=False,
            interactive=not self._quiet,
        )

    def run_format(self) -> process.ProcessResult:
        """Format code with ruff: ``ruff format`` then ``ruff check --fix``.

        Returns:
            ProcessResult of the first failing step, or the final success result
        """
        root = self._context.root_directory
        ruff = _tool_path("ruff")

        ruff_toml = root / ".ruff.toml"
        if not ruff_toml.exists():
            _write_config(ruff_toml, RUFF_TOML)

        result = process.run(
            [ruff, "format", "--exclude", "pyproject.toml"],
            cwd=root,
            check=False,
            interactive=not self._quiet,
        )
        if not result.success:
            return result

        return process.run(
            [ruff, "check", "--fix", "--exclude", "pyproject.toml"],
            cwd=root,
            check=False,
            interactive=not self._quiet,
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
    print(text, file=sys.stderr)
    return process.ProcessResult(
        return_code=1,
        stdout="",
        stderr=text,
        command=[],
        cwd=root,
        duration_ms=0,
    )
