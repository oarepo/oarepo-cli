# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Reusable command execution wrappers for CLI commands.

This module provides decorators to reduce boilerplate in CLI command functions
by handling common patterns like context discovery, console creation, and
consistent error handling.

Usage:
    @with_context_and_console(
        start_message="Starting operation...",
        success_message="Operation completed!",
        error_prefix="Error during operation",
    )
    def my_command(context: ProjectContext, console: ConsoleOutput, quiet: bool = False):
        # Your command implementation
        pass
"""

from __future__ import annotations

from functools import wraps
from typing import Any

import typer

from oarepo_cli.core.context import discover_context
from oarepo_cli.core.errors import OARepoError
from oarepo_cli.ui import ConsoleOutput as ConsoleOutputClass


def with_context_and_console(
    *,
    start_message: str | None = None,
    success_message: str | None = None,
    error_prefix: str = "Error",
    console_quiet_from_args: bool = True,
) -> Any:
    """Decorator to handle common CLI command pattern.

    Automatically:
    - Discovers project context
    - Creates ConsoleOutput
    - Shows start/success messages
    - Handles OARepoError exceptions and exits with code 1

    The decorated function should accept 'context' and 'console' as keyword
    arguments, which will be automatically injected.

    Args:
        start_message: Message to show before execution (with 🚀 emoji and blue color).
                      If None, no start message is shown.
        success_message: Message to show after success (with ✨ ✓ prefix and green color).
                        If None, no success message is shown.
        error_prefix: Prefix for error messages (default: "Error"). Will be formatted
                     as "❌ {error_prefix}: {exception_message}" in red.
        console_quiet_from_args: If True, extract 'quiet' from function kwargs to
                                control console output (default: True).

    Returns:
        Decorated function that handles context, console, and error handling.

    Example:
        @with_context_and_console(
            start_message="Starting services...",
            success_message="Services started successfully!",
            error_prefix="Error starting services",
        )
        def start_services(context: ProjectContext, console: ConsoleOutput, quiet: bool = False):
            # Implementation here
            services_mgr = ServicesLifecycleManager(context.config, context.root_directory, quiet=quiet)
            services_mgr.start_services()
    """

    def decorator(func: Any) -> Any:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Extract quiet flag from kwargs if needed
            quiet = bool(kwargs.get("quiet", False)) if console_quiet_from_args else False

            # Discover context and create console
            context = discover_context()
            console = ConsoleOutputClass(quiet=quiet)

            # Show start message
            if start_message:
                console.info(f"🚀 {start_message}", fg=typer.colors.BRIGHT_BLUE, bold=True)

            try:
                # Inject context and console into the function call
                result = func(*args, context=context, console=console, **kwargs)

                # Show success message
                if success_message:
                    console.success(
                        f"✨ ✓ {success_message}",
                        fg=typer.colors.BRIGHT_GREEN,
                        bold=True,
                    )

                return result

            except OARepoError as e:
                console.error(
                    f"❌ {error_prefix}: {e}",
                    fg=typer.colors.BRIGHT_RED,
                    bold=True,
                )
                raise typer.Exit(code=1) from e

        return wrapper

    return decorator


def with_context_only(func: Any) -> Any:
    """Decorator for commands that only need context discovery.

    Use for passthrough commands (shell, invenio) that handle their own
    console output and error handling. Only injects the 'context' parameter.

    The decorated function should accept 'context' as a keyword argument.

    Args:
        func: Function to decorate

    Returns:
        Decorated function that receives project context

    Example:
        @with_context_only
        def shell_command(context: ProjectContext, args: list[str]):
            # Implementation here - handles its own console and errors
            exec_shell(context, args)
    """

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        context = discover_context()
        return func(*args, context=context, **kwargs)

    return wrapper
