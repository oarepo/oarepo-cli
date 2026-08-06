# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""OARepo CLI main entry point."""

from __future__ import annotations

import sys
from pathlib import Path  # noqa: TC003
from typing import Annotated

import typer

from oarepo_cli import __version__
from oarepo_cli.cli.installer import new_repository
from oarepo_cli.cli.library import library_app
from oarepo_cli.cli.repository import repository_app
from oarepo_cli.core import signals
from oarepo_cli.core.dependency_check import check_invenio_cli_version

# Create the root CLI application
app = typer.Typer(
    name="oarepo-cli",
    help="OARepo CLI - Library and Repository Management Tool",
    no_args_is_help=True,
    add_completion=False,
)

# Register subcommand groups
app.add_typer(library_app, name="library")
app.add_typer(repository_app, name="repository")

# Top-level convenience command (not part of a subcommand group)
app.command("new")(new_repository)


def version_callback(value: bool) -> None:
    """Display version and exit."""
    if value:
        typer.echo(f"oarepo-cli version {__version__}")
        raise typer.Exit


@app.callback()
def main(
    ctx: typer.Context,
    _version: Annotated[
        bool | None,
        typer.Option(
            "--version",
            "-v",
            help="Show version and exit",
            callback=version_callback,
            is_eager=True,
        ),
    ] = None,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            help="Enable verbose output",
        ),
    ] = False,
    config: Annotated[
        Path | None,
        typer.Option(
            "--config",
            help="Path to configuration file",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
        ),
    ] = None,
    cd: Annotated[
        Path | None,
        typer.Option(
            "--cd",
            help="Change to directory before executing",
            exists=True,
            file_okay=False,
            dir_okay=True,
        ),
    ] = None,
) -> None:
    """Oarepo CLI - Manage OARepo libraries and repositories.

    Use 'oarepo-cli COMMAND --help' for help on specific commands.
    """
    # Store global options in context for subcommands to access
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    ctx.obj["config"] = config

    # Change directory if requested
    if cd:
        import os

        os.chdir(cd)
        ctx.obj["cwd"] = cd


def cli_main() -> None:
    """Entry point for the CLI."""
    signals.install()
    try:
        check_invenio_cli_version()
        app()
    except KeyboardInterrupt:
        typer.echo("\nInterrupted by user", err=True)
        sys.exit(130)  # Standard exit code for SIGINT
    except Exception as e:  # noqa: BLE001
        typer.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    cli_main()
