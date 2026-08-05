# Solution for Issue 3.1: Code Duplication in CLI Commands

**Issue:** The pattern of context discovery → ConsoleOutput creation → manager instantiation → error handling is duplicated across multiple CLI command functions.

## Analysis

After reviewing the codebase, I've identified several distinct patterns:

### Pattern 1: Simple Command Execution (Most Common)
```python
context = discover_context()
console = ConsoleOutput(quiet=quiet)
console.info("🚀 Starting...", fg=typer.colors.BRIGHT_BLUE, bold=True)
try:
    result = some_operation(context, quiet=quiet)
    console.success("✨ Success!", fg=typer.colors.BRIGHT_GREEN, bold=True)
except OARepoError as e:
    console.error(f"❌ Error: {e}", fg=typer.colors.BRIGHT_RED, bold=True)
    raise typer.Exit(code=1) from e
```

Examples: `_start_services_impl`, `_stop_services_impl`, `library_upgrade`, `library_clean`

### Pattern 2: Passthrough Commands (No Try/Catch)
```python
context = discover_context()
# Console always shows output for passthrough commands
console = ConsoleOutput(quiet=False)
some_operation(context, args)  # Exits directly with subprocess exit code
```

Examples: `library_shell`, `library_invenio`

### Pattern 3: Delegated Error Handling
```python
context = discover_context()
lint_commands.run_lint(context, fix=fix, quiet=quiet)
# The delegated function handles errors and exits
```

Examples: `library_lint`, `library_format`, `library_check`

### Pattern 4: Repository Commands with Pre-discovery Error Handling
```python
try:
    context = discover_context()
    console = ConsoleOutput(quiet=quiet)
    console.info("→ Installing...\n")
    repository.install_repository(context, quiet=quiet)
    console.success("✓ Success!\n", fg=typer.colors.BRIGHT_GREEN)
except OARepoError as e:
    console_err = ConsoleOutput(quiet=False)  # Always show errors
    console_err.error(f"✗ Failed: {e}\n", fg=typer.colors.RED)
    raise typer.Exit(1) from e
```

Examples: `install`, `upgrade`, `model_create` (in repository.py)

## Proposed Solution

Create a **decorator-based approach** that handles the common patterns while allowing customization:

### Option 1: Decorator with Callbacks (Recommended)

```python
# oarepo_cli/cli/command_wrapper.py
"""Reusable command execution wrappers for CLI commands."""

from __future__ import annotations

from functools import wraps
from typing import TYPE_CHECKING, Callable, TypeVar

import typer

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any, ParamSpec

    from oarepo_cli.core.context import ProjectContext

from oarepo_cli.core.context import discover_context
from oarepo_cli.core.errors import OARepoError
from oarepo_cli.ui import ConsoleOutput

P = ParamSpec("P")
R = TypeVar("R")


def with_context_and_console(
    *,
    start_message: str | None = None,
    success_message: str | None = None,
    error_prefix: str = "Error",
    console_quiet_from_args: bool = True,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator to handle common CLI command pattern.

    Automatically:
    - Discovers project context
    - Creates ConsoleOutput
    - Shows start/success messages
    - Handles OARepoError exceptions and exits with code 1

    Args:
        start_message: Message to show before execution (with 🚀 emoji)
        success_message: Message to show after success (with ✨ emoji)
        error_prefix: Prefix for error messages (default: "Error")
        console_quiet_from_args: If True, extract 'quiet' from function kwargs

    Usage:
        @with_context_and_console(
            start_message="Starting services...",
            success_message="Services started successfully!"
        )
        def my_command(context: ProjectContext, console: ConsoleOutput, quiet: bool = False):
            # Your command implementation
            pass
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            # Extract quiet flag from kwargs if needed
            quiet = kwargs.get("quiet", False) if console_quiet_from_args else False

            # Discover context and create console
            context = discover_context()
            console = ConsoleOutput(quiet=quiet)

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


def with_context_only(func: Callable[P, R]) -> Callable[P, R]:
    """Decorator for commands that only need context discovery.

    Use for passthrough commands (shell, invenio) that handle their own
    console output and error handling.

    Usage:
        @with_context_only
        def my_command(context: ProjectContext, ...):
            pass
    """

    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        context = discover_context()
        return func(*args, context=context, **kwargs)

    return wrapper
```

### Example Refactored Commands

#### Before:
```python
def _start_services_impl(*, quiet: bool = False) -> None:
    """Shared implementation for starting services."""
    context = discover_context()
    console = ConsoleOutput(quiet=quiet)
    console.info("🚀 Starting services...", fg=typer.colors.BRIGHT_BLUE, bold=True)

    services_mgr = ServicesLifecycleManager(
        config=context.config, project_root=context.root_directory, quiet=quiet
    )

    try:
        env_vars = services_mgr.start_services()
        if not env_vars:
            console.info("✓ Services skipped", fg=typer.colors.YELLOW)
        else:
            console.success(
                "✨ ✓ Services started successfully!",
                fg=typer.colors.BRIGHT_GREEN,
                bold=True,
            )
    except OARepoError as e:
        console.error(f"❌ Error starting services: {e}", fg=typer.colors.BRIGHT_RED, bold=True)
        raise typer.Exit(code=1) from e
```

#### After:
```python
@with_context_and_console(
    start_message="Starting services...",
    # No success_message - we show conditional messages inside
    error_prefix="Error starting services",
)
def _start_services_impl(
    context: ProjectContext,
    console: ConsoleOutput,
    *,
    quiet: bool = False,
) -> None:
    """Shared implementation for starting services."""
    services_mgr = ServicesLifecycleManager(
        config=context.config, project_root=context.root_directory, quiet=quiet
    )

    env_vars = services_mgr.start_services()
    if not env_vars:
        console.info("✓ Services skipped", fg=typer.colors.YELLOW)
    else:
        console.success(
            "✨ ✓ Services started successfully!",
            fg=typer.colors.BRIGHT_GREEN,
            bold=True,
        )
        console.info(
            f"  Environment variables written to {context.root_directory / ENV_SERVICES_FILE}",
            fg=typer.colors.GREEN,
        )
```

### Option 2: Context Manager (Alternative)

```python
class CommandContext:
    """Context manager for CLI commands."""

    def __init__(
        self,
        *,
        quiet: bool = False,
        start_message: str | None = None,
        success_message: str | None = None,
        error_prefix: str = "Error",
    ):
        self.quiet = quiet
        self.start_message = start_message
        self.success_message = success_message
        self.error_prefix = error_prefix
        self.context: ProjectContext | None = None
        self.console: ConsoleOutput | None = None

    def __enter__(self) -> tuple[ProjectContext, ConsoleOutput]:
        self.context = discover_context()
        self.console = ConsoleOutput(quiet=self.quiet)

        if self.start_message:
            self.console.info(
                f"🚀 {self.start_message}",
                fg=typer.colors.BRIGHT_BLUE,
                bold=True,
            )

        return self.context, self.console

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            # Success path
            if self.success_message and self.console:
                self.console.success(
                    f"✨ ✓ {self.success_message}",
                    fg=typer.colors.BRIGHT_GREEN,
                    bold=True,
                )
            return True

        if isinstance(exc_val, OARepoError):
            # Handle OARepoError
            if self.console:
                self.console.error(
                    f"❌ {self.error_prefix}: {exc_val}",
                    fg=typer.colors.BRIGHT_RED,
                    bold=True,
                )
            raise typer.Exit(code=1) from exc_val

        # Let other exceptions propagate
        return False


# Usage:
def _start_services_impl(*, quiet: bool = False) -> None:
    """Shared implementation for starting services."""
    with CommandContext(
        quiet=quiet,
        start_message="Starting services...",
        error_prefix="Error starting services",
    ) as (context, console):
        services_mgr = ServicesLifecycleManager(
            config=context.config,
            project_root=context.root_directory,
            quiet=quiet,
        )
        env_vars = services_mgr.start_services()
        # ... rest of logic
```

## Recommendation

**Use Option 1 (Decorator)** for the following reasons:

### Pros:
1. **Less invasive**: Doesn't require changing function signatures drastically
2. **Type-safe**: Modern type checkers understand decorators well
3. **Flexible**: Can opt-in/opt-out per command easily
4. **Familiar**: Decorator pattern is well-understood in Python
5. **Composable**: Can combine with other decorators if needed

### Cons:
1. Adds "magic" parameter injection (context, console)
2. Slightly more complex to understand for new contributors

### Implementation Plan:

1. Create `oarepo_cli/cli/command_wrapper.py` with decorators
2. Start with a few commands as proof of concept:
   - `_start_services_impl`
   - `_stop_services_impl`
   - `library_upgrade`
3. Verify tests pass
4. Gradually refactor other commands
5. Update AGENTS.md with usage guidelines

### Edge Cases to Handle:

1. **Commands that don't need success messages**: Pass `success_message=None`
2. **Commands with conditional success messages**: Show them manually in the function body
3. **Passthrough commands**: Use `@with_context_only` decorator
4. **Commands that delegate to other modules**: Don't use decorator, let the module handle it

## Benefits

- **DRY**: Eliminates ~15-20 lines of boilerplate per command
- **Consistency**: Ensures uniform error handling across all commands
- **Maintainability**: Changes to error handling pattern only need to happen in one place
- **Testability**: Can test the wrapper logic independently
- **Type Safety**: Maintains full type checking

## Estimated Effort

- Create wrapper module: 2 hours
- Refactor 10-15 commands: 3-4 hours
- Testing and verification: 1-2 hours
- **Total: 6-8 hours**

## Files to Change

1. Create: `oarepo_cli/cli/command_wrapper.py`
2. Modify: `oarepo_cli/cli/library.py` (~15 functions)
3. Modify: `oarepo_cli/cli/repository.py` (~5 functions)
4. Update: `AGENTS.md` (add decorator usage guidelines)
5. Tests: Add unit tests for the decorators
