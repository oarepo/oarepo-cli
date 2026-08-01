# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Library commands for OARepo CLI."""

from __future__ import annotations

from typing import Annotated

import typer

from oarepo_cli.core.context import discover_context
from oarepo_cli.services.services_lifecycle import ServicesLifecycleManager
from oarepo_cli.services.venv import VenvRequirements, VirtualEnvironmentManager

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


def _start_services_impl() -> None:
    """Shared implementation for starting services."""
    # Discover project context
    context = discover_context()

    typer.secho("🚀 Starting services...", fg=typer.colors.BRIGHT_BLUE, bold=True)

    # Start services using ServicesLifecycleManager
    services_mgr = ServicesLifecycleManager(
        config=context.config, project_root=context.root_directory
    )

    try:
        env_vars = services_mgr.start_services()

        if not env_vars:
            # Services were skipped (SKIP_SERVICES=1)
            typer.secho("✓ Services skipped", fg=typer.colors.YELLOW)
        else:
            typer.secho(
                "✨ ✓ Services started successfully!", fg=typer.colors.BRIGHT_GREEN, bold=True
            )
            typer.secho(
                f"  Environment variables written to {context.root_directory / '.env-services'}",
                fg=typer.colors.GREEN,
            )
    except Exception as e:
        typer.secho(
            f"❌ Error starting services: {e}", fg=typer.colors.BRIGHT_RED, bold=True, err=True
        )
        raise typer.Exit(code=1) from e


def _stop_services_impl() -> None:
    """Shared implementation for stopping services."""
    # Discover project context
    context = discover_context()

    if not (context.root_directory / ".env-services").exists():
        typer.secho("✓ No services running", fg=typer.colors.YELLOW)
        return

    typer.secho("🛑 Stopping services...", fg=typer.colors.BRIGHT_BLUE, bold=True)

    # Stop services using ServicesLifecycleManager
    services_mgr = ServicesLifecycleManager(
        config=context.config, project_root=context.root_directory
    )

    try:
        services_mgr.stop_services()
        typer.secho("✨ ✓ Services stopped successfully!", fg=typer.colors.BRIGHT_GREEN, bold=True)
    except Exception as e:
        typer.secho(
            f"❌ Error stopping services: {e}", fg=typer.colors.BRIGHT_RED, bold=True, err=True
        )
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

    # Build requirements from context
    requirements = VenvRequirements(
        python_binary=str(context.python_binary),
        oarepo_version=context.oarepo_version,
        extras=[],  # Will be determined from pyproject.toml by VirtualEnvironmentManager
        editable=not no_editable,
    )

    # Create/verify venv
    venv_mgr = VirtualEnvironmentManager(config=context.config)
    venv_path = venv_mgr.ensure_venv(requirements, force=force, quiet=quiet)

    if not quiet:
        typer.secho("✨ ✓ Virtual environment ready!", fg=typer.colors.BRIGHT_GREEN, bold=True)
        typer.secho(f"  Path: {venv_path}", fg=typer.colors.GREEN)


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

    if not quiet:
        typer.secho("🔄 Upgrading environment...", fg=typer.colors.BRIGHT_BLUE, bold=True)

    # Stop services if running
    services_mgr = ServicesLifecycleManager(
        config=context.config, project_root=context.root_directory
    )
    if services_mgr.are_services_running():
        if not quiet:
            typer.secho("🛑 Stopping services...", fg=typer.colors.CYAN)
        try:
            services_mgr.stop_services()
            if not quiet:
                typer.secho("  ✓ Services stopped", fg=typer.colors.GREEN)
        except Exception as e:
            if not quiet:
                typer.secho(
                    f"  ⚠ Warning: Failed to stop services: {e}",
                    fg=typer.colors.YELLOW,
                    err=True,
                )

    # Clean uv cache
    if not quiet:
        typer.secho("🧹 Cleaning uv cache...", fg=typer.colors.CYAN)
    from oarepo_cli.services import process

    try:
        process.run(["uv", "cache", "clean"], check=True, interactive=not quiet)
        if not quiet:
            typer.secho("  ✓ Cache cleaned", fg=typer.colors.GREEN)
    except Exception as e:
        if not quiet:
            typer.secho(
                f"  ⚠ Warning: Failed to clean uv cache: {e}", fg=typer.colors.YELLOW, err=True
            )

    # Remove and recreate venv using VirtualEnvironmentManager
    if not quiet:
        typer.secho("🔨 Recreating virtual environment...", fg=typer.colors.CYAN)

    # Build requirements from context
    requirements = VenvRequirements(
        python_binary=str(context.python_binary),
        oarepo_version=context.oarepo_version,
        extras=[],
        editable=True,  # Default to editable mode
    )

    # Create/verify venv with force=True to recreate
    venv_mgr = VirtualEnvironmentManager(config=context.config)
    venv_path = venv_mgr.ensure_venv(requirements, force=True, quiet=quiet)

    if not quiet:
        typer.secho("✨ ✓ Upgrade completed successfully!", fg=typer.colors.BRIGHT_GREEN, bold=True)
        typer.secho(f"  Virtual environment ready at {venv_path}", fg=typer.colors.GREEN)


@library_app.command("start")
def library_start() -> None:
    """Start Docker services for development and testing.

    Starts the configured Docker services (database, search, message queue,
    cache, S3) and writes connection details to .env-services file.

    The services are configured via environment variables or [tool.oarepo-cli.services]
    in pyproject.toml.
    """
    _start_services_impl()


@services_app.command("start")
def services_start() -> None:
    """Start Docker services for development and testing.

    Starts the configured Docker services (database, search, message queue,
    cache, S3) and writes connection details to .env-services file.

    The services are configured via environment variables or [tool.oarepo-cli.services]
    in pyproject.toml.
    """
    _start_services_impl()


@library_app.command("stop")
def library_stop() -> None:
    """Stop Docker services.

    Stops all running Docker services and removes the .env-services file.
    """
    _stop_services_impl()


@services_app.command("stop")
def services_stop() -> None:
    """Stop Docker services.

    Stops all running Docker services and removes the .env-services file.
    """
    _stop_services_impl()
