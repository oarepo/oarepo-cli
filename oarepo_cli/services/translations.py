# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Translation management for OARepo library projects."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from oarepo_cli.core.context import ProjectContext

from oarepo_cli.services import process


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
        interactive=not quiet,
    )
