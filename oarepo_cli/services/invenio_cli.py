# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Invenio-CLI integration for OARepo repository projects."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, NoReturn

if TYPE_CHECKING:
    from collections.abc import Sequence

    from oarepo_cli.core.context import ProjectContext

from oarepo_cli.services import process


def _default_prerelease_env() -> dict[str, str]:
    """Base env for uv invocations in a repository project.

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
    demand via ``uvx`` from a hardcoded git ref (``repository_runner.sh``'s
    ``run_invenio_cli``, marked there as "temporary implementation until
    release" -- that release has since happened). Mirrors
    ``services.lint._tool_path``'s identical rationale for ruff/ty.

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
        interactive=not quiet,
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
        env: Additional environment variables (merged with this process's
            own environment -- unlike ``run_invenio_cli``, there's no
            subprocess env-merging safety net once this replaces it)

    Raises:
        OSError: If the invenio-cli binary can't be exec'd (not found, not
            executable, ...)
    """
    run_env = {**os.environ, **_default_prerelease_env()}
    if env:
        run_env.update(env)

    os.chdir(context.root_directory)
    binary = _invenio_cli_path()
    os.execvpe(binary, [binary, *args], run_env)
