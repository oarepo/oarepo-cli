# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Invenio-CLI integration for OARepo repository projects."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import subprocess
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


def _build_command(context: ProjectContext, args: Sequence[str]) -> list[str]:
    """Construct the uvx command line to run invenio-cli.

    Mirrors ``repository_runner.sh``'s ``run_invenio_cli`` function:
    uvx --python="$PYTHON" \\
        --with git+https://github.com/oarepo/oarepo-cli@rdm-14 \\
        --from git+https://github.com/oarepo/invenio-cli@oarepo-feature-docker-environment \\
        invenio-cli "$@"
    """
    return [
        "uvx",
        f"--python={context.python_binary}",
        "--with",
        "git+https://github.com/oarepo/oarepo-cli@rdm-14",
        "--from",
        "git+https://github.com/oarepo/invenio-cli@oarepo-feature-docker-environment",
        "invenio-cli",
        *args,
    ]


def run_invenio_cli(
    context: ProjectContext,
    args: Sequence[str],
    *,
    quiet: bool = False,
    check: bool = True,
    env: dict[str, str] | None = None,
) -> process.ProcessResult:
    """Run invenio-cli command with the configured Python interpreter, and wait for it.

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
        _build_command(context, args),
        cwd=context.root_directory,
        check=check,
        interactive=not quiet,
        env=run_env,
    )


def popen_invenio_cli(
    context: ProjectContext,
    args: Sequence[str],
    *,
    env: dict[str, str] | None = None,
) -> subprocess.Popen[bytes]:
    """Start invenio-cli as a foreground child process, without waiting for it.

    Same command construction as ``run_invenio_cli``, but for long-running
    invenio-cli commands (e.g. ``invenio-cli run``, used by
    ``services.server.ServerRunner``) that need direct process control --
    signal forwarding, explicit termination -- rather than a blocking wait.

    Args:
        context: Project context with paths and configuration
        args: Arguments to pass to invenio-cli
        env: Additional environment variables to pass to the subprocess

    Returns:
        The live Popen handle -- the caller owns its lifecycle
    """
    run_env = _default_prerelease_env()
    if env:
        run_env.update(env)

    return process.popen(
        _build_command(context, args),
        cwd=context.root_directory,
        env=run_env,
    )
