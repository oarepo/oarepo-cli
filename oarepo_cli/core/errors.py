# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable


class OARepoError(Exception):
    """Base exception for all OARepo CLI errors."""

    exit_code: int = 1

    def __init__(self, message: str, *args: object) -> None:
        super().__init__(message, *args)
        self.message = message


class ConfigurationError(OARepoError):
    """Raised when configuration is invalid or missing."""

    exit_code: int = 10


class VersionMismatchError(OARepoError):
    """Raised when version requirements are not met."""

    exit_code: int = 11


class ProcessExecutionError(OARepoError):
    """Raised when a subprocess execution fails."""

    exit_code: int = 12

    def __init__(
        self,
        message: str,
        *,
        command: list[str],
        returncode: int,
        stdout: str | None = None,
        stderr: str | None = None,
    ) -> None:
        super().__init__(message)
        self.command = command
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr

    def __str__(self) -> str:
        parts = [super().__str__()]
        parts.append(f"Command: {' '.join(self.command)}")
        parts.append(f"Return code: {self.returncode}")
        if self.stdout:
            parts.append(f"Stdout: {self.stdout}")
        if self.stderr:
            parts.append(f"Stderr: {self.stderr}")
        return "\n".join(parts)


class FileNotFoundError(OARepoError):
    """Raised when a required file or directory is not found."""

    exit_code: int = 13


class ValidationError(OARepoError):
    """Raised when validation of data or configuration fails."""

    exit_code: int = 14


class LockAcquisitionError(OARepoError):
    """Raised when lock file cannot be acquired."""

    exit_code: int = 15


def safe_run(
    func: Callable[..., object],
    *args: object,
    check: bool = True,
    **kwargs: object,
) -> object:
    """
    Wrap a function call with consistent error handling.

    Args:
        func: The function to execute
        *args: Positional arguments to pass to the function
        check: If True, raise an exception on failure
        **kwargs: Keyword arguments to pass to the function

    Returns:
        The result of the function call

    Raises:
        OARepoError: If check=True and the function raises an OARepoError subclass
    """
    try:
        return func(*args, **kwargs)
    except OARepoError as e:
        if check:
            raise
        return e
