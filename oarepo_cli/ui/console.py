# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Console output utilities for OARepo CLI."""

from __future__ import annotations

from typing import Any

import typer


class ConsoleOutput:
    """Manages console output with quiet mode support.

    Provides info/success/warning/error methods that respect the quiet flag.
    Error and warning messages are always shown, even in quiet mode.
    Info and success messages are suppressed when quiet=True.
    """

    def __init__(self, quiet: bool = False) -> None:
        """Initialize console output handler.

        Args:
            quiet: If True, suppress info/success messages (errors/warnings still shown)
        """
        self._quiet = quiet

    def info(self, message: str, **kwargs: Any) -> None:
        """Print an info message (suppressed in quiet mode).

        Args:
            message: Message to print
            **kwargs: Same arguments as typer.secho (fg, bg, bold, etc.)
        """
        if not self._quiet:
            typer.secho(message, **kwargs)

    def success(self, message: str, **kwargs: Any) -> None:
        """Print a success message (suppressed in quiet mode).

        Args:
            message: Message to print
            **kwargs: Same arguments as typer.secho (fg, bg, bold, etc.)
        """
        if not self._quiet:
            typer.secho(message, **kwargs)

    def warning(self, message: str, **kwargs: Any) -> None:
        """Print a warning message (always shown, even in quiet mode).

        Args:
            message: Message to print
            **kwargs: Same arguments as typer.secho (fg, bg, bold, etc.)
                     err=True by default for warnings
        """
        # Default to stderr for warnings
        if "err" not in kwargs:
            kwargs["err"] = True
        typer.secho(message, **kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        """Print an error message (always shown, even in quiet mode).

        Args:
            message: Message to print
            **kwargs: Same arguments as typer.secho (fg, bg, bold, etc.)
                     err=True by default for errors
        """
        # Default to stderr for errors
        if "err" not in kwargs:
            kwargs["err"] = True
        typer.secho(message, **kwargs)
