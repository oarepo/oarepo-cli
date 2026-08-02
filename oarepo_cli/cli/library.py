# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Library commands for OARepo CLI."""

from __future__ import annotations

import os
from typing import Annotated

import typer

from oarepo_cli.core.context import discover_context
from oarepo_cli.core.platform import get_platform_detector
from oarepo_cli.services import process
from oarepo_cli.services.lint import LintRunner
from oarepo_cli.services.services_lifecycle import ServicesLifecycleManager
from oarepo_cli.services.test_orchestrator import TestOrchestrator
from oarepo_cli.services.venv import VenvRequirements, VirtualEnvironmentManager
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
        quiet: If True, pass --quiet to docker-services-cli
    """
    # Discover project context
    context = discover_context()

    # Console always shows output for service commands
    console = ConsoleOutput(quiet=False)

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
                f"  Environment variables written to {context.root_directory / '.env-services'}",
                fg=typer.colors.GREEN,
            )
    except Exception as e:
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
        quiet: If True, pass --quiet to docker-services-cli
    """
    # Discover project context
    context = discover_context()

    # Console always shows output for service commands
    console = ConsoleOutput(quiet=False)

    if not (context.root_directory / ".env-services").exists():
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
    except Exception as e:
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
    2. Removes the virtual environment directory
    3. Removes the .env-services file

    Use this when you want to completely remove your development environment,
    for example before deleting the project or when you want a fresh start.

    This command is idempotent - it will not fail if the environment is
    already clean.
    """
    import shutil

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
        except Exception as e:
            console.warning(
                f"  ⚠ Warning: Failed to stop services: {e}",
                fg=typer.colors.YELLOW,
            )
    else:
        console.info("  ℹ No services running", fg=typer.colors.CYAN)

    # Remove .env-services file
    env_services_file = context.root_directory / ".env-services"
    if env_services_file.exists():
        console.info("🗑️  Removing .env-services file...", fg=typer.colors.CYAN)
        try:
            env_services_file.unlink()
            console.info("  ✓ .env-services removed", fg=typer.colors.GREEN)
            items_removed.append(".env-services")
        except Exception as e:
            console.warning(
                f"  ⚠ Warning: Failed to remove .env-services: {e}",
                fg=typer.colors.YELLOW,
            )
    else:
        console.info("  ℹ No .env-services file found", fg=typer.colors.CYAN)

    # Remove venv directory
    if context.venv_path.exists():
        console.info(
            f"🗑️  Removing virtual environment at {context.venv_path}...", fg=typer.colors.CYAN
        )
        try:
            shutil.rmtree(context.venv_path)
            console.info("  ✓ Virtual environment removed", fg=typer.colors.GREEN)
            items_removed.append("venv")
        except Exception as e:
            console.warning(
                f"  ⚠ Warning: Failed to remove venv: {e}",
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

    except Exception as e:
        # Catch any orchestration errors (not pytest failures)
        if not isinstance(e, typer.Exit):
            console.error(
                f"❌ Error running tests: {e}",
                fg=typer.colors.BRIGHT_RED,
                bold=True,
            )
            raise typer.Exit(code=1) from e
        raise


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
        venv_path = venv_mgr.ensure_venv_fast(requirements, quiet=True)
    except Exception as e:
        console.error(
            f"❌ Error ensuring virtual environment: {e}",
            fg=typer.colors.BRIGHT_RED,
            bold=True,
        )
        import traceback  # noqa: TID251

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

    # Build environment for the shell
    shell_env = dict(os.environ)

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
        venv_path = venv_mgr.ensure_venv_fast(requirements, quiet=True)
    except Exception as e:
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

    # Build environment for the command
    cmd_env = dict(os.environ)

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
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress command output")] = False,
) -> None:
    """Run linters and type checkers on the codebase.

    Runs, in order, stopping at the first failure: ruff check, ruff format
    --check, a license header check, a `from __future__ import annotations`
    check, mypy, and pyright. Generates .ruff.toml and .mypy.ini config files
    in the project root.

    Exits with the exit code of the first failing check.
    """
    context = discover_context()
    console = ConsoleOutput(quiet=quiet)

    console.info("🔍 Running linters...", fg=typer.colors.BRIGHT_BLUE, bold=True)

    runner = LintRunner(context=context, quiet=quiet)

    try:
        result = runner.run_lint()
    except Exception as e:
        console.error(f"❌ Error running linters: {e}", fg=typer.colors.BRIGHT_RED, bold=True)
        raise typer.Exit(code=1) from e

    if result.success:
        console.success("✨ ✓ Linting passed!", fg=typer.colors.BRIGHT_GREEN, bold=True)
    else:
        console.error("❌ Linting failed!", fg=typer.colors.BRIGHT_RED, bold=True)

    raise typer.Exit(code=result.return_code)


@library_app.command("format")
def library_format(
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress command output")] = False,
) -> None:
    """Format the codebase using ruff.

    Runs `ruff format` followed by `ruff check --fix`.
    """
    context = discover_context()
    console = ConsoleOutput(quiet=quiet)

    console.info("🎨 Formatting code...", fg=typer.colors.BRIGHT_BLUE, bold=True)

    runner = LintRunner(context=context, quiet=quiet)

    try:
        result = runner.run_format()
    except Exception as e:
        console.error(f"❌ Error formatting code: {e}", fg=typer.colors.BRIGHT_RED, bold=True)
        raise typer.Exit(code=1) from e

    if result.success:
        console.success("✨ ✓ Formatting complete!", fg=typer.colors.BRIGHT_GREEN, bold=True)
    else:
        console.error("❌ Formatting failed!", fg=typer.colors.BRIGHT_RED, bold=True)

    raise typer.Exit(code=result.return_code)
