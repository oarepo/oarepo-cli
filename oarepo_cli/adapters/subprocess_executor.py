# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

from oarepo_cli.core.errors import ProcessExecutionError, TimeoutExceeded
from oarepo_cli.services.process import ProcessExecutor, ProcessResult


class SubprocessExecutor(ProcessExecutor):
    """Real implementation of ProcessExecutor using subprocess module.

    This executor safely runs external commands without shell injection risks.
    It never uses shell=True; all commands are passed as argument lists.

    Features:
    - UTF-8 encoding for all output
    - Timeout support for long-running commands
    - Basic signal handling (graceful shutdown)
    - Environment variable inheritance and override
    - Working directory specification
    """

    def run(
        self,
        command: Sequence[str],
        *,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        capture_output: bool = True,
        check: bool = True,
        forward_stdout: bool = False,
        timeout: float | None = None,
    ) -> ProcessResult:
        """Execute a command and wait for completion.

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
        # Merge with parent environment if custom env provided
        run_env = None
        if env is not None:
            run_env = dict(**os.environ)
            run_env.update(env)

        start_time = time.time()

        try:
            # Execute without shell=True for safety
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

            # Forward output if requested (while still capturing)
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
            duration_ms = int((time.time() - start_time) * 1000)

            # Extract any partial output before timeout
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
        self,
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
        # Merge with parent environment if custom env provided
        run_env = None
        if env is not None:
            run_env = dict(**os.environ)
            run_env.update(env)

        # Execute with pipes for streaming
        process = subprocess.Popen(
            command,
            cwd=cwd,
            env=run_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # Interleave stderr with stdout
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,  # Line buffered
        )

        if process.stdout is not None:
            for line in process.stdout:
                yield line.rstrip("\n")

        process.wait()

    def get_output(
        self,
        command: Sequence[str],
        *,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
    ) -> str:
        """Execute a command and return stripped stdout.

        Convenience method for commands like `python -c "print(...)"`.

        Args:
            command: List of command arguments
            cwd: Working directory for the command
            env: Environment variables (merged with parent)

        Returns:
            Stripped stdout output
        """
        result = self.run(
            command,
            cwd=cwd,
            env=env,
            capture_output=True,
            check=False,
        )
        return result.stdout.strip()
