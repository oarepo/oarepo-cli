# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Repository commands for OARepo CLI."""

from __future__ import annotations

import os
import sys
from typing import Annotated

import typer

from oarepo_cli.core.context import discover_context
from oarepo_cli.core.errors import OARepoError, ProcessExecutionError
from oarepo_cli.services import invenio_cli, repository, translations
from oarepo_cli.services.venv import VenvRequirements, VirtualEnvironmentManager

# Create the repository subcommand group
repository_app = typer.Typer(
    name="repository",
    help="Commands for OARepo repository management",
    no_args_is_help=True,
)


@repository_app.callback()
def repository_callback() -> None:
    """Repository command group."""


@repository_app.command()
def install(
    quiet: Annotated[
        bool,
        typer.Option(
            "--quiet",
            "-q",
            help="Suppress output from subprocesses (uv, invenio-cli, etc.)",
        ),
    ] = False,
) -> None:
    """Install repository in virtual environment.

    Mirrors ``repository_runner.sh``'s ``install_repository`` function:
    1. Creates/syncs virtual environment with uv
    2. Copies translation overlays to site-packages
    3. Detects instance path via invenio shell
    4. Creates instance directory and symlinks invenio.cfg
    5. Runs invenio-cli install
    6. Configures local service ports in .invenio.private
    7. Compiles backend translations

    Examples:
        $ oarepo-cli repository install
        $ oarepo-cli repository install --quiet

    Exit codes:
        0: Installation successful
        1: Installation failed
    """
    try:
        # Load context and config
        context = discover_context()

        if not quiet:
            print("\n→ Installing repository...\n", file=sys.stderr)

        # Step 1: Ensure virtual environment exists and sync dependencies
        if not quiet:
            print(f"→ Syncing dependencies in {context.config.venv.path}\n", file=sys.stderr)

        venv_manager = VirtualEnvironmentManager(context.config, context.root_directory)
        requirements = VenvRequirements(
            python_binary=str(context.python_binary),
            oarepo_version=context.oarepo_version,
            extras=[],  # No explicit extras for repositories; uv sync reads pyproject.toml
            editable=True,  # Repositories are always editable installs
        )
        venv_manager.ensure_venv(requirements, quiet=quiet)

        # Step 2: Copy translation overlays
        if not quiet:
            print("→ Copying translation overlays\n", file=sys.stderr)

        collected_dir = os.environ.get("COLLECTED_TRANSLATIONS_DIR")
        translations.copy_translations(
            context,
            collected_translations_dir=collected_dir,
            quiet=quiet,
        )

        # Step 3: Get instance path from Invenio shell
        if not quiet:
            print("→ Detecting instance path\n", file=sys.stderr)

        instance_path = repository.get_instance_path(context, quiet=quiet)

        # Step 4: Ensure instance structure (directory + invenio.cfg symlink)
        repository.ensure_instance_structure(context, instance_path, quiet=quiet)

        # Step 5: Run invenio-cli install
        if not quiet:
            print("→ Running invenio-cli install\n", file=sys.stderr)

        invenio_cli.run_invenio_cli(
            context,
            ["install"],
            quiet=quiet,
            check=True,
        )

        # Step 6: Configure local service ports
        if not quiet:
            print("→ Configuring service ports\n", file=sys.stderr)

        repository.configure_local_ports(context, quiet=quiet)

        # Step 7: Compile backend translations
        # First, ensure translations directory structure exists (bootstrap if needed)
        translations_dir = context.root_directory / "translations"
        messages_pot = translations_dir / "messages.pot"
        en_lc_messages = translations_dir / "en" / "LC_MESSAGES"

        if not messages_pot.exists() or not en_lc_messages.exists():
            if not quiet:
                print(
                    "→ Bootstrapping translations with make-translations\n",
                    file=sys.stderr,
                )
            # Try to run make-translations to bootstrap; don't fail if it errors
            result = translations.run_translations(context, quiet=quiet)
            if not result.success and not quiet:
                print(
                    "⚠️  Warning: make-translations failed, translations not compiled!",
                    file=sys.stderr,
                )

        if not quiet:
            print("→ Compiling backend translations\n", file=sys.stderr)

        # Run invenio-cli translations compile
        result = invenio_cli.run_invenio_cli(
            context,
            ["translations", "compile"],
            quiet=quiet,
            check=False,  # Don't fail if translations compile fails
        )

        if not result.success and not quiet:
            print(
                "⚠️  Warning: invenio-cli failed to compile backend translations!",
                file=sys.stderr,
            )

        # Success!
        if not quiet:
            print("\n✓ Repository installed successfully!\n", file=sys.stderr)

    except (OARepoError, ProcessExecutionError) as e:
        print(f"\n✗ Installation failed: {e}\n", file=sys.stderr)
        raise typer.Exit(1) from e
