# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence
    from pathlib import Path


@dataclass
class ProcessResult:
    """Result of a subprocess execution."""

    returncode: int
    stdout: str
    stderr: str
    command: Sequence[str]
    cwd: Path
    duration_ms: int

    @property
    def success(self) -> bool:
        """Return True if command executed successfully (exit code 0)."""
        return self.returncode == 0

    def check(self) -> ProcessResult:
        """Raise ProcessExecutionError if command failed.

        Returns:
            Self if successful.

        Raises:
            ProcessExecutionError: If returncode is non-zero.
        """
        if not self.success:
            from oarepo_cli.core.errors import ProcessExecutionError

            raise ProcessExecutionError(
                message=f"Command failed with exit code {self.returncode}",
                command=list(self.command),
                returncode=self.returncode,
                stdout=self.stdout,
                stderr=self.stderr,
            )
        return self


class ProcessExecutor(ABC):
    """Abstract interface for executing external processes."""

    @abstractmethod
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
        """
        Execute a command and wait for completion.

        Args:
            command: List of arguments (never shell string)
            cwd: Working directory
            env: Environment variables (merged with parent)
            capture_output: Capture stdout/stderr strings
            check: Raise on non-zero exit code
            forward_stdout: Stream output while capturing
            timeout: Maximum execution time in seconds

        Returns:
            ProcessResult with exit code, output, timing

        Raises:
            ProcessExecutionError: If check=True and returncode != 0
            TimeoutExceeded: If timeout is exceeded
        """

    @abstractmethod
    def stream(
        self,
        command: Sequence[str],
        *,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
    ) -> Iterator[str]:
        """
        Execute a command and yield output lines as they're produced.

        Use for long-running commands where real-time output is needed.

        Yields:
            Lines of stdout interleaved with stderr
        """

    @abstractmethod
    def get_output(
        self,
        command: Sequence[str],
        *,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
    ) -> str:
        """
        Execute a command and return stripped stdout.

        Convenience method for commands like `python -c "print(...)"`.

        Returns:
            Stripped stdout output
        """
