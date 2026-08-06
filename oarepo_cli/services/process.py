# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Subprocess execution helpers: run a command, or exec-replace this process."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Sequence

from oarepo_cli.configuration.constants import OAREPO_ENV_DEFAULTS
from oarepo_cli.core import signals

# Environment variables that should be stripped when running subprocesses
# to prevent oarepo-cli's own venv from leaking into project venvs
VENV_ENV_VARS = {
    "VIRTUAL_ENV",  # Path to active venv
    "VIRTUAL_ENV_PROMPT",  # Venv prompt customization
    "_OLD_VIRTUAL_PATH",  # Original PATH before venv activation
    "_OLD_VIRTUAL_PYTHONHOME",  # Original PYTHONHOME before venv activation
}


class ProcessOutputMode(Enum):
    """Output handling mode for subprocess execution.

    Attributes:
        CAPTURE: Capture stdout/stderr silently (default)
        FORWARD: Capture stdout/stderr AND display in real-time
        INTERACTIVE: Real-time output only, no capture (for interactive commands)

    """

    CAPTURE = "capture"  # Capture only, no display
    FORWARD = "forward"  # Capture + display in real-time
    INTERACTIVE = "interactive"  # Display only, no capture


@dataclass
class ProcessResult:
    """Result of a subprocess execution."""

    return_code: int
    stdout: str
    stderr: str
    command: Sequence[str]
    cwd: Path
    duration_ms: int

    @property
    def success(self) -> bool:
        """Return True if command executed successfully (exit code 0)."""
        return self.return_code == 0

    def check(self) -> ProcessResult:
        """Raise ProcessExecutionError if command failed.

        Returns:
            Self if successful.

        Raises:
            ProcessExecutionError: If return_code is non-zero.

        """
        if not self.success:
            from oarepo_cli.core.errors import ProcessExecutionError

            raise ProcessExecutionError(
                message=f"Command failed with exit code {self.return_code}",
                command=list(self.command),
                returncode=self.return_code,
                stdout=self.stdout,
                stderr=self.stderr,
            )
        return self


def _strip_venv_vars(env: dict[str, str]) -> dict[str, str]:
    """Strip virtual environment variables from environment.

    When oarepo-cli is called from within its own venv, VIRTUAL_ENV and
    related variables would leak into subprocesses and cause them to use
    the wrong venv. This function removes those variables and also strips
    the venv's bin directory from PATH.

    Args:
        env: Environment dictionary to clean

    Returns:
        New environment dictionary without venv variables

    """
    cleaned = {k: v for k, v in env.items() if k not in VENV_ENV_VARS}

    # Strip venv bin directory from PATH if VIRTUAL_ENV was set
    if "VIRTUAL_ENV" in env and "PATH" in cleaned:
        venv_path = env["VIRTUAL_ENV"]
        # Venv bin directories follow platform conventions:
        # Unix: {venv}/bin, Windows: {venv}\\Scripts
        if sys.platform == "win32":
            venv_bin = f"{venv_path}\\Scripts"
        else:
            venv_bin = f"{venv_path}/bin"

        # Remove venv bin from PATH
        path_parts = cleaned["PATH"].split(os.pathsep)
        cleaned_path_parts = [p for p in path_parts if not (p == venv_bin or p.rstrip("/\\") == venv_bin.rstrip("/\\"))]
        cleaned["PATH"] = os.pathsep.join(cleaned_path_parts)

    return cleaned


def get_system_path() -> str:
    """Return PATH with the currently active venv's bin directory stripped out.

    Mirrors ``repository_runner.sh``'s ``get_highest_available_python``,
    which temporarily removes the activated venv from PATH before searching
    for a system Python interpreter. Without this, resolving e.g.
    ``python3.14`` while a project's own venv is activated finds that
    venv's own interpreter -- which is wrong for anything that needs to
    (re)create that very venv, e.g. ``shutil.which()`` calls used to pick
    the interpreter for ``uv venv --python ...`` after ``repository
    upgrade`` has just removed it.

    Returns:
        PATH string with the active venv's bin directory removed, if any

    """
    return _strip_venv_vars(dict(os.environ)).get("PATH", os.environ.get("PATH", ""))


def build_subprocess_env(
    env: dict[str, str] | None = None,
    *,
    strip_venv: bool = True,
    include_oarepo_defaults: bool = True,
) -> dict[str, str]:
    """Build a full environment dict for a subprocess or ``os.execve``/``os.execvpe`` call.

    The single source of truth for env-var handling shared by every
    command-execution path in this codebase: :func:`run` and every
    exec-based passthrough (``services.invenio_cli.exec_invenio_cli``,
    ``services.server.ServerRunner._exec_bare_invenio``,
    ``services.repository.exec_invenio``/``exec_shell``, ``cli.library``'s
    ``library_shell``/``library_invenio``, ``services.js_tools.run_jstest``'s
    real test-run path) all call this rather than build their own env dict,
    so venv-stripping and ``OAREPO_ENV_DEFAULTS`` apply identically
    everywhere a subprocess or exec call is made.

    Args:
        env: Custom environment variables, applied last (override everything else)
        strip_venv: If True, strip ``VIRTUAL_ENV`` and related variables to
            prevent oarepo-cli's own venv from leaking into a target
            project's venv
        include_oarepo_defaults: If True, include ``OAREPO_ENV_DEFAULTS``
            (``UV_EXTRA_INDEX_URL``, ``INVENIO_*`` settings, etc.), only
            where not already set in the parent environment

    Returns:
        A full environment dict, suitable for ``subprocess.run(env=...)``/
        ``os.execve``/``os.execvpe``

    """
    run_env = dict(os.environ)

    if strip_venv:
        run_env = _strip_venv_vars(run_env)

    if include_oarepo_defaults:
        for key, value in OAREPO_ENV_DEFAULTS.items():
            if key not in run_env:
                run_env[key] = value

    if env is not None:
        run_env.update(env)

    return run_env


def _run_subprocess(
    command: Sequence[str],
    *,
    cwd: Path | None,
    env: dict[str, str],
    capture: bool,
) -> tuple[int, str, str]:
    """Run ``command`` via ``Popen``, registering it so a SIGTERM can be forwarded to it.

    Mirrors ``subprocess.run()``'s own semantics exactly (kills the child on
    ``KeyboardInterrupt``/any other exception raised while waiting for it)
    but keeps a reference to the ``Popen`` object so ``core.signals`` can
    forward a SIGTERM to it -- something ``subprocess.run()`` itself
    doesn't expose a hook for.
    """
    popen_kwargs: dict[str, Any] = {"cwd": cwd, "env": env}
    if capture:
        popen_kwargs.update(
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

    with subprocess.Popen(command, **popen_kwargs) as proc:  # noqa: S603
        signals.register_active_process(proc)
        try:
            stdout, stderr = proc.communicate()
        except BaseException:
            proc.kill()
            raise
        finally:
            signals.unregister_active_process()

    return proc.returncode, stdout or "", stderr or ""


def run(  # noqa: PLR0913 too many arguments ok here
    command: Sequence[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    output_mode: ProcessOutputMode = ProcessOutputMode.CAPTURE,
    check: bool = True,
    strip_venv: bool = True,
) -> ProcessResult:
    """Execute a command and wait for completion. Never uses shell=True.

    Deliberately no timeout: commands this is used for (``uv sync``,
    docker image pulls, ``copier`` template rendering) can legitimately run
    long, and a fixed limit would kill a healthy operation just as often as
    a stuck one. A SIGTERM received while this is running is forwarded to
    the child (see ``core.signals``) and waited for, however long that
    takes.

    Args:
        command: List of command arguments (never a shell string)
        cwd: Working directory for the command
        env: Environment variables (merged with parent environment)
        output_mode: How to handle command output (CAPTURE/FORWARD/INTERACTIVE)
        check: Raise ProcessExecutionError on non-zero exit code
        strip_venv: Strip VIRTUAL_ENV and related variables (default: True)
                    to prevent oarepo-cli's own venv from leaking

    Returns:
        ProcessResult with exit code, output, and timing

    Raises:
        ProcessExecutionError: If check=True and return_code != 0

    """
    from oarepo_cli.core.errors import ProcessExecutionError

    run_env = build_subprocess_env(env, strip_venv=strip_venv)
    start_time = time.time()
    capture = output_mode != ProcessOutputMode.INTERACTIVE

    returncode, stdout, stderr = _run_subprocess(command, cwd=cwd, env=run_env, capture=capture)

    duration_ms = int((time.time() - start_time) * 1000)

    process_result = ProcessResult(
        return_code=returncode,
        stdout=stdout,
        stderr=stderr,
        command=command,
        cwd=cwd or Path.cwd(),
        duration_ms=duration_ms,
    )

    # Forward mode: also display the captured output
    if output_mode == ProcessOutputMode.FORWARD:
        if stdout:
            pass
        if stderr:
            pass

    if check and returncode != 0:
        raise ProcessExecutionError(
            message=f"Command failed with exit code {returncode}",
            command=list(command),
            returncode=returncode,
            stdout=stdout if capture else None,
            stderr=stderr if capture else None,
        )

    return process_result


def get_output(
    command: Sequence[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    strip_venv: bool = True,
) -> str:
    """Execute a command and return stripped stdout.

    Convenience function for commands like `python -c "print(...)"`.

    Args:
        command: List of command arguments
        cwd: Working directory for the command
        env: Environment variables (merged with parent)
        strip_venv: Strip VIRTUAL_ENV and related variables (default: True)

    Returns:
        Stripped stdout output

    """
    result = run(
        command,
        cwd=cwd,
        env=env,
        check=False,
        strip_venv=strip_venv,
    )
    return result.stdout.strip()
