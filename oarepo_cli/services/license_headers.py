# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""License header management for OARepo library projects."""

from __future__ import annotations

import pathlib  # noqa: TC003
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable
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
    if suffix in (".html", ".jinja", ".jinja2", ".j2"):
        return CommentStyle.JINJA
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


def _extract_copyright_info(content: str, comment_style: CommentStyle) -> tuple[str | None, str | None]:
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


def _get_copyright_comment_checker(comment_style: CommentStyle) -> Callable[[str], bool]:
    """Return the appropriate comment check function based on the comment style."""

    def is_hash_comment(s: str) -> bool:
        """Return True if `s` starts a `#`-style comment line."""
        return s.startswith("#")

    def is_slash_comment(s: str) -> bool:
        """Return True if `s` starts a `//`-style comment line."""
        return s.startswith("//")

    def is_jinja_comment(s: str) -> bool:
        """Return True if `s` starts a `{#`-style Jinja comment line."""
        return s.startswith("{#")

    if comment_style == CommentStyle.HASH:
        is_comment = is_hash_comment
    elif comment_style == CommentStyle.SLASH:
        is_comment = is_slash_comment
    else:  # JINJA
        is_comment = is_jinja_comment

    return is_comment


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
    if comment_style == CommentStyle.JINJA and start_idx < len(lines) and lines[start_idx].strip().startswith("<!"):
        start_idx += 1

    is_comment = _get_copyright_comment_checker(comment_style)

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
            if is_comment(stripped) or stripped == "" or (comment_style == CommentStyle.JINJA and "#}" in stripped):
                end_idx = i + 1
            else:
                # Found a non-comment, non-blank line - end of block
                break
        # Haven't found a copyright block yet, and this isn't it
        elif not is_comment(stripped) and stripped != "":
            # No copyright block found
            break

    # If we found a copyright block, remove it
    if in_copyright_block:
        # Keep shebang/DOCTYPE, remove copyright block, keep the rest
        if start_idx > 0:
            return "".join(lines[:start_idx]) + "".join(lines[end_idx:])
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
        return f"# SPDX-FileCopyrightText: {year} {organization}\n# SPDX-License-Identifier: MIT\n\n"
    if comment_style == CommentStyle.SLASH:
        return f"// SPDX-FileCopyrightText: {year} {organization}\n// SPDX-License-Identifier: MIT\n\n"
    # JINJA
    # Single multi-line comment to avoid extra blank lines when rendered
    return f"{{#\nSPDX-FileCopyrightText: {year} {organization}\nSPDX-License-Identifier: MIT\n#}}\n"


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
    final_year = year_string or str(current_year)
    final_org = extracted_org or organization

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
        organization: Organization name for copyright. Defaults to
            ``context.config.license.organization`` (see
            ``core.config.LicenseConfig``), itself resolved from the
            ``organization`` key of ``[tool.oarepo-cli.license]`` in
            pyproject.toml, or the ``OAREPO_LICENSE_ORG`` environment
            variable, falling back to "CESNET z.s.p.o." if neither is set.
        quiet: If True, suppress progress output

    Returns:
        ProcessResult indicating success or failure

    """
    root = context.root_directory
    code_directories = context.code_directories

    organization = organization or context.config.license.organization
    current_year = datetime.now(UTC).year

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
        except OSError as e:
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
        pass

    return process.ProcessResult(
        return_code=0,
        stdout=f"Processed {files_processed} files",
        stderr="",
        command=[],
        cwd=root,
        duration_ms=0,
    )


_COPYRIGHT_YEARS_PATTERN = re.compile(r"SPDX-FileCopyrightText:\s*(?:(\d{4})(?:\s*-\s*(\d{4}))?)?", re.IGNORECASE)
_FIX_YEARS_PATTERN = re.compile(
    r"(SPDX-FileCopyrightText:)[ \t]*(?:\d{4}(?:[ \t]*-[ \t]*\d{4})?[ \t]*)?", re.IGNORECASE
)
_YEAR_MARKER = "\x1e"


@dataclass(frozen=True)
class LicenseHeaderIssue:
    """A license header that does not match the file's git history.

    Attributes:
        code: Stable issue code (``LIC001`` wrong range, ``LIC002`` no year)
        message: Human-readable description including the expected range
        path: Path to the offending file
        line: 1-based line of the SPDX-FileCopyrightText header
        column: 1-based column of the year (or of the header if no year)
        expected_years: The year range the header should contain
        fixable: False if the file has several copyright holders, whose
            years cannot be derived from a single file history

    """

    code: str
    message: str
    path: Path
    line: int
    column: int
    expected_years: str
    fixable: bool

    def format(self, relative_to: Path) -> str:
        """Render the issue in a compiler-like format that editors can jump to."""
        try:
            display_path = self.path.relative_to(relative_to)
        except ValueError:
            display_path = self.path
        return f"{self.code} {self.message}\n--> {display_path}:{self.line}:{self.column}"


def _format_year_range(start: int, end: int) -> str:
    return str(start) if start == end else f"{start}-{end}"


def _collect_name_status_years(
    lines: list[str], root: Path, years: dict[Path, set[int]], current_name: dict[str, str], year: int
) -> None:
    """Record the year of every file touched in ``git --name-status`` output.

    Output must be fed newest first; ``_YEAR_MARKER`` lines switch the year.
    Renames are followed: once ``old -> new`` is seen, older entries for
    ``old`` are attributed to the file's current name via ``current_name``.
    """
    for line in lines:
        if line.startswith(_YEAR_MARKER):
            year = int(line[1:])
            continue
        if not line:
            continue
        status, *paths = (path.strip('"') for path in line.split("\t"))
        name = current_name.get(paths[-1], paths[-1])
        if status.startswith("R") and len(paths) == 2:  # noqa: PLR2004 rename: old, new
            current_name[paths[0]] = name
        years.setdefault(root / name, set()).add(year)


def _git_modification_years(root: Path) -> dict[Path, set[int]]:
    """Collect the years in which each file under ``root`` was modified.

    Walks uncommitted changes and then ``git log`` newest to oldest, following
    renames so that a moved file inherits the history of its previous
    location. Uncommitted changes and untracked files count as the current
    year.

    Args:
        root: Project root; must be inside a git work tree

    Returns:
        Mapping of absolute file paths (at their current location) to years

    """
    git = ["git", "-c", "core.quotePath=false"]
    diff_options = ["-M", "--name-status", "--relative", "--no-color"]
    current_year = datetime.now(UTC).year
    years: dict[Path, set[int]] = {}
    current_name: dict[str, str] = {}

    has_head = process.run([*git, "rev-parse", "--verify", "-q", "HEAD"], cwd=root, check=False).success
    if has_head:
        diff = process.run([*git, "diff", *diff_options, "HEAD", "--", "."], cwd=root)
        _collect_name_status_years(diff.stdout.split("\n"), root, years, current_name, current_year)
        log = process.run(
            [
                *git,
                "log",
                "--no-merges",
                *diff_options,
                f"--format={_YEAR_MARKER}%ad",
                "--date=format:%Y",
                "--",
                ".",
            ],
            cwd=root,
        )
        # split("\n"), not splitlines(): the latter also splits on _YEAR_MARKER
        _collect_name_status_years(log.stdout.split("\n"), root, years, current_name, current_year)

    # Without any commit yet, staged files are as new as untracked ones
    ls_files_options = ["--others"] if has_head else ["--others", "--cached"]
    untracked = process.run([*git, "ls-files", *ls_files_options, "--exclude-standard", "--", "."], cwd=root)
    for path in untracked.stdout.splitlines():
        years.setdefault(root / path.strip('"'), set()).add(current_year)

    return years


def _check_file_years(file_path: Path, content: str, first_year: int, last_year: int) -> LicenseHeaderIssue | None:
    """Compare a file's SPDX copyright years with its git history.

    The header's end year must equal the last modification year. Its start
    year may predate the first commit (the file may have existed before the
    repository did), but must not be later than it.

    Correcting the header modifies the file, so the expected range always
    ends in the current year - after the fix (and its commit) the header
    matches the history again.
    """
    current_year = datetime.now(UTC).year
    header_lines = content.splitlines()[:10]
    holders = sum(1 for line in header_lines if _COPYRIGHT_YEARS_PATTERN.search(line))
    suffix = "" if holders == 1 else " (multiple copyright holders, fix manually)"
    for line_no, line in enumerate(header_lines, start=1):
        match = _COPYRIGHT_YEARS_PATTERN.search(line)
        if not match:
            continue
        if not match.group(1):
            expected = _format_year_range(first_year, current_year)
            return LicenseHeaderIssue(
                code="LIC002",
                message=f"Missing copyright year, should be {expected}{suffix}",
                path=file_path,
                line=line_no,
                column=match.start() + 1,
                expected_years=expected,
                fixable=holders == 1,
            )
        header_start = int(match.group(1))
        header_end = int(match.group(2) or header_start)
        if header_start > first_year or header_end != last_year:
            expected = _format_year_range(min(header_start, first_year), current_year)
            return LicenseHeaderIssue(
                code="LIC001",
                message=f"Wrong range, should be {expected}{suffix}",
                path=file_path,
                line=line_no,
                column=match.start(1) + 1,
                expected_years=expected,
                fixable=holders == 1,
            )
        return None
    return None


def check_license_header_years(context: ProjectContext) -> list[LicenseHeaderIssue]:
    """Check that SPDX copyright years match each file's git history.

    Scans the same files as :func:`add_license_headers` (source and test
    directories). For every file with an SPDX header, the year range must
    span from the year the file first appeared in git to the year it was
    last modified (uncommitted changes count as the current year). Files
    without an SPDX header are skipped - adding them is
    :func:`add_license_headers`' job.

    Args:
        context: Project context with paths and configuration

    Returns:
        Issues found, sorted by path

    Raises:
        ProcessExecutionError: If git is unavailable or the project is not
            inside a git repository

    """
    root = context.root_directory.resolve()
    years_by_path = _git_modification_years(root)

    issues: list[LicenseHeaderIssue] = []
    for file_path in _iter_target_files(context.code_directories):
        if ".venv" in file_path.parts:
            continue
        years = years_by_path.get(file_path.resolve())
        if not years:
            continue
        content = file_path.read_text(encoding="utf-8", errors="replace")
        issue = _check_file_years(file_path, content, min(years), max(years))
        if issue:
            issues.append(issue)
    return issues


def fix_license_header_years(issues: list[LicenseHeaderIssue]) -> list[LicenseHeaderIssue]:
    """Rewrite the copyright years of every fixable issue in place.

    Only files with a single SPDX-FileCopyrightText line are fixed; with
    several copyright holders it is unknown whose years the history reflects.

    Args:
        issues: Issues returned by :func:`check_license_header_years`

    Returns:
        The issues that were not fixed

    """
    for issue in issues:
        if not issue.fixable:
            continue
        lines = issue.path.read_text(encoding="utf-8").splitlines(keepends=True)
        lines[issue.line - 1] = _FIX_YEARS_PATTERN.sub(
            lambda m, years=issue.expected_years: f"{m.group(1)} {years} ", lines[issue.line - 1], count=1
        )
        issue.path.write_text("".join(lines), encoding="utf-8")
    return [issue for issue in issues if not issue.fixable]
