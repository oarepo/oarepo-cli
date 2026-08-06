# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Shared CLI-layer implementation for `library`/`repository` jslint/jstest.

Both `library jslint`/`jstest` and `repository jslint`/`jstest` are functionally
identical -- they discover the project context and delegate to
`services.js_tools.run_jslint()`/`run_jstest()`, which shell out to npm test
commands (jstest) or look for and execute ./node_modules/.bin/jslint (jslint).

This module provides the shared command implementations to avoid duplicating
the console output, error handling, and exit-code propagation logic across
`cli/library.py` and `cli/repository.py`. Each of those modules registers
their own `@library_app.command`/`@repository_app.command` Typer decorators,
but both immediately call the functions defined here.

Key Pattern:
- Thin delegation layer: no business logic lives here
- Exit codes are preserved exactly from the underlying npm/jslint processes
- Quiet flag is respected for suppressing console output
- Similar to `cli/lint_commands.py` (same pattern for lint/format/check)

See Also:
- services/js_tools.py: Actual implementation of JS linting/testing
- cli/library.py: library_jslint(), library_jstest() command registrations
- cli/repository.py: repository_jslint(), repository_jstest() registrations

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
        console.success("✨ ✓ JavaScript linting complete!", fg=typer.colors.BRIGHT_GREEN, bold=True)
    else:
        console.error("❌ JavaScript linting failed!", fg=typer.colors.BRIGHT_RED, bold=True)

    raise typer.Exit(code=result.return_code)


def run_jstest_command(
    context: ProjectContext,
    *,
    setup: bool,
    service_env: dict[str, str] | None,
    extra_args: Sequence[str],
    quiet: bool,
) -> NoReturn:
    """Run ``run_jstest()`` and exit with its result, for `library`/`repository jstest`.

    The caller is responsible for starting Docker services (if needed) and passing
    their connection environment variables via ``service_env``.

    ``run_jstest()`` never returns on successful test runs (it ``os.execve``s into
    Jest) -- only precondition failures (setup not implemented, missing ``invenio``
    binary) return a ``ProcessResult``, which this function then exits with.
    """
    console = ConsoleOutput(quiet=quiet)
    if setup:
        console.info("🛠️  Setting up JavaScript tests...", fg=typer.colors.BRIGHT_BLUE, bold=True)
    else:
        console.info("🧪 Running JavaScript tests...", fg=typer.colors.BRIGHT_BLUE, bold=True)

    try:
        result = run_jstest(
            context,
            setup=setup,
            service_env=service_env,
            extra_args=list(extra_args),
            quiet=quiet,
        )
    except OARepoError as e:
        console.error(f"❌ Error running jstest: {e}", fg=typer.colors.BRIGHT_RED, bold=True)
        raise typer.Exit(code=1) from e

    # Only precondition failures (setup not implemented, missing invenio binary)
    # return a ProcessResult -- successful test runs never return (os.execve)
    if result.success:
        console.success("✨ ✓ JavaScript tests complete!", fg=typer.colors.BRIGHT_GREEN, bold=True)
    else:
        console.error("❌ JavaScript tests failed!", fg=typer.colors.BRIGHT_RED, bold=True)

    raise typer.Exit(code=result.return_code)
