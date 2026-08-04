# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Shared CLI-layer implementation for `library`/`repository` jslint/jstest.

`library jslint`/`jstest` and `repository jslint`/`jstest` are functionally
identical -- both just run `services.js_tools.run_jslint()`/`run_jstest()`
-- so the console messages, error handling, and exit-code logic live here
once, rather than duplicated verbatim across `cli/library.py` and
`cli/repository.py` (mirrors `cli/lint_commands.py`'s identical rationale
for `lint`/`format`/`check`). Each module still owns its own Typer command
registration (decorator, options, docstring/`--help` text, and
`discover_context()` call/error handling, which differs between the two).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, NoReturn

import typer

from oarepo_cli.core.errors import OARepoError
from oarepo_cli.services.js_tools import run_jslint, run_jstest
from oarepo_cli.ui import ConsoleOutput

if TYPE_CHECKING:
    from collections.abc import Sequence

    from oarepo_cli.core.context import ProjectContext


def run_jslint_command(context: ProjectContext, *, quiet: bool) -> NoReturn:
    """Run ``run_jslint()`` and exit with its result, for `library`/`repository jslint`."""
    console = ConsoleOutput(quiet=quiet)
    console.info("🔍 Running JavaScript linters...", fg=typer.colors.BRIGHT_BLUE, bold=True)

    try:
        result = run_jslint(context, quiet=quiet)
    except OARepoError as e:
        console.error(f"❌ Error running jslint: {e}", fg=typer.colors.BRIGHT_RED, bold=True)
        raise typer.Exit(code=1) from e

    if result.success:
        console.success(
            "✨ ✓ JavaScript linting complete!", fg=typer.colors.BRIGHT_GREEN, bold=True
        )
    else:
        console.error("❌ JavaScript linting failed!", fg=typer.colors.BRIGHT_RED, bold=True)

    raise typer.Exit(code=result.return_code)


def run_jstest_command(
    context: ProjectContext,
    *,
    setup: bool,
    skip_services: bool,
    extra_args: Sequence[str],
    quiet: bool,
) -> NoReturn:
    """Run ``run_jstest()`` and exit with its result, for `library`/`repository jstest`."""
    console = ConsoleOutput(quiet=quiet)
    if setup:
        console.info("🛠️  Setting up JavaScript tests...", fg=typer.colors.BRIGHT_BLUE, bold=True)
    else:
        console.info("🧪 Running JavaScript tests...", fg=typer.colors.BRIGHT_BLUE, bold=True)

    try:
        result = run_jstest(
            context,
            setup=setup,
            skip_services=skip_services,
            extra_args=list(extra_args),
            quiet=quiet,
        )
    except OARepoError as e:
        console.error(f"❌ Error running jstest: {e}", fg=typer.colors.BRIGHT_RED, bold=True)
        raise typer.Exit(code=1) from e

    if result.success:
        console.success("✨ ✓ JavaScript tests complete!", fg=typer.colors.BRIGHT_GREEN, bold=True)
    else:
        console.error("❌ JavaScript tests failed!", fg=typer.colors.BRIGHT_RED, bold=True)

    raise typer.Exit(code=result.return_code)
