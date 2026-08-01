# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

from __future__ import annotations

import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence


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


def _merge_env(env: dict[str, str] | None) -> dict[str, str] | None:
    if env is None:
        return None
    run_env = dict(**os.environ)
    run_env.update(env)
    return run_env


def run(
    command: Sequence[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    capture_output: bool = True,
    check: bool = True,
    forward_stdout: bool = False,
    timeout: float | None = None,
) -> ProcessResult:
    """Execute a command and wait for completion. Never uses shell=True.

    Args:
        command: List of command arguments (never a shell string)
        cwd: Working directory for the command
        env: Environment variables (merged with parent environment)
        capture_output: Whether to capture stdout/stderr as strings
        check: Raise ProcessExecutionError on non-zero exit code
        forward_stdout: Stream output to console while capturing
        timeout: Maximum execution time in seconds

    Returns:
        ProcessResult with exit code, output, and timing

    Raises:
        ProcessExecutionError: If check=True and return_code != 0
        TimeoutExceeded: If timeout is exceeded
    """
    from oarepo_cli.core.errors import ProcessExecutionError, TimeoutExceeded

    run_env = _merge_env(env)
    start_time = time.time()

    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            env=run_env,
            capture_output=capture_output,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )

        duration_ms = int((time.time() - start_time) * 1000)

        process_result = ProcessResult(
            return_code=result.returncode,
            stdout=result.stdout if capture_output else "",
            stderr=result.stderr if capture_output else "",
            command=command,
            cwd=cwd or Path.cwd(),
            duration_ms=duration_ms,
        )

        if forward_stdout and capture_output:
            if result.stdout:
                print(result.stdout, end="")
            if result.stderr:
                print(result.stderr, end="", file=sys.stderr)

        if check and result.returncode != 0:
            raise ProcessExecutionError(
                message=f"Command failed with exit code {result.returncode}",
                command=list(command),
                returncode=result.returncode,
                stdout=result.stdout if capture_output else None,
                stderr=result.stderr if capture_output else None,
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
) -> Iterator[str]:
    """Execute a command and yield output lines as they're produced.

    Use for long-running commands where real-time output is needed.

    Args:
        command: List of command arguments
        cwd: Working directory for the command
        env: Environment variables (merged with parent)

    Yields:
        Lines of stdout interleaved with stderr
    """
    run_env = _merge_env(env)

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
) -> str:
    """Execute a command and return stripped stdout.

    Convenience function for commands like `python -c "print(...)"`.

    Args:
        command: List of command arguments
        cwd: Working directory for the command
        env: Environment variables (merged with parent)

    Returns:
        Stripped stdout output
    """
    result = run(
        command,
        cwd=cwd,
        env=env,
        capture_output=True,
        check=False,
    )
    return result.stdout.strip()
