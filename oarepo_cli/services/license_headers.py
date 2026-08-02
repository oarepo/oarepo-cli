# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""License header management for OARepo library projects."""

from __future__ import annotations

import pathlib  # noqa: TC003
import re
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from oarepo_cli.core.context import ProjectContext

from oarepo_cli.services import process


class CommentStyle(Enum):
    """Comment style for different file types."""

    HASH = "hash"  # Python: # comment
    SLASH = "slash"  # JavaScript: // comment
    JINJA = "jinja"  # Jinja: {# comment #}


def _get_comment_style(file_path: Path) -> CommentStyle:
    """Determine the comment style based on file extension.

    Args:
        file_path: Path to the file

    Returns:
        CommentStyle enum value
    """
    suffix = file_path.suffix.lower()
    if suffix in (".js", ".jsx"):
        return CommentStyle.SLASH
    elif suffix in (".html", ".jinja", ".jinja2", ".j2"):
        return CommentStyle.JINJA
    else:
        return CommentStyle.HASH


def _has_spdx_header(content: str) -> bool:
    """Check if a file has an SPDX license header.

    Args:
        content: File content to check

    Returns:
        True if file has SPDX-FileCopyrightText and SPDX-License-Identifier
    """
    lines = content.splitlines()
    # Check first 10 lines for SPDX headers (more for Jinja with DOCTYPE)
    first_lines = "\n".join(lines[:10]).lower()
    return "spdx-filecopyrighttext" in first_lines and "spdx-license-identifier" in first_lines


def _extract_copyright_info(
    content: str, comment_style: CommentStyle
) -> tuple[str | None, str | None]:
    """Extract year range and organization from old-style copyright header.

    Args:
        content: File content to extract from
        comment_style: Comment style for the file type

    Returns:
        Tuple of (year_string, organization) or (None, None) if not found
    """
    # Build pattern based on comment style
    if comment_style == CommentStyle.HASH:
        # Python: # Copyright (c) 2025 CESNET z.s.p.o.
        comment_prefix = r"#"
    elif comment_style == CommentStyle.SLASH:
        # JavaScript: // Copyright (c) 2025 CESNET z.s.p.o.
        comment_prefix = r"//"
    else:  # JINJA
        # Jinja: {# Copyright (c) 2025 CESNET z.s.p.o. #}
        comment_prefix = r"{#"

    copyright_pattern = re.compile(
        rf"{comment_prefix}\s*Copyright\s*(?:\([cC]\))?\s*(\d{{4}}(?:-\d{{4}})?)?\s*(.+?)(?:\s*#}}|\s*#|\n|$)",
        re.IGNORECASE | re.MULTILINE,
    )

    match = copyright_pattern.search(content)
    if match:
        year_string = match.group(1).strip() if match.group(1) else None
        org = match.group(2).strip()
        # Clean up organization name (remove trailing periods, etc.)
        org = org.rstrip(".")
        return year_string, org
    return None, None


def _remove_old_copyright_block(content: str, comment_style: CommentStyle) -> str:
    """Remove old-style copyright header block from content.

    Removes comment blocks at the start of the file (after optional shebang)
    that contain copyright information.

    Args:
        content: File content
        comment_style: Comment style for the file type

    Returns:
        Content with old copyright block removed
    """
    lines = content.splitlines(keepends=True)
    start_idx = 0

    # Skip shebang if present
    if lines and lines[0].startswith("#!"):
        start_idx = 1

    # For Jinja templates, also skip DOCTYPE if present
    if (
        comment_style == CommentStyle.JINJA
        and start_idx < len(lines)
        and lines[start_idx].strip().startswith("<!")
    ):
        start_idx += 1

    # Determine comment check function based on style
    def is_hash_comment(s: str) -> bool:
        return s.startswith("#")

    def is_slash_comment(s: str) -> bool:
        return s.startswith("//")

    def is_jinja_comment(s: str) -> bool:
        return s.startswith("{#")

    if comment_style == CommentStyle.HASH:
        is_comment = is_hash_comment
    elif comment_style == CommentStyle.SLASH:
        is_comment = is_slash_comment
    else:  # JINJA
        is_comment = is_jinja_comment

    # Find the end of the copyright block
    in_copyright_block = False
    end_idx = start_idx

    for i in range(start_idx, len(lines)):
        line = lines[i]
        stripped = line.strip()

        # Check if this line starts the copyright block
        if not in_copyright_block and "copyright" in stripped.lower() and is_comment(stripped):
            in_copyright_block = True
            end_idx = i
            continue

        # If we're in a copyright block, continue as long as we see comments or blank lines
        if in_copyright_block:
            if (
                is_comment(stripped)
                or stripped == ""
                or (comment_style == CommentStyle.JINJA and "#}" in stripped)
            ):
                end_idx = i + 1
            else:
                # Found a non-comment, non-blank line - end of block
                break
        else:
            # Haven't found a copyright block yet, and this isn't it
            if not is_comment(stripped) and stripped != "":
                # No copyright block found
                break

    # If we found a copyright block, remove it
    if in_copyright_block:
        # Keep shebang/DOCTYPE, remove copyright block, keep the rest
        if start_idx > 0:
            return "".join(lines[:start_idx]) + "".join(lines[end_idx:])
        else:
            return "".join(lines[end_idx:])

    return content


def _build_spdx_header(year: str, organization: str, comment_style: CommentStyle) -> str:
    """Build SPDX header with appropriate comment style.

    Args:
        year: Year or year range
        organization: Organization name
        comment_style: Comment style for the file type

    Returns:
        Formatted SPDX header string
    """
    if comment_style == CommentStyle.HASH:
        return (
            f"# SPDX-FileCopyrightText: {year} {organization}\n# SPDX-License-Identifier: MIT\n\n"
        )
    elif comment_style == CommentStyle.SLASH:
        return (
            f"// SPDX-FileCopyrightText: {year} {organization}\n// SPDX-License-Identifier: MIT\n\n"
        )
    else:  # JINJA
        # Single multi-line comment to avoid extra blank lines when rendered
        return (
            f"{{#\n"
            f"SPDX-FileCopyrightText: {year} {organization}\n"
            f"SPDX-License-Identifier: MIT\n"
            "#}\n"
        )


def _add_spdx_header(file_path: Path, organization: str, current_year: int) -> None:
    """Add SPDX license header to a file.

    If an old-style copyright header exists, extracts year and organization
    from it, removes it, and replaces it with SPDX format.

    Args:
        file_path: Path to the file
        organization: Organization name for copyright (fallback if not in file)
        current_year: Current year for copyright (fallback if not in file)
    """
    comment_style = _get_comment_style(file_path)
    content = file_path.read_text(encoding="utf-8")

    # Try to extract copyright info from existing header
    year_string, extracted_org = _extract_copyright_info(content, comment_style)

    # Use extracted info if available, otherwise use defaults
    final_year = year_string if year_string else str(current_year)
    final_org = extracted_org if extracted_org else organization

    # Remove old copyright block
    content = _remove_old_copyright_block(content, comment_style)

    # Build SPDX header with appropriate comment style
    spdx_header = _build_spdx_header(final_year, final_org, comment_style)

    # Handle special cases for file starts
    if content.startswith("#!"):
        # Preserve shebang (Python scripts)
        lines = content.splitlines(keepends=True)
        shebang = lines[0]
        rest = "".join(lines[1:])
        new_content = shebang + spdx_header + rest
    elif comment_style == CommentStyle.JINJA and content.strip().startswith("<!"):
        # Preserve DOCTYPE for HTML/Jinja templates
        lines = content.splitlines(keepends=True)
        doctype = lines[0]
        rest = "".join(lines[1:])
        new_content = doctype + spdx_header + rest
    else:
        new_content = spdx_header + content

    file_path.write_text(new_content, encoding="utf-8")


def _iter_target_files(directories: list[Path]) -> list[Path]:
    """Find all target files under the given directories.

    Targets: *.py, *.js, *.jsx, *.html, *.jinja, *.jinja2, *.j2 files

    Args:
        directories: Directories to search recursively

    Returns:
        Sorted list of file paths
    """
    files: list[pathlib.Path] = []
    extensions = (".py", ".js", ".jsx", ".html", ".jinja", ".jinja2", ".j2")

    for directory in directories:
        for ext in extensions:
            files.extend(directory.rglob(f"*{ext}"))

    return sorted(files)  # type: ignore[return-value]


def add_license_headers(
    context: ProjectContext, *, organization: str | None = None, quiet: bool = False
) -> process.ProcessResult:
    """Add SPDX license headers to source files missing them.

    Adds SPDX-style headers to Python, JavaScript, JSX, and Jinja template
    files that don't have "spdx-filecopyrighttext" and
    "spdx-license-identifier" in the first 10 lines (case-insensitive).

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
    for file_path in _iter_target_files(code_directories):
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
