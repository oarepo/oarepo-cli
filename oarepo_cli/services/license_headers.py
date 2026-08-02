# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""License header management for OARepo library projects."""

from __future__ import annotations

import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from oarepo_cli.core.context import ProjectContext

from oarepo_cli.configuration import resources
from oarepo_cli.services import process
from oarepo_cli.services.pyproject_reader import PyProjectReader


def _tool_path(name: str) -> str:
    """Resolve a tool binary installed alongside oarepo-cli.

    Args:
        name: Console script name (e.g. "licenseheaders")

    Returns:
        Absolute path to the binary if found next to the current
        interpreter, otherwise the bare name (resolved via PATH by the
        subprocess call).
    """
    candidate = Path(sys.executable).parent / name
    return str(candidate) if candidate.exists() else name


def _get_homepage_from_pyproject(pyproject_path: Path) -> str:
    """Extract homepage URL from pyproject.toml.

    Args:
        pyproject_path: Path to pyproject.toml

    Returns:
        Homepage URL

    Raises:
        ValueError: If homepage not found in pyproject.toml
    """
    reader = PyProjectReader()
    data = reader.read(pyproject_path)

    if not data.homepage:
        raise ValueError("No Homepage URL found in pyproject.toml [project.urls]")

    return data.homepage


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


def add_license_headers(
    context: ProjectContext, *, organization: str | None = None, quiet: bool = False
) -> process.ProcessResult:
    """Add MIT license headers to Python files missing them.

    Mirrors ``library_runner.sh``'s ``add_license_headers``: uses the
    licenseheaders tool to add headers to files that don't have "Copyright
    (C)" anywhere in them (case-insensitive).

    Args:
        context: Project context with paths and configuration
        organization: Organization name for copyright (default: "CESNET z.s.p.o.")
        quiet: If True, suppress progress output

    Returns:
        ProcessResult indicating success or failure
    """
    root = context.root_directory
    code_directories = context.code_directories

    # Get package name from pyproject.toml
    reader = PyProjectReader()
    pyproject_data = reader.read(root / "pyproject.toml")
    package_name = pyproject_data.name

    organization = organization or "CESNET z.s.p.o."
    current_year = datetime.now().year

    try:
        homepage = _get_homepage_from_pyproject(root / "pyproject.toml")
    except ValueError as e:
        # Return a synthetic failure result
        return process.ProcessResult(
            return_code=1,
            stdout="",
            stderr=str(e),
            command=[],
            cwd=root,
            duration_ms=0,
        )

    # Write template to a temp file
    template_content = resources.read_text("license-header.txt.tmpl")
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        template_path = Path(f.name)
        f.write(template_content)

    try:
        licenseheaders = _tool_path("licenseheaders")
        files_processed = 0

        # Find files without copyright headers
        for file_path in _iter_python_files(code_directories):
            if ".venv" in file_path.parts:
                continue

            content = file_path.read_text(encoding="utf-8", errors="replace")
            if "copyright (c)" not in content.lower():
                # Add header to this file
                result = process.run(
                    [
                        licenseheaders,
                        "-t",
                        str(template_path),
                        "-y",
                        str(current_year),
                        "-o",
                        organization,
                        "-n",
                        package_name,
                        "-u",
                        homepage,
                        "-f",
                        str(file_path),
                    ],
                    cwd=root,
                    check=False,
                    interactive=not quiet,
                )
                if not result.success:
                    return result
                files_processed += 1

        if not quiet and files_processed > 0:
            print(f"Added license headers to {files_processed} file(s)")

        return process.ProcessResult(
            return_code=0,
            stdout=f"Processed {files_processed} files",
            stderr="",
            command=[licenseheaders],
            cwd=root,
            duration_ms=0,
        )
    finally:
        # Clean up temp file
        template_path.unlink(missing_ok=True)
