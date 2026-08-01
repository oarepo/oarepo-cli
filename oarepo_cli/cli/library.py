# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Library commands for OARepo CLI."""

from __future__ import annotations

from typing import Annotated

import typer

from oarepo_cli.core.context import discover_context
from oarepo_cli.services.venv import VenvRequirements, VirtualEnvironmentManager

# Create the library subcommand group
library_app = typer.Typer(
    name="library",
    help="Commands for OARepo library development",
    no_args_is_help=True,
)


@library_app.callback()
def library_callback() -> None:
    """Library command group."""


@library_app.command("venv")
def library_venv(
    force: Annotated[
        bool, typer.Option("--force", "-f", help="Recreate venv from scratch")
    ] = False,
    no_editable: Annotated[
        bool, typer.Option("--no-editable", help="Build wheel instead of editable install")
    ] = False,
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
    venv_path = venv_mgr.ensure_venv(requirements, force=force)

    typer.secho("✨ ✓ Virtual environment ready!", fg=typer.colors.BRIGHT_GREEN, bold=True)
    typer.secho(f"  Path: {venv_path}", fg=typer.colors.GREEN)


@library_app.command("upgrade")
def library_upgrade() -> None:
    """Clean cache and recreate virtual environment from scratch.

    This command:
    1. Removes the existing virtual environment (if present)
    2. Cleans the uv cache to ensure fresh package downloads
    3. Recreates the virtual environment with all dependencies

    Use this when you need to completely refresh your development environment,
    for example after updating OARepo or when dependencies become corrupted.

    Note: This does not stop services. Use 'oarepo-cli library stop' first
    if you have services running.
    """
    # Discover project context
    context = discover_context()

    typer.secho("🔄 Upgrading environment...", fg=typer.colors.BRIGHT_BLUE, bold=True)

    # Clean uv cache
    typer.secho("🧹 Cleaning uv cache...", fg=typer.colors.CYAN)
    from oarepo_cli.services import process

    try:
        process.run(["uv", "cache", "clean"], check=True)
        typer.secho("  ✓ Cache cleaned", fg=typer.colors.GREEN)
    except Exception as e:
        typer.secho(f"  ⚠ Warning: Failed to clean uv cache: {e}", fg=typer.colors.YELLOW, err=True)

    # Remove and recreate venv using VirtualEnvironmentManager
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
    venv_path = venv_mgr.ensure_venv(requirements, force=True)

    typer.secho("✨ ✓ Upgrade completed successfully!", fg=typer.colors.BRIGHT_GREEN, bold=True)
    typer.secho(f"  Virtual environment ready at {venv_path}", fg=typer.colors.GREEN)
