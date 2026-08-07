# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Library commands for OARepo CLI."""

from __future__ import annotations

import json
import os
import traceback
from typing import TYPE_CHECKING, Annotated

if TYPE_CHECKING:
    from oarepo_cli.core.context import ProjectContext
    from oarepo_cli.ui import ConsoleOutput

import typer

from oarepo_cli.cli import js_commands, lint_commands
from oarepo_cli.cli.command_wrapper import with_context_and_console
from oarepo_cli.configuration.constants import ENV_SERVICES_FILE
from oarepo_cli.core.context import discover_context, find_pyproject_toml
from oarepo_cli.core.errors import OARepoError
from oarepo_cli.core.platform import get_platform_detector
from oarepo_cli.services import process
from oarepo_cli.services.license_headers import add_license_headers
from oarepo_cli.services.process import ProcessOutputMode
from oarepo_cli.services.pyproject_reader import PyProjectReader
from oarepo_cli.services.services_lifecycle import ServicesLifecycleManager
from oarepo_cli.services.test_orchestrator import TestOrchestrator
from oarepo_cli.services.translations import run_translations
from oarepo_cli.services.venv import VenvRequirements, VirtualEnvironmentManager
from oarepo_cli.services.version_resolver import VersionResolver
from oarepo_cli.ui import ConsoleOutput

# Create the library subcommand group
library_app = typer.Typer(
    name="library",
    help="Commands for OARepo library development",
    no_args_is_help=True,
)

# Create the services subcommand group
services_app = typer.Typer(
    name="services",
    help="Docker services management",
    no_args_is_help=True,
)

# Create the alembic subcommand group
alembic_app = typer.Typer(
    name="alembic",
    help="Alembic migration management",
    no_args_is_help=True,
)

# Register services as a subcommand of library
library_app.add_typer(services_app)

# Register alembic as a subcommand of library
library_app.add_typer(alembic_app)


@library_app.callback()
def library_callback(
    ctx: typer.Context,
    no_editable: Annotated[
        bool,
        typer.Option(
            "--no-editable",
            help="Build wheel instead of editable install (bash-CLI-compatible global "
            "position; same flag on 'venv'/'install' themselves takes precedence over this)",
        ),
    ] = False,
) -> None:
    """Library command group."""
    # The old bash `library_runner.sh` treated --no-editable as a flag that
    # could appear anywhere in argv (`./run.sh --no-editable venv`), not
    # just after the subcommand name. Typer/Click only accept a group's own
    # options before the subcommand, so this stores it on the context for
    # `venv`/`install` to fall back to when their own --no-editable wasn't
    # given, preserving that old position.
    ctx.obj = {"no_editable": no_editable}


@services_app.callback()
def services_callback() -> None:
    """Services command group."""


@alembic_app.callback()
def alembic_callback() -> None:
    """Alembic command group."""


@with_context_and_console(
    start_message="Initializing Alembic support...",
    error_prefix="Error initializing Alembic",
)
def _alembic_init_impl(
    context: ProjectContext,
    console: ConsoleOutput,
    *,
    quiet: bool = False,  # noqa: ARG001 (used by decorator to control console output)
) -> None:
    """Shared implementation for alembic init.

    Initializes Alembic support including creating migrations and setting up
    the database schema. After completion, instructs the user to review the
    generated migration files.

    Args:
        context: Project context (injected by decorator)
        console: Console output handler (injected by decorator)
        quiet: Suppress command output (passed from CLI, used by decorator)

    """
    from oarepo_cli.services.alembic import AlembicManager

    manager = AlembicManager(context, console)
    manager.init()


@alembic_app.command("init")
def alembic_init(
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress command output")] = False,
) -> None:
    """Initialize Alembic support for the library.

    This command performs the following steps:
    1. Checks for the required 'invenio_db.models' entrypoint in pyproject.toml
    2. Creates an 'alembic' directory in the first code directory if it doesn't exist
    3. Adds the 'invenio_db.alembic' entrypoint to pyproject.toml if missing
    4. Checks if alembic is already initialized (exits early if 2+ migrations exist)
    5. Syncs the project to register entrypoints (uv pip install --no-deps -e .)
    6. Restarts Docker services to ensure clean database state
    7. Verifies alembic state is clean (no uncommitted database changes)
    8. Creates initial branch migration if no Python files exist in alembic/
    9. Runs 'invenio alembic upgrade heads' to apply base migrations
    10. Creates migration for initial database tables

    After completion, you should carefully review the generated migration file
    to ensure it contains only the intended table changes for your models.

    The 'invenio_db.models' entrypoint is required for Alembic support and should
    point to your database models module. If it's missing, the command will exit
    with an error and provide an example configuration.

    Note: This command requires Docker services to be available and will restart
    them to ensure a clean database state.

    Example:
        oarepo-cli library alembic init
        oarepo-cli library alembic init --quiet

    """
    _alembic_init_impl(quiet=quiet)


@with_context_and_console(
    start_message="Starting services...",
    error_prefix="Error starting services",
)
def _start_services_impl(
    context: ProjectContext,
    console: ConsoleOutput,
    *,
    quiet: bool = False,
) -> None:
    """Shared implementation for starting services.

    Args:
        context: Project context (injected by decorator)
        console: Console output handler (injected by decorator)
        quiet: If True, suppress console output and pass --quiet to docker-services-cli

    """
    # Start services using ServicesLifecycleManager
    services_mgr = ServicesLifecycleManager(config=context.config, project_root=context.root_directory, quiet=quiet)

    env_vars = services_mgr.start_services()

    if not env_vars:
        # Services were skipped (SKIP_SERVICES=1)
        console.info("✓ Services skipped", fg=typer.colors.YELLOW)
    else:
        console.success("✨ ✓ Services started successfully!", fg=typer.colors.BRIGHT_GREEN, bold=True)
        console.info(
            f"  Environment variables written to {context.root_directory / ENV_SERVICES_FILE}",
            fg=typer.colors.GREEN,
        )


def _start_services_if_needed_impl(*, quiet: bool = False) -> dict[str, str]:
    """Start services unless already running, and return connection env vars.

    Delegates the "already running?" check to ServicesLifecycleManager
    itself; only shows the usual start messages (via _start_services_impl())
    when services actually need to start. Intended for commands that just
    need connection details available on every invocation (shell, invenio,
    test) rather than restarting services each time.

    Args:
        quiet: If True, pass --quiet to docker-services-cli if it runs

    Returns:
        Dictionary of environment variables for connecting to services

    """
    context = discover_context()
    services_mgr = ServicesLifecycleManager(config=context.config, project_root=context.root_directory, quiet=quiet)

    if services_mgr.are_services_running():
        return services_mgr.load_service_env()

    _start_services_impl(quiet=quiet)
    return services_mgr.load_service_env()


@with_context_and_console(
    start_message="Stopping services...",
    success_message="Services stopped successfully!",
    error_prefix="Error stopping services",
)
def _stop_services_impl(
    context: ProjectContext,
    console: ConsoleOutput,
    *,
    quiet: bool = False,
) -> None:
    """Shared implementation for stopping services.

    Args:
        context: Project context (injected by decorator)
        console: Console output handler (injected by decorator)
        quiet: If True, suppress console output and pass --quiet to docker-services-cli

    """
    if not (context.root_directory / ENV_SERVICES_FILE).exists():
        console.info("✓ No services running", fg=typer.colors.YELLOW)
        return

    # Stop services using ServicesLifecycleManager
    services_mgr = ServicesLifecycleManager(config=context.config, project_root=context.root_directory, quiet=quiet)
    services_mgr.stop_services()


@with_context_and_console(
    success_message="Virtual environment ready!",
    error_prefix="Error setting up virtual environment",
)
def _library_venv_impl(
    context: ProjectContext,
    console: ConsoleOutput,
    *,
    force: bool = False,
    no_editable: bool = False,
    quiet: bool = False,
) -> None:
    """Implement library venv command.

    Args:
        context: Project context (injected by decorator)
        console: Console output handler (injected by decorator)
        force: Recreate venv from scratch
        no_editable: Build wheel instead of editable install
        quiet: Suppress command output

    """
    # Build requirements from context
    requirements = VenvRequirements(
        python_binary=str(context.python_binary),
        oarepo_version=context.oarepo_version,
        extras=[],  # Will be determined from pyproject.toml by VirtualEnvironmentManager
        editable=not no_editable,
    )

    # Create/verify venv
    venv_mgr = VirtualEnvironmentManager(config=context.config, project_root=context.root_directory)
    venv_path = venv_mgr.ensure_venv(requirements, force=force, quiet=quiet)

    console.info(f"  Path: {venv_path}", fg=typer.colors.GREEN)


def _resolve_no_editable(ctx: typer.Context, *, no_editable: bool) -> bool:
    """Merge a command's own --no-editable with the group-level fallback.

    Mirrors the old bash CLI, where `--no-editable` could appear anywhere in
    argv and just set a flag: either position implies non-editable, so this
    is an OR, not an override.

    Args:
        ctx: Command's Typer context (its `.obj` holds the group-level flag,
            set by `library_callback`)
        no_editable: The value of this command's own --no-editable option

    Returns:
        True if --no-editable was given either on the group or the command

    """
    group_no_editable = bool(ctx.obj and ctx.obj.get("no_editable"))
    return no_editable or group_no_editable


@library_app.command("venv")
def library_venv(
    ctx: typer.Context,
    force: Annotated[bool, typer.Option("--force", "-f", help="Recreate venv from scratch")] = False,
    no_editable: Annotated[bool, typer.Option("--no-editable", help="Build wheel instead of editable install")] = False,
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress command output")] = False,
) -> None:
    """Set up virtual environment with OARepo dependencies.

    Creates or verifies a Python virtual environment in the project directory
    and installs all required dependencies including OARepo and the project itself.

    By default, the project is installed in editable mode (-e) so changes to
    the code are immediately reflected. Use --no-editable to build and install
    a wheel instead.

    The virtual environment path defaults to .venv but can be configured via
    the OAREPO_VENV_PATH environment variable or [tool.oarepo-cli.venv.path]
    in pyproject.toml.
    """
    _library_venv_impl(force=force, no_editable=_resolve_no_editable(ctx, no_editable=no_editable), quiet=quiet)


@library_app.command("install")
def library_install(
    ctx: typer.Context,
    force: Annotated[bool, typer.Option("--force", "-f", help="Recreate venv from scratch")] = False,
    no_editable: Annotated[bool, typer.Option("--no-editable", help="Build wheel instead of editable install")] = False,
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress command output")] = False,
) -> None:
    """Alias for 'venv' command - set up virtual environment with OARepo dependencies.

    Creates or verifies a Python virtual environment in the project directory
    and installs all required dependencies including OARepo and the project itself.

    By default, the project is installed in editable mode (-e) so changes to
    the code are immediately reflected. Use --no-editable to build and install
    a wheel instead.

    The virtual environment path defaults to .venv but can be configured via
    the OAREPO_VENV_PATH environment variable or [tool.oarepo-cli.venv.path]
    in pyproject.toml.
    """
    _library_venv_impl(force=force, no_editable=_resolve_no_editable(ctx, no_editable=no_editable), quiet=quiet)


def _stop_services_if_running(
    context: ProjectContext,
    console: ConsoleOutput,
    items_removed: list[str],
    quiet: bool,
) -> None:
    """Stop services if running and record in items_removed.

    Plain helper (not `@with_context_and_console`-wrapped): called from
    `_library_clean_impl`, which already has `context`/`console` from its
    own decorator - wrapping this one too would inject a second, freshly
    `discover_context()`-ed context/console on top of the explicit ones
    passed in below.
    """
    services_mgr = ServicesLifecycleManager(config=context.config, project_root=context.root_directory, quiet=quiet)
    if services_mgr.are_services_running():
        console.info("🛁 Stopping services...", fg=typer.colors.CYAN)
        try:
            services_mgr.stop_services()
            console.info("  ✓ Services stopped", fg=typer.colors.GREEN)
            items_removed.append("services")
        # Best-effort cleanup step: keep going even on a non-OARepoError failure.
        except Exception as e:  # noqa: BLE001
            console.warning(
                f"  ⚠ Warning: Failed to stop services: {e}",
                fg=typer.colors.YELLOW,
            )
    else:
        console.info(
            "  ℹ No services running",  # noqa: RUF001 icon
            fg=typer.colors.CYAN,
        )


def _remove_env_services_file(
    context: ProjectContext,
    console: ConsoleOutput,
    items_removed: list[str],
) -> None:
    """Remove .env-services file if it exists and record in items_removed."""
    env_services_file = context.root_directory / ENV_SERVICES_FILE
    if env_services_file.exists():
        console.info(f"🗑️  Removing {ENV_SERVICES_FILE} file...", fg=typer.colors.CYAN)
        try:
            env_services_file.unlink()
            console.info(f"  ✓ {ENV_SERVICES_FILE} removed", fg=typer.colors.GREEN)
            items_removed.append(ENV_SERVICES_FILE)
        # Best-effort cleanup step: keep going even on a non-OARepoError failure.
        except Exception as e:  # noqa: BLE001
            console.warning(
                f"  ⚠ Warning: Failed to remove {ENV_SERVICES_FILE}: {e}",
                fg=typer.colors.YELLOW,
            )
    else:
        console.info(
            f"  ℹ No {ENV_SERVICES_FILE} file found",  # noqa: RUF001 icon
            fg=typer.colors.CYAN,
        )


def _remove_venv_and_lock(
    context: ProjectContext,
    console: ConsoleOutput,
    items_removed: list[str],
) -> None:
    """Remove venv directory and uv.lock if they exist and record in items_removed."""
    venv_existed = context.venv_path.exists()
    lock_file = context.root_directory / "uv.lock"
    lock_existed = lock_file.exists()

    if not (venv_existed or lock_existed):
        console.info(
            f"  ℹ No virtual environment found at {context.venv_path}",  # noqa: RUF001 icon
            fg=typer.colors.CYAN,
        )
        return

    console.info(f"🗑️  Removing virtual environment at {context.venv_path}...", fg=typer.colors.CYAN)
    try:
        venv_mgr = VirtualEnvironmentManager(config=context.config, project_root=context.root_directory)
        venv_mgr.cleanup()
        if venv_existed:
            console.info("  ✓ Virtual environment removed", fg=typer.colors.GREEN)
            items_removed.append("venv")
        if lock_existed:
            console.info("  ✓ uv.lock file removed", fg=typer.colors.GREEN)
            items_removed.append("uv.lock")
    # Best-effort cleanup step: keep going even on a non-OARepoError failure.
    except Exception as e:  # noqa: BLE001
        console.warning(
            f"  ⚠ Warning: Failed to remove venv/uv.lock: {e}",
            fg=typer.colors.YELLOW,
        )


def _display_cleanup_summary(console: ConsoleOutput, items_removed: list[str]) -> None:
    """Display summary of cleanup operation."""
    if items_removed:
        console.success(
            f"✨ ✓ Cleanup completed! Removed: {', '.join(items_removed)}",
            fg=typer.colors.BRIGHT_GREEN,
            bold=True,
        )
    else:
        console.success(
            "✨ ✓ Environment is already clean!",
            fg=typer.colors.BRIGHT_GREEN,
            bold=True,
        )


@with_context_and_console(
    success_message="Cleanup complete!",
    error_prefix="Error cleaning environment",
    console_quiet_from_args=True,
)
def _library_clean_impl(
    context: ProjectContext,
    console: ConsoleOutput,
    *,
    quiet: bool = False,
) -> None:
    """Implement library clean command.

    Args:
        context: Project context (injected by decorator)
        console: Console output handler (injected by decorator)
        quiet: Suppress command output

    """
    items_removed: list[str] = []

    _stop_services_if_running(context, console, items_removed, quiet)
    _remove_env_services_file(context, console, items_removed)
    _remove_venv_and_lock(context, console, items_removed)
    _display_cleanup_summary(console, items_removed)


@library_app.command("clean")
def library_clean(
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress command output")] = False,
) -> None:
    """Clean up development environment.

    This command:
    1. Stops running services (if any)
    2. Removes the virtual environment directory and uv.lock file
    3. Removes the .env-services file

    Use this when you want to completely remove your development environment,
    for example before deleting the project or when you want a fresh start.

    This command is idempotent - it will not fail if the environment is
    already clean.
    """
    _library_clean_impl(quiet=quiet)


@with_context_and_console(
    success_message="Upgrade complete!",
    error_prefix="Error during upgrade",
)
def _library_upgrade_impl(
    context: ProjectContext,
    console: ConsoleOutput,
    *,
    quiet: bool = False,
) -> None:
    """Implement library upgrade command.

    Args:
        context: Project context (injected by decorator)
        console: Console output handler (injected by decorator)
        quiet: Suppress command output

    """
    # Stop services if running
    services_mgr = ServicesLifecycleManager(config=context.config, project_root=context.root_directory, quiet=quiet)
    if services_mgr.are_services_running():
        console.info("🛁 Stopping services...", fg=typer.colors.CYAN)
        try:
            services_mgr.stop_services()
            console.info("  ✓ Services stopped", fg=typer.colors.GREEN)
        # Best-effort cleanup step: keep going even on a non-OARepoError failure.
        except Exception as e:  # noqa: BLE001
            console.warning(
                f"  ⚠ Warning: Failed to stop services: {e}",
                fg=typer.colors.YELLOW,
            )

    # Clean uv cache
    console.info("🧹 Cleaning uv cache...", fg=typer.colors.CYAN)

    try:
        process.run(
            ["uv", "cache", "clean"],
            check=True,
            output_mode=ProcessOutputMode.INTERACTIVE if not quiet else ProcessOutputMode.CAPTURE,
        )
        console.info("  ✓ Cache cleaned", fg=typer.colors.GREEN)
    # Best-effort step: keep going even on a non-OARepoError failure.
    except Exception as e:  # noqa: BLE001
        console.warning(f"  ⚠ Warning: Failed to clean uv cache: {e}", fg=typer.colors.YELLOW)

    # Remove and recreate venv using VirtualEnvironmentManager
    console.info("🔨 Recreating virtual environment...", fg=typer.colors.CYAN)

    # Build requirements from context
    requirements = VenvRequirements(
        python_binary=str(context.python_binary),
        oarepo_version=context.oarepo_version,
        extras=[],
        editable=True,  # Default to editable mode
    )

    # Create/verify venv with force=True to recreate
    venv_mgr = VirtualEnvironmentManager(config=context.config, project_root=context.root_directory)
    venv_path = venv_mgr.ensure_venv(requirements, force=True, quiet=quiet)

    console.info(f"  Virtual environment ready at {venv_path}", fg=typer.colors.GREEN)


@library_app.command("upgrade")
def library_upgrade(
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress command output")] = False,
) -> None:
    """Clean cache and recreate virtual environment from scratch.

    This command:
    1. Stops running services (if any)
    2. Removes the existing virtual environment (if present)
    3. Cleans the uv cache to ensure fresh package downloads
    4. Recreates the virtual environment with all dependencies

    Use this when you need to completely refresh your development environment,
    for example after updating OARepo or when dependencies become corrupted.
    """
    _library_upgrade_impl(quiet=quiet)


@library_app.command("start")
def library_start(
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress docker-services-cli output")] = False,
) -> None:
    """Start Docker services for development and testing.

    Starts the configured Docker services (database, search, message queue,
    cache, S3) and writes connection details to .env-services file.

    The services are configured via environment variables or [tool.oarepo-cli.services]
    in pyproject.toml.
    """
    _start_services_impl(quiet=quiet)


@services_app.command("start")
def services_start(
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress docker-services-cli output")] = False,
) -> None:
    """Start Docker services for development and testing.

    Starts the configured Docker services (database, search, message queue,
    cache, S3) and writes connection details to .env-services file.

    The services are configured via environment variables or [tool.oarepo-cli.services]
    in pyproject.toml.
    """
    _start_services_impl(quiet=quiet)


@library_app.command("stop")
def library_stop(
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress docker-services-cli output")] = False,
) -> None:
    """Stop Docker services.

    Stops all running Docker services and removes the .env-services file.
    """
    _stop_services_impl(quiet=quiet)


@services_app.command("stop")
def services_stop(
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress docker-services-cli output")] = False,
) -> None:
    """Stop Docker services.

    Stops all running Docker services and removes the .env-services file.
    """
    _stop_services_impl(quiet=quiet)


@with_context_and_console(
    success_message=None,  # Custom success/error handling in impl
    error_prefix="Error running tests",
)
def _library_test_impl(  # noqa: PLR0913 too many arguments ok for commandline client
    context: ProjectContext,
    console: ConsoleOutput,
    *,
    pytest_args: list[str],
    skip_services: bool = False,
    with_coverage: bool = False,
    quiet: bool = False,
) -> None:
    """Implement library test command.

    Args:
        context: Project context (injected by decorator)
        console: Console output handler (injected by decorator)
        pytest_args: Additional arguments to pass to pytest
        skip_services: Skip starting/stopping Docker services
        with_coverage: Enable coverage reporting
        quiet: Suppress service start/stop messages

    """
    # Create orchestrator and run tests
    orchestrator = TestOrchestrator(context=context, quiet=quiet)

    result = orchestrator.run_tests(
        pytest_args=pytest_args,
        coverage=with_coverage,
        skip_services=skip_services,
    )

    # Display result
    if result.success:
        console.success(
            "✨ ✓ All tests passed!",
            fg=typer.colors.BRIGHT_GREEN,
            bold=True,
        )
    else:
        console.error(
            "❌ Tests failed!",
            fg=typer.colors.BRIGHT_RED,
            bold=True,
        )

    # Exit with pytest's exit code
    raise typer.Exit(code=result.return_code)


@library_app.command(
    "test",
    context_settings={
        "allow_extra_args": True,
        "ignore_unknown_options": True,
    },
)
def library_test(
    ctx: typer.Context,
    skip_services: Annotated[
        bool, typer.Option("--skip-services", help="Skip starting/stopping Docker services")
    ] = False,
    with_coverage: Annotated[bool, typer.Option("--with-coverage", help="Enable coverage reporting")] = False,
    quiet: Annotated[
        bool,
        typer.Option(
            "--quiet",
            "-q",
            help="Suppress service start/stop messages and docker-services-cli output",
        ),
    ] = False,
) -> None:
    """Run pytest tests with optional coverage and services.

    Runs the project's test suite using pytest. By default, Docker services
    (database, search, etc.) are started before running tests and stopped
    afterward.

    Use --skip-services to run tests without starting services (faster for
    unit tests that don't need external dependencies).

    Use --with-coverage to generate coverage reports (HTML and terminal).

    Use --quiet to suppress service start/stop messages and docker-services-cli
    output (pytest output is still shown).

    Any additional arguments are passed directly to pytest.

    Examples:
        oarepo-cli library test
        oarepo-cli library test --with-coverage
        oarepo-cli library test --skip-services
        oarepo-cli library test --quiet
        oarepo-cli library test -v tests/unit/
        oarepo-cli library test --with-coverage -x -k test_specific

    """
    # Get extra args from context
    pytest_args = ctx.args or []

    _library_test_impl(
        pytest_args=pytest_args,
        skip_services=skip_services,
        with_coverage=with_coverage,
        quiet=quiet,
    )


@library_app.command("shell")
def library_shell(
    skip_services: Annotated[bool, typer.Option("--skip-services", help="Skip starting Docker services")] = False,
) -> None:
    """Start an interactive bash shell in the project's virtual environment.

    Opens a bash shell with the virtual environment activated and all
    environment variables from .env-services loaded. By default, Docker
    services are started before opening the shell.

    Use --skip-services to skip starting services (useful if services are
    already running or not needed).

    Examples:
        oarepo-cli library shell
        oarepo-cli library shell --skip-services

    """
    # Discover project context
    context = discover_context()

    # Console always shows output for passthrough commands
    console = ConsoleOutput(quiet=False)

    # Ensure venv exists
    console.info("🔧 Checking virtual environment...", fg=typer.colors.BRIGHT_BLUE, bold=True)
    venv_mgr = VirtualEnvironmentManager(config=context.config, project_root=context.root_directory)
    requirements = VenvRequirements(
        python_binary=str(context.python_binary),
        oarepo_version=context.oarepo_version,
        editable=context.config.build.editable,
    )

    try:
        venv_path = venv_mgr.ensure_venv_exists(requirements, quiet=True)
    except OARepoError as e:
        console.error(
            f"❌ Error ensuring virtual environment: {e}",
            fg=typer.colors.BRIGHT_RED,
            bold=True,
        )
        traceback.print_exc()
        raise typer.Exit(code=1) from e

    # Start services unless already running or explicitly skipped, and load
    # the environment variables needed to connect to them
    if skip_services:
        services_mgr = ServicesLifecycleManager(config=context.config, project_root=context.root_directory)
        service_env = services_mgr.load_service_env()
    else:
        service_env = _start_services_if_needed_impl(quiet=False)

    # Get platform-specific paths
    platform = get_platform_detector()
    bin_dir = platform.get_venv_bin_dir()

    # Build environment for the shell: build_subprocess_env() strips oarepo-cli's own
    # venv and injects OAREPO_ENV_DEFAULTS, same as any process.run() call gets --
    # there's no other subprocess env-merging safety net once this replaces the
    # current process.
    shell_env = process.build_subprocess_env()

    # Add service environment variables
    shell_env.update(service_env)

    # Set VIRTUAL_ENV and update PATH
    shell_env["VIRTUAL_ENV"] = str(venv_path)
    venv_bin_path = str(venv_path / bin_dir)
    shell_env["PATH"] = f"{venv_bin_path}{os.pathsep}{shell_env.get('PATH', '')}"

    # Advertise the venv to prompt tools that read it directly (uv's own
    # activate script sets this too). Use the project name rather than
    # ".venv" since it's the more useful thing to see in the prompt.
    shell_env["VIRTUAL_ENV_PROMPT"] = context.root_directory.name

    # Fallback PS1 for plain bash with no prompt tool of its own. Only takes
    # effect if nothing later in shell startup (rc files, prompt tools that
    # respect this convention) resets it — VIRTUAL_ENV_DISABLE_PROMPT lets
    # users who prefer their own prompt opt out entirely.
    if "VIRTUAL_ENV_DISABLE_PROMPT" not in shell_env:
        shell_env["PS1"] = f"({context.root_directory.name}) \\u@\\h:\\w\\$ "

    # Drop PROMPT_COMMAND: prompt tools (e.g. starship) set it to recompute
    # PS1 before every prompt render, so an inherited value would silently
    # override PS1 above the moment the first prompt is drawn.
    shell_env.pop("PROMPT_COMMAND", None)

    # Suppress macOS's "default interactive shell is now zsh" nag: it's printed
    # on every interactive bash startup and reads like something went wrong.
    shell_env["BASH_SILENCE_DEPRECATION_WARNING"] = "1"

    console.info(
        "🐚 Starting bash shell in virtual environment...",
        fg=typer.colors.BRIGHT_GREEN,
        bold=True,
    )
    console.info("   Type 'exit' or press Ctrl+D to exit the shell.", fg=typer.colors.GREEN)

    # Execute bash with the prepared environment
    # Use os.execve to replace current process (like the old shell script did)
    try:
        bash_path = platform.get_default_shell()
        os.execve(bash_path, ["bash"], shell_env)  # noqa S606 no shell is ok here, replacing the process
    except OSError as e:
        console.error(
            f"❌ Failed to start shell: {e}",
            fg=typer.colors.BRIGHT_RED,
            bold=True,
        )
        raise typer.Exit(code=1) from e


@library_app.command(
    "invenio",
    context_settings={
        "allow_extra_args": True,
        "allow_interspersed_args": True,
        "ignore_unknown_options": True,
        # Don't let Click intercept --help: this is a passthrough to the
        # real invenio CLI, so --help must reach invenio_args and produce
        # invenio's own --help output, not oarepo-cli's.
        "help_option_names": [],
    },
)
def library_invenio(
    ctx: typer.Context,
    skip_services: Annotated[bool, typer.Option("--skip-services", help="Skip starting Docker services")] = False,
) -> None:
    """Run invenio commands in the project's virtual environment.

    Executes invenio CLI commands with the virtual environment activated and
    all environment variables from .env-services loaded. By default, Docker
    services are started before running the command.

    Use --skip-services to skip starting services (useful if services are
    already running or not needed).

    Any additional arguments are passed directly to invenio.

    Examples:
        oarepo-cli library invenio db upgrade
        oarepo-cli library invenio run
        oarepo-cli library invenio --skip-services shell
        oarepo-cli library invenio users create admin@example.com --password admin

    """
    # Get extra args from context (these are the invenio command args)
    invenio_args = ctx.args or []

    if not invenio_args:
        typer.echo("Error: No invenio command provided.")
        typer.echo("Example: oarepo-cli library invenio db upgrade")
        raise typer.Exit(code=1)

    # Discover project context
    context = discover_context()

    # Console always shows output for passthrough commands
    console = ConsoleOutput(quiet=False)

    # Ensure venv exists
    console.info("🔧 Checking virtual environment...", fg=typer.colors.BRIGHT_BLUE, bold=True)
    venv_mgr = VirtualEnvironmentManager(config=context.config, project_root=context.root_directory)
    requirements = VenvRequirements(
        python_binary=str(context.python_binary),
        oarepo_version=context.oarepo_version,
        editable=context.config.build.editable,
    )

    try:
        venv_path = venv_mgr.ensure_venv_exists(requirements, quiet=True)
    except OARepoError as e:
        console.error(
            f"❌ Error ensuring virtual environment: {e}",
            fg=typer.colors.BRIGHT_RED,
            bold=True,
        )
        raise typer.Exit(code=1) from e

    # Start services unless already running or explicitly skipped, and load
    # the environment variables needed to connect to them
    if skip_services:
        services_mgr = ServicesLifecycleManager(config=context.config, project_root=context.root_directory)
        service_env = services_mgr.load_service_env()
    else:
        service_env = _start_services_if_needed_impl(quiet=False)

    # Get platform-specific paths
    platform = get_platform_detector()
    bin_dir = platform.get_venv_bin_dir()
    invenio_path = venv_path / bin_dir / "invenio"

    # Check if invenio executable exists
    if not invenio_path.exists():
        console.error(
            "❌ invenio command not found in virtual environment.",
            fg=typer.colors.BRIGHT_RED,
            bold=True,
        )
        console.info(
            "   Make sure your project has invenio installed.",
            fg=typer.colors.YELLOW,
        )
        raise typer.Exit(code=1)

    # Build environment for the command: build_subprocess_env() strips oarepo-cli's
    # own venv and injects OAREPO_ENV_DEFAULTS, same as any process.run() call gets.
    cmd_env = process.build_subprocess_env()

    # Add service environment variables
    cmd_env.update(service_env)

    # Set VIRTUAL_ENV and update PATH
    cmd_env["VIRTUAL_ENV"] = str(venv_path)
    venv_bin_path = str(venv_path / bin_dir)
    cmd_env["PATH"] = f"{venv_bin_path}{os.pathsep}{cmd_env.get('PATH', '')}"

    console.info(
        f"🚀 Running: invenio {' '.join(invenio_args)}",
        fg=typer.colors.BRIGHT_GREEN,
        bold=True,
    )

    # Execute invenio with the prepared environment
    # Use os.execve to replace current process (preserves exit codes)
    try:
        os.execve(str(invenio_path), ["invenio", *invenio_args], cmd_env)  # noqa S606 no shell is ok here, replacing the process
    except OSError as e:
        console.error(
            f"❌ Failed to run invenio: {e}",
            fg=typer.colors.BRIGHT_RED,
            bold=True,
        )
        raise typer.Exit(code=1) from e


@library_app.command("lint")
def library_lint(
    fix: Annotated[
        bool,
        typer.Option("--fix/--no-fix", help="Auto-fix what ruff/ty can fix (default) vs. report only"),
    ] = True,
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress command output")] = False,
) -> None:
    """Run linters and type checkers on the codebase.

    Runs, in order, stopping at the first failure: ruff check, ruff format,
    a license header check, a `from __future__ import annotations` check,
    and ty check. Generates .ruff.toml and ty.toml config files in the
    project root.

    By default (--fix), auto-fixes what ruff and ty can fix (`ruff check
    --fix`, `ruff format`, `ty check --fix`) instead of only reporting.
    The license header and future annotations checks never modify files
    regardless of --fix - use `library license-headers` to add those.
    Use --no-fix (or `library check`, its dedicated read-only equivalent)
    to never modify any file.

    Exits with the exit code of the first failing check.
    """
    context = discover_context()
    lint_commands.run_lint(context, fix=fix, quiet=quiet)


@library_app.command(
    "format",
    context_settings={
        "allow_extra_args": True,
        "allow_interspersed_args": True,
        "ignore_unknown_options": True,
    },
)
def library_format(
    ctx: typer.Context,
    fix: Annotated[
        bool,
        typer.Option(
            "--fix/--no-fix",
            help="Rewrite files (default) vs. preview-only (`ruff format --check`)",
        ),
    ] = True,
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress command output")] = False,
) -> None:
    """Format the codebase using ruff.

    By default (--fix), runs `ruff format` followed by `ruff check --fix`,
    rewriting files. Use --no-fix for a preview-only run (`ruff format
    --check`, nothing written) - or `library check`, its dedicated
    read-only equivalent.

    Any additional arguments are passed directly to the ruff invocation(s).

    Examples:
        oarepo-cli library format
        oarepo-cli library format src/mymodule.py
        oarepo-cli library format --diff
        oarepo-cli library format --no-fix

    """
    # Get extra args from context (passed through to ruff)
    extra_args = ctx.args or []

    context = discover_context()
    lint_commands.run_format(context, fix=fix, extra_args=extra_args, quiet=quiet)


@library_app.command("check")
def library_check(
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress command output")] = False,
) -> None:
    """Check the codebase without modifying any file.

    The read-only equivalent of `library lint`/`library format`: runs ruff
    check, ruff format --check, a license header check, a `from __future__
    import annotations` check, and ty check - none of them applying fixes.
    Equivalent to `library lint --no-fix`, provided as its own command as
    the safe-for-CI entry point. Still generates .ruff.toml and ty.toml
    config files in the project root (that's config generation, not
    modifying target project source).

    Exits with the exit code of the first failing check.
    """
    context = discover_context()
    lint_commands.run_check(context, quiet=quiet)


@with_context_and_console(
    success_message=None,  # Custom success/error handling in impl
    error_prefix="Error running translations",
)
def _library_translations_impl(
    context: ProjectContext,
    console: ConsoleOutput,
    *,
    extra_args: list[str],
    quiet: bool = False,
) -> None:
    """Implement library translations command.

    Args:
        context: Project context (injected by decorator)
        console: Console output handler (injected by decorator)
        extra_args: Additional arguments to pass to make-translations
        quiet: Suppress command output

    """
    result = run_translations(context, extra_args=extra_args, quiet=quiet)

    if result.success:
        console.success("✨ ✓ Translations complete!", fg=typer.colors.BRIGHT_GREEN, bold=True)
    else:
        console.error("❌ Translations failed!", fg=typer.colors.BRIGHT_RED, bold=True)

    raise typer.Exit(code=result.return_code)


@library_app.command(
    "translations",
    context_settings={
        "allow_extra_args": True,
        "ignore_unknown_options": True,
    },
)
def library_translations(
    ctx: typer.Context,
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress command output")] = False,
) -> None:
    """Extract and compile translations using oarepo-tools make-translations.

    Calls make-translations from oarepo-tools with any additional arguments.
    This command is typically used in library packages that include
    translatable strings.

    Any additional arguments are passed directly to make-translations.

    Examples:
        oarepo-cli library translations
        oarepo-cli library translations --help

    """
    extra_args = ctx.args or []

    _library_translations_impl(extra_args=extra_args, quiet=quiet)


@with_context_and_console(
    success_message=None,  # Custom success/error handling in impl
    error_prefix="Error adding license headers",
)
def _library_license_headers_impl(
    context: ProjectContext,
    console: ConsoleOutput,
    *,
    organization: str | None = None,
    quiet: bool = False,
) -> None:
    """Implement library license-headers command.

    Args:
        context: Project context (injected by decorator)
        console: Console output handler (injected by decorator)
        organization: Organization name for copyright
        quiet: Suppress command output

    """
    result = add_license_headers(context, organization=organization, quiet=quiet)

    if result.success:
        console.success("✨ ✓ License headers complete!", fg=typer.colors.BRIGHT_GREEN, bold=True)
    else:
        console.error("❌ License headers failed!", fg=typer.colors.BRIGHT_RED, bold=True)

    raise typer.Exit(code=result.return_code)


@library_app.command("license-headers")
def library_license_headers(
    organization: Annotated[
        str | None,
        typer.Option("--organization", "-o", help="Organization name for copyright"),
    ] = None,
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress command output")] = False,
) -> None:
    """Add MIT license headers to Python files.

    Scans Python files in the project and adds MIT license headers to any
    files that don't already have "Copyright (c)" (case-insensitive) in
    them. Uses the homepage URL from pyproject.toml [project.urls].

    By default, uses "CESNET z.s.p.o." as the organization name, but this
    can be overridden with --organization.

    Examples:
        oarepo-cli library license-headers
        oarepo-cli library license-headers --organization "My Organization"

    """
    _library_license_headers_impl(organization=organization, quiet=quiet)


@library_app.command("jslint")
def library_jslint(
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress command output")] = False,
) -> None:
    """Run ESLint and Prettier on JavaScript files.

    Installs necessary dependencies if needed (@inveniosoftware/eslint-config-invenio),
    generates .eslintrc.yaml configuration, runs eslint with --fix to
    auto-fix issues, and runs prettier to format code.

    In CI environments (CI=true), prettier runs in check mode (--check)
    instead of write mode (--write).

    Skips entirely if no package.json is found.

    Examples:
        oarepo-cli library jslint

    """
    context = discover_context()
    js_commands.run_jslint_command(context, quiet=quiet)


@library_app.command(
    "jstest",
    context_settings={
        "allow_extra_args": True,
        "allow_interspersed_args": True,
        "ignore_unknown_options": True,
    },
)
def library_jstest(
    ctx: typer.Context,
    setup: Annotated[bool, typer.Option("--setup", help="Set up Jest configuration instead of running tests")] = False,
    skip_services: Annotated[bool, typer.Option("--skip-services", help="Skip starting Docker services")] = False,
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress command output")] = False,
) -> None:
    """Run JavaScript tests (Jest) via invenio webpack.

    Runs Jest tests through the invenio webpack test command. Use --setup
    to set up the Jest configuration (currently delegates to bash script).

    By default, starts Docker services if needed. Use --skip-services to
    skip service startup.

    Any additional arguments are passed directly to the test command.

    Examples:
        oarepo-cli library jstest
        oarepo-cli library jstest --skip-services
        oarepo-cli library jstest --setup

    """
    extra_args = ctx.args or []

    context = discover_context()

    # Start services unless already running or explicitly skipped, and get
    # the environment variables needed to connect to them
    if skip_services:
        services_mgr = ServicesLifecycleManager(config=context.config, project_root=context.root_directory)
        service_env = services_mgr.load_service_env()
    else:
        service_env = _start_services_if_needed_impl(quiet=quiet)

    js_commands.run_jstest_command(context, setup=setup, service_env=service_env, extra_args=extra_args, quiet=quiet)


@library_app.command("oarepo-versions")
def library_oarepo_versions(
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress command output")] = False,
) -> None:
    """List supported OARepo and Python versions (JSON output).

    Parses pyproject.toml for OARepo version constraints in [project].dependencies
    and [project].optional-dependencies, and outputs a JSON object with:
    - oarepo_versions: List of detected OARepo major versions (as strings), highest-first
    - python_versions: List of compatible Python versions (as strings)
    - node_versions: List of Node.js major versions available on the system (as strings)

    Example pyproject.toml:
        [project]
        dependencies = ["oarepo>=14.0.0,<15.0.0"]
        requires-python = ">=3.14"

        [project.optional-dependencies]
        tests = ["oarepo>=13.0.0,<14.0.0"]

    Example output (multiple versions detected):
        {
            "oarepo_versions": ["14", "13"],
            "python_versions": ["3.14"],
            "node_versions": ["24"]
        }

    Examples:
        oarepo-cli library oarepo-versions
        oarepo-cli library oarepo-versions | jq .python_versions

    """
    # Deliberately not discover_context(): this command only ever needs
    # pyproject.toml to exist (it reports what a project *declares*, before
    # any venv is created or an OARepo version is even resolvable), whereas
    # discover_context() additionally requires a working Python binary and a
    # resolvable OARepo version -- either of which may not exist yet.
    pyproject_path = find_pyproject_toml()

    if pyproject_path is None:
        console = ConsoleOutput(quiet=quiet)
        console.error(
            "❌ pyproject.toml not found in current directory or any parent",
            fg=typer.colors.BRIGHT_RED,
            bold=True,
        )
        raise typer.Exit(code=1)

    pyproject_reader = PyProjectReader()
    resolver = VersionResolver(pyproject_reader=pyproject_reader)

    try:
        info = resolver.resolve_from_pyproject(pyproject_path)
    except OARepoError as e:
        console = ConsoleOutput(quiet=quiet)
        console.error(f"❌ Error resolving versions: {e}", fg=typer.colors.BRIGHT_RED, bold=True)
        raise typer.Exit(code=1) from e

    # Construct JSON output
    # Note: Convert oarepo_versions from int to string to match bash output format
    output = {
        "oarepo_versions": [str(v) for v in info.oarepo_versions],
        "python_versions": info.python_versions,
        "node_versions": info.node_versions,
    }

    # Print JSON to stdout (so it can be piped or parsed)
    typer.echo(json.dumps(output))
