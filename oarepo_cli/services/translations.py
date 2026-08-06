# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Translation management for OARepo library and repository projects."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from oarepo_cli.core.context import ProjectContext

from oarepo_cli.services import process
from oarepo_cli.services.process import ProcessOutputMode


def _tool_path(name: str) -> str:
    """Resolve a tool binary installed alongside oarepo-cli.

    Args:
        name: Console script name (e.g. "make-translations")

    Returns:
        Absolute path to the binary if found next to the current
        interpreter, otherwise the bare name (resolved via PATH by the
        subprocess call).

    """
    candidate = Path(sys.executable).parent / name
    return str(candidate) if candidate.exists() else name


def run_translations(
    context: ProjectContext, *, extra_args: list[str] | None = None, quiet: bool = False
) -> process.ProcessResult:
    """Extract and compile translations using oarepo-tools make-translations.

    Mirrors ``library_runner.sh``'s ``translations`` command: calls
    ``make-translations`` from oarepo-tools with any extra arguments.

    Args:
        context: Project context with paths and configuration
        extra_args: Additional arguments passed to make-translations
        quiet: If True, suppress real-time subprocess output

    Returns:
        ProcessResult from the make-translations command

    """
    extra_args = extra_args or []
    make_translations = _tool_path("make-translations")

    return process.run(
        [make_translations, *extra_args],
        cwd=context.root_directory,
        check=False,
        output_mode=ProcessOutputMode.INTERACTIVE if not quiet else ProcessOutputMode.CAPTURE,
    )


def copy_translations(
    context: ProjectContext,
    *,
    collected_translations_dir: str | None = None,
    quiet: bool = False,
) -> None:
    """Copy translation overlay from oarepo collected_translations to site-packages.

    Mirrors ``repository_runner.sh``'s ``copy_translations`` function: overlays
    collected translations onto the site-packages directory to customize
    Invenio translations for OARepo repositories.

    Args:
        context: Project context with paths and configuration
        collected_translations_dir: Optional override for COLLECTED_TRANSLATIONS_DIR env var
        quiet: If True, suppress status messages

    Raises:
        ProcessExecutionError: If site-packages detection or copy fails

    """
    # Get site-packages directory from the venv Python
    result = process.run(
        ["uv", "run", "--no-sync", "python", "-c", "import site; print(site.getsitepackages()[0])"],
        cwd=context.root_directory,
        check=True,
    )
    site_packages = Path(result.stdout.strip())

    # Determine source directory
    if collected_translations_dir is None:
        # Default: oarepo/collected_translations in site-packages
        src = site_packages / "oarepo" / "collected_translations"
    else:
        src = Path(collected_translations_dir)

    # Check if source exists
    if not src.exists():
        if not quiet:
            pass

        return

    if not quiet:
        pass

    # Use cp -R to recursively copy and merge
    # The /. pattern copies contents and merges into existing directories (works on both BSD and GNU cp)
    import shutil

    # Python's shutil.copytree with dirs_exist_ok=True is equivalent to cp -R
    # Copy all items from src into site_packages
    for item in src.iterdir():
        dest = site_packages / item.name
        if item.is_dir():
            shutil.copytree(item, dest, dirs_exist_ok=True)
        else:
            shutil.copy2(item, dest)

    if not quiet:
        pass
