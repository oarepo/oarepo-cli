# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Library commands for OARepo CLI."""

from __future__ import annotations

import json
import os
import traceback
from typing import Annotated

import typer

from oarepo_cli.cli import js_commands, lint_commands
from oarepo_cli.configuration.constants import ENV_SERVICES_FILE
from oarepo_cli.core.context import discover_context, find_pyproject_toml
from oarepo_cli.core.errors import OARepoError
from oarepo_cli.core.platform import get_platform_detector
from oarepo_cli.services import process
from oarepo_cli.services.license_headers import add_license_headers
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

# Register services as a subcommand of library
library_app.add_typer(services_app)


@library_app.callback()
def library_callback() -> None:
    """Library command group."""


@services_app.callback()
def services_callback() -> None:
    """Services command group."""


def _start_services_impl(*, quiet: bool = False) -> None:
    """Shared implementation for starting services.

    Args:
        quiet: If True, suppress console output and pass --quiet to docker-services-cli
    """
    # Discover project context
    context = discover_context()

    # Create console with the provided quiet flag
    console = ConsoleOutput(quiet=quiet)

    console.info("🚀 Starting services...", fg=typer.colors.BRIGHT_BLUE, bold=True)

    # Start services using ServicesLifecycleManager
    services_mgr = ServicesLifecycleManager(
        config=context.config, project_root=context.root_directory, quiet=quiet
    )

    try:
        env_vars = services_mgr.start_services()

        if not env_vars:
            # Services were skipped (SKIP_SERVICES=1)
            console.info("✓ Services skipped", fg=typer.colors.YELLOW)
        else:
            console.success(
                "✨ ✓ Services started successfully!", fg=typer.colors.BRIGHT_GREEN, bold=True
            )
            console.info(
                f"  Environment variables written to {context.root_directory / ENV_SERVICES_FILE}",
                fg=typer.colors.GREEN,
            )
    except OARepoError as e:
        console.error(f"❌ Error starting services: {e}", fg=typer.colors.BRIGHT_RED, bold=True)
        raise typer.Exit(code=1) from e


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
    services_mgr = ServicesLifecycleManager(
        config=context.config, project_root=context.root_directory, quiet=quiet
    )

    if services_mgr.are_services_running():
        return services_mgr.load_service_env()

    _start_services_impl(quiet=quiet)
    return services_mgr.load_service_env()


def _stop_services_impl(*, quiet: bool = False) -> None:
    """Shared implementation for stopping services.

    Args:
        quiet: If True, suppress console output and pass --quiet to docker-services-cli
    """
    # Discover project context
    context = discover_context()

    # Create console with the provided quiet flag
    console = ConsoleOutput(quiet=quiet)

    if not (context.root_directory / ENV_SERVICES_FILE).exists():
        console.info("✓ No services running", fg=typer.colors.YELLOW)
        return

    console.info("🛑 Stopping services...", fg=typer.colors.BRIGHT_BLUE, bold=True)

    # Stop services using ServicesLifecycleManager
    services_mgr = ServicesLifecycleManager(
        config=context.config, project_root=context.root_directory, quiet=quiet
    )

    try:
        services_mgr.stop_services()
        console.success(
            "✨ ✓ Services stopped successfully!", fg=typer.colors.BRIGHT_GREEN, bold=True
        )
    except OARepoError as e:
        console.error(f"❌ Error stopping services: {e}", fg=typer.colors.BRIGHT_RED, bold=True)
        raise typer.Exit(code=1) from e


@library_app.command("venv")
def library_venv(
    force: Annotated[
        bool, typer.Option("--force", "-f", help="Recreate venv from scratch")
    ] = False,
    no_editable: Annotated[
        bool, typer.Option("--no-editable", help="Build wheel instead of editable install")
    ] = False,
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
    # Discover project context
    context = discover_context()

    # Create console output handler
    console = ConsoleOutput(quiet=quiet)

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

    console.success("✨ ✓ Virtual environment ready!", fg=typer.colors.BRIGHT_GREEN, bold=True)
    console.info(f"  Path: {venv_path}", fg=typer.colors.GREEN)


@library_app.command("install")
def library_install(
    force: Annotated[
        bool, typer.Option("--force", "-f", help="Recreate venv from scratch")
    ] = False,
    no_editable: Annotated[
        bool, typer.Option("--no-editable", help="Build wheel instead of editable install")
    ] = False,
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
    # Just call library_venv with the same parameters
    library_venv(force=force, no_editable=no_editable, quiet=quiet)


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
    # Discover project context
    context = discover_context()

    # Create console output handler
    console = ConsoleOutput(quiet=quiet)

    console.info("🧹 Cleaning environment...", fg=typer.colors.BRIGHT_BLUE, bold=True)

    items_removed = []

    # Stop services if running
    services_mgr = ServicesLifecycleManager(
        config=context.config, project_root=context.root_directory, quiet=quiet
    )
    if services_mgr.are_services_running():
        console.info("🛑 Stopping services...", fg=typer.colors.CYAN)
        try:
            services_mgr.stop_services()
            console.info("  ✓ Services stopped", fg=typer.colors.GREEN)
            items_removed.append("services")
        # Best-effort cleanup step: keep going even on a non-OARepoError failure.
        except Exception as e:
            console.warning(
                f"  ⚠ Warning: Failed to stop services: {e}",
                fg=typer.colors.YELLOW,
            )
    else:
        console.info("  ℹ No services running", fg=typer.colors.CYAN)

    # Remove .env-services file
    env_services_file = context.root_directory / ENV_SERVICES_FILE
    if env_services_file.exists():
        console.info(f"🗑️  Removing {ENV_SERVICES_FILE} file...", fg=typer.colors.CYAN)
        try:
            env_services_file.unlink()
            console.info(f"  ✓ {ENV_SERVICES_FILE} removed", fg=typer.colors.GREEN)
            items_removed.append(ENV_SERVICES_FILE)
        # Best-effort cleanup step: keep going even on a non-OARepoError failure.
        except Exception as e:
            console.warning(
                f"  ⚠ Warning: Failed to remove {ENV_SERVICES_FILE}: {e}",
                fg=typer.colors.YELLOW,
            )
    else:
        console.info(f"  ℹ No {ENV_SERVICES_FILE} file found", fg=typer.colors.CYAN)

    # Remove venv directory and uv.lock using VirtualEnvironmentManager
    venv_existed = context.venv_path.exists()
    lock_file = context.root_directory / "uv.lock"
    lock_existed = lock_file.exists()

    if venv_existed or lock_existed:
        console.info(
            f"🗑️  Removing virtual environment at {context.venv_path}...", fg=typer.colors.CYAN
        )
        try:
            venv_mgr = VirtualEnvironmentManager(
                config=context.config, project_root=context.root_directory
            )
            venv_mgr.cleanup()
            if venv_existed:
                console.info("  ✓ Virtual environment removed", fg=typer.colors.GREEN)
                items_removed.append("venv")
            if lock_existed:
                console.info("  ✓ uv.lock file removed", fg=typer.colors.GREEN)
                items_removed.append("uv.lock")
        # Best-effort cleanup step: keep going even on a non-OARepoError failure.
        except Exception as e:
            console.warning(
                f"  ⚠ Warning: Failed to remove venv/uv.lock: {e}",
                fg=typer.colors.YELLOW,
            )
    else:
        console.info(
            f"  ℹ No virtual environment found at {context.venv_path}", fg=typer.colors.CYAN
        )

    # Display summary
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
    # Discover project context
    context = discover_context()

    # Create console output handler
    console = ConsoleOutput(quiet=quiet)

    console.info("🔄 Upgrading environment...", fg=typer.colors.BRIGHT_BLUE, bold=True)

    # Stop services if running
    services_mgr = ServicesLifecycleManager(
        config=context.config, project_root=context.root_directory, quiet=quiet
    )
    if services_mgr.are_services_running():
        console.info("🛑 Stopping services...", fg=typer.colors.CYAN)
        try:
            services_mgr.stop_services()
            console.info("  ✓ Services stopped", fg=typer.colors.GREEN)
        # Best-effort cleanup step: keep going even on a non-OARepoError failure.
        except Exception as e:
            console.warning(
                f"  ⚠ Warning: Failed to stop services: {e}",
                fg=typer.colors.YELLOW,
            )

    # Clean uv cache
    console.info("🧹 Cleaning uv cache...", fg=typer.colors.CYAN)

    try:
        process.run(["uv", "cache", "clean"], check=True, interactive=not quiet)
        console.info("  ✓ Cache cleaned", fg=typer.colors.GREEN)
    # Best-effort step: keep going even on a non-OARepoError failure.
    except Exception as e:
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

    console.success("✨ ✓ Upgrade completed successfully!", fg=typer.colors.BRIGHT_GREEN, bold=True)
    console.info(f"  Virtual environment ready at {venv_path}", fg=typer.colors.GREEN)


@library_app.command("start")
def library_start(
    quiet: Annotated[
        bool, typer.Option("--quiet", "-q", help="Suppress docker-services-cli output")
    ] = False,
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
    quiet: Annotated[
        bool, typer.Option("--quiet", "-q", help="Suppress docker-services-cli output")
    ] = False,
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
    quiet: Annotated[
        bool, typer.Option("--quiet", "-q", help="Suppress docker-services-cli output")
    ] = False,
) -> None:
    """Stop Docker services.

    Stops all running Docker services and removes the .env-services file.
    """
    _stop_services_impl(quiet=quiet)


@services_app.command("stop")
def services_stop(
    quiet: Annotated[
        bool, typer.Option("--quiet", "-q", help="Suppress docker-services-cli output")
    ] = False,
) -> None:
    """Stop Docker services.

    Stops all running Docker services and removes the .env-services file.
    """
    _stop_services_impl(quiet=quiet)


@library_app.command(
    "test",
    context_settings={
        "allow_extra_args": True,
        "allow_interspersed_args": True,
        "ignore_unknown_options": True,
    },
)
def library_test(
    ctx: typer.Context,
    skip_services: Annotated[
        bool, typer.Option("--skip-services", help="Skip starting/stopping Docker services")
    ] = False,
    with_coverage: Annotated[
        bool, typer.Option("--with-coverage", help="Enable coverage reporting")
    ] = False,
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
    pytest_args = ctx.args if ctx.args else []

    # Discover project context
    context = discover_context()

    # Create console output handler
    console = ConsoleOutput(quiet=quiet)

    console.info("🧪 Running tests...", fg=typer.colors.BRIGHT_BLUE, bold=True)

    # Create orchestrator and run tests
    orchestrator = TestOrchestrator(context=context, quiet=quiet)

    try:
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

    except OARepoError as e:
        # Catch any orchestration errors (not pytest failures, which are reported
        # above via result.return_code) -- typer.Exit itself is never caught here
        # since it isn't an OARepoError, so it always propagates untouched.
        console.error(
            f"❌ Error running tests: {e}",
            fg=typer.colors.BRIGHT_RED,
            bold=True,
        )
        raise typer.Exit(code=1) from e


@library_app.command("shell")
def library_shell(
    skip_services: Annotated[
        bool, typer.Option("--skip-services", help="Skip starting Docker services")
    ] = False,
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
        services_mgr = ServicesLifecycleManager(
            config=context.config, project_root=context.root_directory
        )
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
        os.execve(bash_path, ["bash"], shell_env)
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
    skip_services: Annotated[
        bool, typer.Option("--skip-services", help="Skip starting Docker services")
    ] = False,
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
    invenio_args = ctx.args if ctx.args else []

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
        services_mgr = ServicesLifecycleManager(
            config=context.config, project_root=context.root_directory
        )
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
        os.execve(str(invenio_path), ["invenio", *invenio_args], cmd_env)
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
        typer.Option(
            "--fix/--no-fix", help="Auto-fix what ruff/ty can fix (default) vs. report only"
        ),
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
    extra_args = ctx.args if ctx.args else []

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


@library_app.command(
    "translations",
    context_settings={
        "allow_extra_args": True,
        "allow_interspersed_args": True,
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
    extra_args = ctx.args if ctx.args else []

    context = discover_context()
    console = ConsoleOutput(quiet=quiet)

    console.info("🌍 Running translations...", fg=typer.colors.BRIGHT_BLUE, bold=True)

    try:
        result = run_translations(context, extra_args=extra_args, quiet=quiet)
    except OARepoError as e:
        console.error(f"❌ Error running translations: {e}", fg=typer.colors.BRIGHT_RED, bold=True)
        raise typer.Exit(code=1) from e

    if result.success:
        console.success("✨ ✓ Translations complete!", fg=typer.colors.BRIGHT_GREEN, bold=True)
    else:
        console.error("❌ Translations failed!", fg=typer.colors.BRIGHT_RED, bold=True)

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
    context = discover_context()
    console = ConsoleOutput(quiet=quiet)

    console.info("📝 Adding license headers...", fg=typer.colors.BRIGHT_BLUE, bold=True)

    try:
        result = add_license_headers(context, organization=organization, quiet=quiet)
    except OARepoError as e:
        console.error(
            f"❌ Error adding license headers: {e}", fg=typer.colors.BRIGHT_RED, bold=True
        )
        raise typer.Exit(code=1) from e

    if result.success:
        console.success("✨ ✓ License headers complete!", fg=typer.colors.BRIGHT_GREEN, bold=True)
    else:
        console.error("❌ License headers failed!", fg=typer.colors.BRIGHT_RED, bold=True)

    raise typer.Exit(code=result.return_code)


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
    setup: Annotated[
        bool, typer.Option("--setup", help="Set up Jest configuration instead of running tests")
    ] = False,
    skip_services: Annotated[
        bool, typer.Option("--skip-services", help="Skip starting Docker services")
    ] = False,
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
    extra_args = ctx.args if ctx.args else []

    context = discover_context()

    # Start services unless already running or explicitly skipped, and get
    # the environment variables needed to connect to them
    if skip_services:
        services_mgr = ServicesLifecycleManager(
            config=context.config, project_root=context.root_directory
        )
        service_env = services_mgr.load_service_env()
    else:
        service_env = _start_services_if_needed_impl(quiet=quiet)

    js_commands.run_jstest_command(
        context, setup=setup, service_env=service_env, extra_args=extra_args, quiet=quiet
    )


@library_app.command("oarepo-versions")
def library_oarepo_versions(
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress command output")] = False,
) -> None:
    """List supported OARepo and Python versions (JSON output).

    Parses pyproject.toml for OARepo version constraints in [project].dependencies
    and [project].optional-dependencies, and outputs a JSON object with:
    - oarepo_versions: List of detected OARepo major versions (as strings), highest-first
    - python_versions: List of compatible Python versions (as strings)
    - node_versions: List of Node.js versions (hard-coded to ["24"])

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
        "node_versions": ["24"],  # Hard-coded to match bash script behavior
    }

    # Print JSON to stdout (so it can be piped or parsed)
    print(json.dumps(output, separators=(",", ": ")))
