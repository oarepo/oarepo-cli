# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Invenio-CLI integration: delegation and exec-replacement for repository commands.

This module provides two patterns for invoking the CESNET-patched invenio-cli
(installed from the CESNET GitLab PyPI registry, verified at startup by
core/dependency_check.py):

1. **Blocking delegation** (`run_invenio_cli`): Run `invenio-cli <args>` as a
   subprocess, wait for completion, return exit code + output. Used by:
   - `repository services` subcommands (setup/start/stop/destroy)
   - Any command that needs to capture/inspect invenio-cli's output

2. **Exec-replacement** (`exec_invenio_cli`): Replace the current Python process
   with `invenio-cli <args>` via os.execvpe(), never returning. Used by:
   - `repository cli` (passes arbitrary invenio commands)
   - `repository reset`/`info`/`translations` (thin passthroughs)
   - Any command where the user expects to interact with invenio-cli directly

Key Invariant:
- Exit codes are preserved exactly (never collapsed to 0/1)
- Environment variables from .env-services are passed through
- VIRTUAL_ENV stripping happens via process.build_subprocess_env()

Why Exec-Replacement?
Some invenio-cli commands expect a TTY and/or set up signal handlers (e.g.
`invenio run`). Running them as a subprocess breaks this. Exec-replacement
makes oarepo-cli transparent: the user sees invenio-cli's exact behavior,
including Ctrl+C handling, progress bars, colored output, etc.

See Also:
- core/dependency_check.py: Validates invenio-cli is the CESNET-patched version
- services/process.py: build_subprocess_env() handles venv stripping
- cli/repository.py: Commands that use these functions

"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, NoReturn

if TYPE_CHECKING:
    from collections.abc import Sequence

    from oarepo_cli.core.context import ProjectContext

from oarepo_cli.services import process
from oarepo_cli.services.process import ProcessOutputMode


def _default_prerelease_env() -> dict[str, str]:
    """Set base env for uv invocations in a repository project.

    Mirrors ``repository_runner.sh``'s ``export UV_PRERELEASE=${UV_PRERELEASE:-"allow"}``:
    every uv command run for a repository allows pre-release versions (e.g. RDM
    release candidates) by default, unless the user already set the variable
    themselves. Applied consistently to every uv command in this module so they
    all agree on the same pre-release mode -- otherwise uv detects a mismatch
    between invocations and forces a full lockfile re-resolution.
    """
    return {"UV_PRERELEASE": os.environ.get("UV_PRERELEASE", "allow")}


def _invenio_cli_path() -> str:
    """Resolve the invenio-cli binary installed alongside oarepo-cli's own venv.

    oarepo-cli depends directly on invenio-cli (see pyproject.toml's
    ``[tool.uv.sources] invenio-cli = { index = "cesnet" }``, verified as
    the CESNET-patched build at startup by
    ``core.dependency_check.check_invenio_cli_version()``). invenio-cli
    purely orchestrates the target project via subprocesses/docker -- it
    doesn't need to run under the target project's own interpreter -- so
    it's resolved next to the running interpreter rather than fetched on
    demand via ``uvx`` from a git ref, unlike ``repository_runner.sh``'s
    ``run_invenio_cli``. Mirrors ``services.lint._tool_path``'s identical
    rationale for ruff/ty.

    Returns:
        Absolute path to the binary if found next to the current
        interpreter, otherwise the bare name (resolved via PATH by the
        subprocess call).

    """
    candidate = Path(sys.executable).parent / "invenio-cli"
    return str(candidate) if candidate.exists() else "invenio-cli"


def _build_command(args: Sequence[str]) -> list[str]:
    """Construct the invenio-cli command line."""
    return [_invenio_cli_path(), *args]


def run_invenio_cli(
    context: ProjectContext,
    args: Sequence[str],
    *,
    quiet: bool = False,
    check: bool = True,
    env: dict[str, str] | None = None,
) -> process.ProcessResult:
    """Run invenio-cli command, and wait for it to complete.

    Args:
        context: Project context with paths and configuration
        args: Arguments to pass to invenio-cli
        quiet: If True, suppress real-time subprocess output
        check: If True, raise ProcessExecutionError on non-zero exit
        env: Additional environment variables to pass to the subprocess

    Returns:
        ProcessResult from the invenio-cli command

    Raises:
        ProcessExecutionError: If check=True and command fails

    """
    run_env = _default_prerelease_env()
    if env:
        run_env.update(env)

    return process.run(
        _build_command(args),
        cwd=context.root_directory,
        check=check,
        output_mode=ProcessOutputMode.INTERACTIVE if not quiet else ProcessOutputMode.CAPTURE,
        env=run_env,
    )


def exec_invenio_cli(
    context: ProjectContext,
    args: Sequence[str],
    *,
    env: dict[str, str] | None = None,
) -> NoReturn:
    """Replace the current process with invenio-cli. Never returns.

    Same command construction as ``run_invenio_cli``, but for the final,
    long-running invenio-cli command in a command's lifecycle (``invenio-cli
    run``, used by ``services.server.ServerRunner``), where nothing needs to
    happen in this process afterward -- mirrors ``cli/library.py``'s
    ``library_shell``/``library_invenio``. Lets a terminal Ctrl+C (or any
    signal sent to this process) hit invenio-cli directly, exactly as if the
    user had run it themselves: invenio-cli's own ``run`` command already
    installs its own SIGINT handling for the child processes it spawns
    internally (web server, Celery worker, jobs scheduler -- see
    ``invenio_cli.commands.local.LocalCommands._handle_sigint`` in the
    installed package), which only works correctly if invenio-cli believes
    itself to be the foreground process, not a supervised child of ours.

    Args:
        context: Project context with paths and configuration -- also
            ``chdir``s into ``context.root_directory`` first, since
            ``execve`` has no ``cwd`` parameter of its own and invenio-cli
            discovers its own project via the process's current directory
            (matching ``run_invenio_cli``/the pre-exec ``services start``
            call, which both pass ``cwd=`` explicitly)
        args: Arguments to pass to invenio-cli
        env: Additional environment variables, applied on top of
            ``process.build_subprocess_env()``'s usual stripping/defaults
            (same as ``run_invenio_cli``'s own env handling via
            ``process.run()`` -- there's no other subprocess env-merging
            safety net once this replaces the current process)

    Raises:
        OSError: If the invenio-cli binary can't be exec'd (not found, not
            executable, ...)

    """
    run_env = process.build_subprocess_env({**_default_prerelease_env(), **(env or {})})

    os.chdir(context.root_directory)
    binary = _invenio_cli_path()
    os.execvpe(binary, [binary, *args], run_env)  # noqa S606 no shell is ok here, replacing the process
