# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Shared CLI-layer implementation for `library`/`repository` lint/format/check.

Both `library` and `repository` provide lint/format/check commands with
identical behavior: run ruff and ty over `context.code_directories`. The
only difference is the command registration (`@library_app.command` vs.
`@repository_app.command`), so this module centralizes the implementation
to avoid duplicating console output, error handling, and exit-code logic.

Key Differences Between Commands:
- `lint` / `format`: Fix issues by default (--fix for lint, always fixes for format)
- `check`: Read-only verification (fails with non-zero exit code if issues found)

All three commands:
1. Discover the project context to find code_directories
2. Create a LintRunner (services/lint.py) with appropriate mode/flags
3. Run ruff + ty over each code directory
4. Propagate exit codes exactly (0 = clean, non-zero = issues/errors)
5. Respect the --quiet flag for suppressing console output

Pattern:
- Thin CLI layer: business logic lives in services/lint.py
- Exit codes preserved (required by architecture ADRs)
- No abstraction over ruff/ty themselves (called directly as subprocesses)

See Also:
- services/lint.py: LintRunner implementation with ruff/ty subprocess execution
- cli/library.py: library_lint(), library_format(), library_check() registrations
- cli/repository.py: repository_lint(), repository_format(), repository_check()
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
