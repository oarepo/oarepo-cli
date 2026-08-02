# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""License header management for OARepo library projects."""

from __future__ import annotations

import pathlib  # noqa: TC003
import re
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from oarepo_cli.core.context import ProjectContext

from oarepo_cli.services import process


def _has_spdx_header(content: str) -> bool:
    """Check if a file has an SPDX license header.

    Args:
        content: File content to check

    Returns:
        True if file has SPDX-FileCopyrightText and SPDX-License-Identifier
    """
    lines = content.splitlines()
    # Check first 5 lines for SPDX headers
    first_lines = "\n".join(lines[:5]).lower()
    return "spdx-filecopyrighttext" in first_lines and "spdx-license-identifier" in first_lines


def _extract_copyright_info(content: str) -> tuple[str | None, str | None]:
    """Extract year range and organization from old-style copyright header.

    Args:
        content: File content to extract from

    Returns:
        Tuple of (year_string, organization) or (None, None) if not found
    """
    # Look for patterns like:
    # Copyright (c) 2025 CESNET z.s.p.o.
    # Copyright (C) 2020-2025 Some Organization
    # Copyright 2025 Org Name
    copyright_pattern = re.compile(
        r"#\s*Copyright\s*(?:\([cC]\))?\s*(\d{4}(?:-\d{4})?)\s+(.+?)(?:\s*#|\n|$)",
        re.IGNORECASE | re.MULTILINE,
    )

    match = copyright_pattern.search(content)
    if match:
        year_string = match.group(1).strip()
        org = match.group(2).strip()
        # Clean up organization name (remove trailing periods, etc.)
        org = org.rstrip(".")
        return year_string, org
    return None, None


def _remove_old_copyright_block(content: str) -> str:
    """Remove old-style copyright header block from content.

    Removes comment blocks at the start of the file (after optional shebang)
    that contain copyright information.

    Args:
        content: File content

    Returns:
        Content with old copyright block removed
    """
    lines = content.splitlines(keepends=True)
    start_idx = 0

    # Skip shebang if present
    if lines and lines[0].startswith("#!"):
        start_idx = 1

    # Find the end of the copyright block
    # A copyright block is a sequence of comment lines or blank lines
    # that starts with a comment containing "copyright"
    in_copyright_block = False
    end_idx = start_idx

    for i in range(start_idx, len(lines)):
        line = lines[i]
        stripped = line.strip()

        # Check if this line starts the copyright block
        if not in_copyright_block and "copyright" in stripped.lower() and stripped.startswith("#"):
            in_copyright_block = True
            end_idx = i
            continue

        # If we're in a copyright block, continue as long as we see comments or blank lines
        if in_copyright_block:
            if stripped.startswith("#") or stripped == "":
                end_idx = i + 1
            else:
                # Found a non-comment, non-blank line - end of block
                break
        else:
            # Haven't found a copyright block yet, and this isn't it
            if not stripped.startswith("#") and stripped != "":
                # No copyright block found
                break

    # If we found a copyright block, remove it
    if in_copyright_block:
        # Keep shebang, remove copyright block, keep the rest
        if start_idx > 0:
            return lines[0] + "".join(lines[end_idx:])
        else:
            return "".join(lines[end_idx:])

    return content


def _add_spdx_header(file_path: Path, organization: str, current_year: int) -> None:
    """Add SPDX license header to a Python file.

    If an old-style copyright header exists, extracts year and organization
    from it, removes it, and replaces it with SPDX format.

    Args:
        file_path: Path to the file
        organization: Organization name for copyright (fallback if not in file)
        current_year: Current year for copyright (fallback if not in file)
    """
    content = file_path.read_text(encoding="utf-8")

    # Try to extract copyright info from existing header
    year_string, extracted_org = _extract_copyright_info(content)

    # Use extracted info if available, otherwise use defaults
    final_year = year_string if year_string else str(current_year)
    final_org = extracted_org if extracted_org else organization

    # Remove old copyright block
    content = _remove_old_copyright_block(content)

    # Build SPDX header
    spdx_header = (
        f"# SPDX-FileCopyrightText: {final_year} {final_org}\n# SPDX-License-Identifier: MIT\n\n"
    )

    # If file starts with shebang, preserve it
    if content.startswith("#!"):
        lines = content.splitlines(keepends=True)
        shebang = lines[0]
        rest = "".join(lines[1:])
        new_content = shebang + spdx_header + rest
    else:
        new_content = spdx_header + content

    file_path.write_text(new_content, encoding="utf-8")


def _iter_python_files(directories: list[Path]) -> list[Path]:
    """Find all *.py files under the given directories.

    Args:
        directories: Directories to search recursively

    Returns:
        Sorted list of Python file paths
    """
    files: list[pathlib.Path] = []
    for directory in directories:
        files.extend(directory.rglob("*.py"))
    return sorted(files)  # type: ignore[return-value]


def add_license_headers(
    context: ProjectContext, *, organization: str | None = None, quiet: bool = False
) -> process.ProcessResult:
    """Add SPDX license headers to Python files missing them.

    Adds SPDX-style headers to files that don't have
    "spdx-filecopyrighttext" and "spdx-license-identifier" in the first 5
    lines (case-insensitive).

    Args:
        context: Project context with paths and configuration
        organization: Organization name for copyright (default: "CESNET z.s.p.o.")
        quiet: If True, suppress progress output

    Returns:
        ProcessResult indicating success or failure
    """
    root = context.root_directory
    code_directories = context.code_directories

    organization = organization or "CESNET z.s.p.o."
    current_year = datetime.now().year

    files_processed = 0

    # Find files without SPDX headers
    for file_path in _iter_python_files(code_directories):
        if ".venv" in file_path.parts:
            continue

        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            if not _has_spdx_header(content):
                # Add SPDX header to this file
                _add_spdx_header(file_path, organization, current_year)
                files_processed += 1
        except Exception as e:
            # Return a synthetic failure result
            return process.ProcessResult(
                return_code=1,
                stdout="",
                stderr=f"Failed to process {file_path}: {e}",
                command=[],
                cwd=root,
                duration_ms=0,
            )

    if not quiet and files_processed > 0:
        print(f"Added license headers to {files_processed} file(s)")

    return process.ProcessResult(
        return_code=0,
        stdout=f"Processed {files_processed} files",
        stderr="",
        command=[],
        cwd=root,
        duration_ms=0,
    )
