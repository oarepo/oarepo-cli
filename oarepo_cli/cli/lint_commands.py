# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Shared CLI-layer implementation for `library`/`repository` lint/format/check.

`library lint`/`format`/`check` and `repository lint`/`format`/`check` are
functionally identical -- both just run `services.lint.LintRunner` over
`context.code_directories` -- so the console messages, error handling, and
exit-code logic live here once, rather than duplicated verbatim across
`cli/library.py` and `cli/repository.py`. Each module still owns its own
Typer command registration (decorator, options, docstring/`--help` text,
and `discover_context()` call/error handling, which differs between the
two -- see each module's own commands).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, NoReturn

import typer

from oarepo_cli.core.errors import OARepoError
from oarepo_cli.services.lint import LintRunner
from oarepo_cli.ui import ConsoleOutput

if TYPE_CHECKING:
    from collections.abc import Sequence

    from oarepo_cli.core.context import ProjectContext


def run_lint(context: ProjectContext, *, fix: bool, quiet: bool) -> NoReturn:
    """Run ``LintRunner.run_lint()`` and exit with its result, for `library`/`repository lint`."""
    console = ConsoleOutput(quiet=quiet)
    console.info("🔍 Running linters...", fg=typer.colors.BRIGHT_BLUE, bold=True)

    runner = LintRunner(context=context, quiet=quiet)

    try:
        result = runner.run_lint(fix=fix)
    except OARepoError as e:
        console.error(f"❌ Error running linters: {e}", fg=typer.colors.BRIGHT_RED, bold=True)
        raise typer.Exit(code=1) from e

    if result.success:
        console.success("✨ ✓ Linting passed!", fg=typer.colors.BRIGHT_GREEN, bold=True)
    else:
        console.error("❌ Linting failed!", fg=typer.colors.BRIGHT_RED, bold=True)

    raise typer.Exit(code=result.return_code)


def run_format(
    context: ProjectContext, *, fix: bool, extra_args: Sequence[str], quiet: bool
) -> NoReturn:
    """Run ``LintRunner.run_format()`` and exit with its result, for `library`/`repository format`."""
    console = ConsoleOutput(quiet=quiet)
    console.info("🎨 Formatting code...", fg=typer.colors.BRIGHT_BLUE, bold=True)

    runner = LintRunner(context=context, quiet=quiet)

    try:
        result = runner.run_format(fix=fix, extra_args=list(extra_args))
    except OARepoError as e:
        console.error(f"❌ Error formatting code: {e}", fg=typer.colors.BRIGHT_RED, bold=True)
        raise typer.Exit(code=1) from e

    if result.success:
        console.success("✨ ✓ Formatting complete!", fg=typer.colors.BRIGHT_GREEN, bold=True)
    else:
        console.error("❌ Formatting failed!", fg=typer.colors.BRIGHT_RED, bold=True)

    raise typer.Exit(code=result.return_code)


def run_check(context: ProjectContext, *, quiet: bool) -> NoReturn:
    """Run ``LintRunner.run_lint(fix=False)`` and exit with its result, for
    `library`/`repository check`."""
    console = ConsoleOutput(quiet=quiet)
    console.info("🔎 Checking...", fg=typer.colors.BRIGHT_BLUE, bold=True)

    runner = LintRunner(context=context, quiet=quiet)

    try:
        result = runner.run_lint(fix=False)
    except OARepoError as e:
        console.error(f"❌ Error running checks: {e}", fg=typer.colors.BRIGHT_RED, bold=True)
        raise typer.Exit(code=1) from e

    if result.success:
        console.success("✨ ✓ Check passed!", fg=typer.colors.BRIGHT_GREEN, bold=True)
    else:
        console.error("❌ Check failed!", fg=typer.colors.BRIGHT_RED, bold=True)

    raise typer.Exit(code=result.return_code)
