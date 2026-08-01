# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import TYPE_CHECKING

from oarepo_cli.core.errors import TimeoutExceeded
from oarepo_cli.services.process import ProcessExecutor, ProcessResult

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence


class FakeProcessExecutor(ProcessExecutor):
    """Fake implementation of ProcessExecutor for testing.

    This fake executor simulates subprocess execution without actually
    running processes. It supports:

    - Pre-registered command responses
    - Simulated delays
    - Configurable exit codes, stdout, stderr
    - Verification of command parameters (cwd, env)
    """

    def __init__(self, execute_real_commands: bool = False) -> None:
        """Initialize the fake executor with empty command registry.

        Args:
            execute_real_commands: If True, execute real subprocess commands
                when no response is registered. Useful for contract tests.
        """
        self._command_registry: dict[tuple[str, ...] | str, dict] = {}
        self._last_command: list[str] | None = None
        self._last_cwd: Path | None = None
        self._last_env: dict[str, str] | None = None
        self._execute_real_commands = execute_real_commands

    def register_response(
        self,
        command: Sequence[str],
        *,
        returncode: int = 0,
        stdout: str = "",
        stderr: str = "",
        duration_ms: int = 10,
    ) -> None:
        """Register a response for a specific command.

        Args:
            command: The command sequence to match
            returncode: Exit code to return
            stdout: Standard output to simulate
            stderr: Standard error to simulate
            duration_ms: Simulated execution time in milliseconds
        """
        self._command_registry[tuple(command)] = {
            "returncode": returncode,
            "stdout": stdout,
            "stderr": stderr,
            "duration_ms": duration_ms,
        }

    def register_regex_response(
        self,
        pattern: str,
        *,
        returncode: int = 0,
        stdout: str = "",
        stderr: str = "",
        duration_ms: int = 10,
    ) -> None:
        """Register a response that matches commands by regex pattern.

        Args:
            pattern: Regex pattern to match against command strings
            returncode: Exit code to return
            stdout: Standard output to simulate
            stderr: Standard error to simulate
            duration_ms: Simulated execution time in milliseconds
        """
        import re

        key = f"__regex__:{pattern}"
        self._command_registry[key] = {
            "returncode": returncode,
            "stdout": stdout,
            "stderr": stderr,
            "duration_ms": duration_ms,
            "pattern": re.compile(pattern),
        }

    def _find_response(self, command: Sequence[str]) -> dict:
        """Find the response for a given command.

        Args:
            command: The command to look up

        Returns:
            Response dict with returncode, stdout, stderr, duration_ms

        Raises:
            ValueError: If no response is registered for the command
        """
        # Try exact match first
        key = tuple(command)
        if key in self._command_registry:
            return self._command_registry[key]

        # Try regex patterns
        command_str = " ".join(command)
        for value in self._command_registry.values():
            if "pattern" in value and value["pattern"].search(command_str):
                return value

        # Default response if nothing registered
        # If execute_real_commands is True, return marker to trigger real execution
        if self._execute_real_commands:
            return {"__execute_real": True}
        return {
            "returncode": 0,
            "stdout": "",
            "stderr": "",
            "duration_ms": 10,
        }

    def run(
        self,
        command: Sequence[str],
        *,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        capture_output: bool = True,
        check: bool = True,
        forward_stdout: bool = False,  # noqa: ARG002
        timeout: float | None = None,  # noqa: ARG002
    ) -> ProcessResult:
        """Execute a command (simulated).

        Args:
            command: List of arguments
            cwd: Working directory (stored for verification)
            env: Environment variables (stored for verification)
            capture_output: If False, stdout/stderr will be empty
            check: If True, raise on non-zero exit code
            forward_stdout: Ignored in fake implementation
            timeout: Ignored in fake implementation

        Returns:
            ProcessResult with simulated output

        Raises:
            ProcessExecutionError: If check=True and returncode != 0
        """
        from oarepo_cli.core.errors import ProcessExecutionError

        self._last_command = list(command)
        self._last_cwd = cwd
        self._last_env = env

        response = self._find_response(command)

        # Execute real command if requested and no registered response
        if response.get("__execute_real"):
            import subprocess

            start_time = time.time()

            # Merge with parent environment if custom env provided
            run_env = None
            if env is not None:
                run_env = dict(**os.environ)
                run_env.update(env)

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

                return ProcessResult(
                    return_code=result.returncode,
                    stdout=result.stdout if capture_output else "",
                    stderr=result.stderr if capture_output else "",
                    command=command,
                    cwd=cwd or Path.cwd(),
                    duration_ms=duration_ms,
                )
            except subprocess.TimeoutExpired as exc:
                duration_ms = int((time.time() - start_time) * 1000)
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

        # Simulate delay for fake responses
        start_time = time.time()
        time.sleep(response["duration_ms"] / 1000.0)
        duration_ms = int((time.time() - start_time) * 1000)

        # Ensure at least minimum duration for test reliability
        if duration_ms < response["duration_ms"]:
            duration_ms = response["duration_ms"]

        stdout = response["stdout"] if capture_output else ""
        stderr = response["stderr"] if capture_output else ""

        result = ProcessResult(
            return_code=response["returncode"],
            stdout=stdout,
            stderr=stderr,
            command=command,
            cwd=cwd or Path.cwd(),
            duration_ms=duration_ms,
        )

        if check and not result.success:
            raise ProcessExecutionError(
                message=f"Command failed with exit code {result.return_code}",
                command=list(command),
                returncode=result.return_code,
                stdout=stdout,
                stderr=stderr,
            )

        return result

    def stream(
        self,
        command: Sequence[str],
        *,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
    ) -> Iterator[str]:
        """Stream command output line by line (simulated).

        Args:
            command: List of arguments
            cwd: Working directory
            env: Environment variables

        Yields:
            Lines of output (stdout interleaved with stderr)
        """
        self._last_command = list(command)
        self._last_cwd = cwd
        self._last_env = env

        response = self._find_response(command)

        # Yield stdout lines
        for line in response["stdout"].splitlines():
            yield line

        # Yield stderr lines
        for line in response["stderr"].splitlines():
            yield line

    def get_output(
        self,
        command: Sequence[str],
        *,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
    ) -> str:
        """Get stripped stdout output (simulated).

        Args:
            command: List of arguments
            cwd: Working directory
            env: Environment variables

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

    @property
    def last_command(self) -> list[str] | None:
        """Get the last executed command."""
        return self._last_command

    @property
    def last_cwd(self) -> Path | None:
        """Get the last working directory."""
        return self._last_cwd

    @property
    def last_env(self) -> dict[str, str] | None:
        """Get the last environment variables."""
        return self._last_env

    def reset(self) -> None:
        """Reset all state including command registry."""
        self._command_registry.clear()
        self._last_command = None
        self._last_cwd = None
        self._last_env = None

    def clear_history(self) -> None:
        """Clear command history but keep registered responses."""
        self._last_command = None
        self._last_cwd = None
        self._last_env = None
