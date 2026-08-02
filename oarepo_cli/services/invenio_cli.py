# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Invenio-CLI integration for OARepo repository projects."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

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


def run_invenio_cli(
    context: ProjectContext,
    args: Sequence[str],
    *,
    quiet: bool = False,
    check: bool = True,
    env: dict[str, str] | None = None,
) -> process.ProcessResult:
    """Run invenio-cli command with the configured Python interpreter.

    Mirrors ``repository_runner.sh``'s ``run_invenio_cli`` function: executes
    invenio-cli via uvx with the project's Python version and OARepo branch.

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
    python_binary = context.python_binary

    # Construct uvx command to run invenio-cli
    # Uses the same approach as repository_runner.sh:
    # uvx --python="$PYTHON" \
    #     --with git+https://github.com/oarepo/oarepo-cli@rdm-14 \
    #     --from git+https://github.com/oarepo/invenio-cli@oarepo-feature-docker-environment \
    #     invenio-cli "$@"
    cmd = [
        "uvx",
        f"--python={python_binary}",
        "--with",
        "git+https://github.com/oarepo/oarepo-cli@rdm-14",
        "--from",
        "git+https://github.com/oarepo/invenio-cli@oarepo-feature-docker-environment",
        "invenio-cli",
        *args,
    ]

    run_env = _default_prerelease_env()
    if env:
        run_env.update(env)

    return process.run(
        cmd,
        cwd=context.root_directory,
        check=check,
        interactive=not quiet,
        env=run_env,
    )


def run_invenio_shell(
    context: ProjectContext,
    python_code: str,
    *,
    check: bool = True,
) -> process.ProcessResult:
    """Run Python code in the Invenio shell via uv run.

    Mirrors ``repository_runner.sh``'s ``in_invenio_shell`` function: executes
    Python code in the Invenio application context using `invenio shell`.

    Callers rely on parsing a value out of ``stdout`` (e.g. the last line),
    so output is always captured rather than streamed interactively -- like
    the bash version's ``$(... | tail -n1)``, which never shows the shell's
    startup logging to the user either.

    Args:
        context: Project context with paths and configuration
        python_code: Python code to execute in the Invenio shell
        check: If True, raise ProcessExecutionError on non-zero exit

    Returns:
        ProcessResult from the invenio shell command

    Raises:
        ProcessExecutionError: If check=True and command fails
    """
    # Disable the basic Python REPL to prevent interactive prompts
    env = _default_prerelease_env()
    env["PYTHON_BASIC_REPL"] = "0"

    cmd = [
        "uv",
        "run",
        "invenio",
        "shell",
        "--no-term-title",
        "-c",
        python_code,
    ]

    return process.run(
        cmd,
        cwd=context.root_directory,
        check=check,
        interactive=False,
        env=env,
    )
