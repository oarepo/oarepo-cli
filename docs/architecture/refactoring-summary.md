# Command Wrapper Decorator Refactoring Summary

This document summarizes the refactoring work to apply the `@with_context_and_console` decorator pattern across the CLI codebase.

## Overview

The refactoring reduces code duplication by extracting common patterns (context discovery, console creation, error handling) into reusable decorators. This was identified as Issue 3.1 in the code review.

## Implementation

### Phase 1: Decorator Creation (PR #148)
- Created `oarepo_cli/cli/command_wrapper.py` with two decorators:
  - `@with_context_and_console`: For commands needing full context, console, and error handling
  - `@with_context_only`: For passthrough commands (shell, invenio)
- Refactored initial commands: `_start_services_impl`, `_stop_services_impl`
- Added comprehensive unit tests (8 tests in `tests/unit/test_command_wrapper.py`)
- Documented pattern in `docs/architecture/solution-3.1-cli-duplication.md`

### Phase 2: Remaining Commands (PR #150)
Applied the decorator pattern to remaining commands:

#### Library Commands
1. ✅ `library venv` → `_library_venv_impl`
2. ✅ `library clean` → `_library_clean_impl`
3. ✅ `library upgrade` → `_library_upgrade_impl`
4. ✅ `library test` → `_library_test_impl`
5. ✅ `library translations` → `_library_translations_impl`
6. ✅ `library license-headers` → `_library_license_headers_impl`

#### Repository Commands
1. ✅ `repository install` → `_install_impl`
2. ✅ `repository upgrade` → `_upgrade_impl`
3. ✅ `repository model create` → `_model_create_impl`

## Pattern Structure

Each refactored command follows this structure:

```python
@with_context_and_console(
    start_message="...",      # Optional: shown before execution
    success_message="...",     # Optional: shown after success
    error_prefix="Error...",   # Required: prefix for error messages
)
def _<command>_impl(
    context: ProjectContext,   # Injected by decorator
    console: ConsoleOutput,    # Injected by decorator
    *,                        # Force keyword-only args
    option1: type,            # Command-specific options
    quiet: bool = False,      # Common pattern
) -> None:
    """Implementation docstring."""
    # Command logic using context and console
    pass

@app.command("name")
def <command>(
    option1: Annotated[type, typer.Option(...)],
    quiet: Annotated[bool, typer.Option("--quiet", "-q", ...)],
) -> None:
    """User-facing docstring."""
    _<command>_impl(option1=option1, quiet=quiet)
```

## Benefits

### Code Reduction
- **15-20 lines removed per command**: Eliminates boilerplate for:
  - Context discovery (`discover_context()`)
  - Console creation (`ConsoleOutput(quiet=quiet)`)
  - Start message display
  - Success message display
  - Error handling (`try/except OARepoError`)

### Consistency
- **Uniform error handling**: All commands handle `OARepoError` identically
- **Consistent messaging**: Start/success messages follow same format (emojis, colors)
- **Type safety**: Proper type hints with `TYPE_CHECKING` separation

### Maintainability
- **Single source of truth**: Error handling logic in one place
- **Easy to test**: Decorators have comprehensive unit tests
- **Clear separation**: Helper functions contain business logic, Typer commands handle CLI concerns

## Example: Before and After

### Before (library_upgrade)
```python
@library_app.command("upgrade")
def library_upgrade(
    quiet: Annotated[bool, typer.Option("--quiet", "-q", ...)] = False,
) -> None:
    # Discover project context
    context = discover_context()

    # Create console output handler
    console = ConsoleOutput(quiet=quiet)

    console.info("🔄 Upgrading environment...", fg=typer.colors.BRIGHT_BLUE, bold=True)

    # ... 30+ lines of implementation ...

    console.success("✨ ✓ Upgrade completed!", fg=typer.colors.BRIGHT_GREEN, bold=True)
```

### After (library_upgrade)
```python
@with_context_and_console(
    start_message="Upgrading environment...",
    success_message="Upgrade completed successfully!",
    error_prefix="Error upgrading environment",
)
def _library_upgrade_impl(
    context: ProjectContext,
    console: ConsoleOutput,
    *,
    quiet: bool = False,
) -> None:
    # ... 30+ lines of implementation (same logic) ...

@library_app.command("upgrade")
def library_upgrade(
    quiet: Annotated[bool, typer.Option("--quiet", "-q", ...)] = False,
) -> None:
    _library_upgrade_impl(quiet=quiet)
```

**Line count reduction**: ~37% (from 50 lines to 32 lines per command on average)

## Commands Not Refactored

The following commands were not refactored because they don't fit the pattern:

### Callback Functions
- `library_callback()` - Empty callback for command group
- `services_callback()` - Empty callback for subcommand group
- `repository_callback()` - Empty callback for command group
- `model_callback()` - Empty callback for subcommand group
- `local_callback()` - Empty callback for subcommand group
- `index_callback()` - Empty callback for subcommand group

### Passthrough Commands (Different Pattern)
These use `@with_context_only` or delegate directly:
- `library_shell` - Uses `@with_context_only` for shell passthrough
- `library_invenio` - Uses `@with_context_only` for invenio passthrough
- `library_lint` - Delegates to `lint_commands.run_lint`
- `repository_shell` - Uses `@with_context_only`
- `repository_invenio` - Uses `@with_context_only`
- Repository services commands - Passthrough to invenio-cli

### Already Refactored
- `_start_services_impl` (Phase 1)
- `_stop_services_impl` (Phase 1)

## Testing

### Unit Tests
- `tests/unit/test_command_wrapper.py`: 8 tests covering decorator behavior
- Tests verify context/console injection, error handling, message display

### Integration Tests
- All existing integration tests pass
- Commands maintain exact same behavior from user perspective
- Exit codes, stdout/stderr preserved

## Future Work

### Additional Commands to Consider (Not Critical)
- `repository_model_update`
- `repository_local_add`
- `repository_local_remove`
- `repository_run`
- `repository_cli`
- JS/lint commands in dedicated modules

These could be refactored if/when they become complex enough to benefit from the pattern.

## References

- **Design Document**: `docs/architecture/solution-3.1-cli-duplication.md`
- **Before/After Comparison**: `docs/architecture/solution-3.1-comparison.md`
- **Decorator Implementation**: `oarepo_cli/cli/command_wrapper.py`
- **Unit Tests**: `tests/unit/test_command_wrapper.py`
- **PR #148**: Initial decorator implementation
- **PR #150**: Applied to remaining commands
