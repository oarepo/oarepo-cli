# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Subprocess execution helpers: run/stream a command, or exec-replace this process."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

from oarepo_cli.configuration.constants import OAREPO_ENV_DEFAULTS, STREAM_ENV_DEFAULTS

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
        cleaned_path_parts = [
            p
            for p in path_parts
            if not (p == venv_bin or p.rstrip("/\\") == venv_bin.rstrip("/\\"))
        ]
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
    command-execution path in this codebase: :func:`run`, :func:`stream`,
    and every exec-based passthrough (``services.invenio_cli.exec_invenio_cli``,
    ``services.server.ServerRunner._exec_bare_invenio``,
    ``services.repository.exec_invenio``/``exec_shell``, ``cli.library``'s
    ``library_shell``/``library_invenio``, ``services.js_tools.run_jstest``'s
    real test-run path). Previously duplicated -- with subtly different
    behavior each time -- inline in :func:`run` (via the old, private
    ``_merge_env``), a second time in :func:`stream`, and not at all in any
    of the exec-based functions (which just did
    ``{**os.environ, <manual overrides>}`` directly, silently missing both
    the venv-stripping and the OAREPO_ENV_DEFAULTS every blocking call got).

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


def run(
    command: Sequence[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    output_mode: ProcessOutputMode = ProcessOutputMode.CAPTURE,
    check: bool = True,
    timeout: float | None = None,
    strip_venv: bool = True,
) -> ProcessResult:
    """Execute a command and wait for completion. Never uses shell=True.

    Args:
        command: List of command arguments (never a shell string)
        cwd: Working directory for the command
        env: Environment variables (merged with parent environment)
        output_mode: How to handle command output (CAPTURE/FORWARD/INTERACTIVE)
        check: Raise ProcessExecutionError on non-zero exit code
        timeout: Maximum execution time in seconds
        strip_venv: Strip VIRTUAL_ENV and related variables (default: True)
                    to prevent oarepo-cli's own venv from leaking

    Returns:
        ProcessResult with exit code, output, and timing

    Raises:
        ProcessExecutionError: If check=True and return_code != 0
        TimeoutExceeded: If timeout is exceeded
    """
    from oarepo_cli.core.errors import ProcessExecutionError, TimeoutExceeded

    run_env = build_subprocess_env(env, strip_venv=strip_venv)
    start_time = time.time()

    # Interactive mode: inherit stdout/stderr for real-time output
    if output_mode == ProcessOutputMode.INTERACTIVE:
        try:
            result = subprocess.run(
                command,
                cwd=cwd,
                env=run_env,
                timeout=timeout,
            )

            duration_ms = int((time.time() - start_time) * 1000)

            process_result = ProcessResult(
                return_code=result.returncode,
                stdout="",
                stderr="",
                command=command,
                cwd=cwd or Path.cwd(),
                duration_ms=duration_ms,
            )

            if check and result.returncode != 0:
                raise ProcessExecutionError(
                    message=f"Command failed with exit code {result.returncode}",
                    command=list(command),
                    returncode=result.returncode,
                    stdout=None,
                    stderr=None,
                )

            return process_result

        except subprocess.TimeoutExpired as exc:
            raise TimeoutExceeded(
                command=list(command),
                timeout=timeout,
                stdout=None,
                stderr=None,
            ) from exc

    # Capture or Forward mode: capture output
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            env=run_env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )

        duration_ms = int((time.time() - start_time) * 1000)

        process_result = ProcessResult(
            return_code=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            command=command,
            cwd=cwd or Path.cwd(),
            duration_ms=duration_ms,
        )

        # Forward mode: also display the captured output
        if output_mode == ProcessOutputMode.FORWARD:
            if result.stdout:
                print(result.stdout, end="")
            if result.stderr:
                print(result.stderr, end="", file=sys.stderr)

        if check and result.returncode != 0:
            raise ProcessExecutionError(
                message=f"Command failed with exit code {result.returncode}",
                command=list(command),
                returncode=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
            )

        return process_result

    except subprocess.TimeoutExpired as exc:
        stdout = ""
        stderr = ""
        if exc.stdout is not None:
            stdout = exc.stdout.decode("utf-8", errors="replace")
        if exc.stderr is not None:
            stderr = exc.stderr.decode("utf-8", errors="replace")

        raise TimeoutExceeded(
            command=list(command),
            timeout=timeout,
            stdout=stdout,
            stderr=stderr,
        ) from exc


def stream(
    command: Sequence[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    strip_venv: bool = True,
) -> Iterator[str]:
    """Execute a command and yield output lines as they're produced.

    Use for long-running commands where real-time output is needed.

    Sets PYTHONUNBUFFERED=1 by default: stdout isn't a TTY here (it's a pipe),
    so a Python child (e.g. `invenio run`) would otherwise block-buffer its
    output and defeat real-time streaming. Pass PYTHONUNBUFFERED explicitly in
    `env` to override. This has no effect on non-Python commands.

    Args:
        command: List of command arguments
        cwd: Working directory for the command
        env: Environment variables (merged with parent, PYTHONUNBUFFERED=1 default)
        strip_venv: Strip VIRTUAL_ENV and related variables (default: True)

    Yields:
        Lines of stdout interleaved with stderr
    """
    run_env = build_subprocess_env(strip_venv=strip_venv)

    # Add streaming defaults, then apply custom environment on top (same
    # precedence as before: custom env overrides everything, including
    # STREAM_ENV_DEFAULTS)
    run_env.update(STREAM_ENV_DEFAULTS)
    if env is not None:
        run_env.update(env)

    process = subprocess.Popen(
        command,
        cwd=cwd,
        env=run_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )

    if process.stdout is not None:
        for line in process.stdout:
            yield line.rstrip("\n")

    process.wait()


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
