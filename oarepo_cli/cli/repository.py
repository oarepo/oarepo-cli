# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Repository commands for OARepo CLI."""

from __future__ import annotations

import os
from typing import Annotated

import typer

from oarepo_cli.core.context import ProjectContext, discover_context
from oarepo_cli.core.errors import OARepoError, ProcessExecutionError
from oarepo_cli.services import invenio_cli, process, repository, translations
from oarepo_cli.services.venv import VenvRequirements, VirtualEnvironmentManager
from oarepo_cli.ui import ConsoleOutput

# Create the repository subcommand group
repository_app = typer.Typer(
    name="repository",
    help="Commands for OARepo repository management",
    no_args_is_help=True,
)


@repository_app.callback()
def repository_callback() -> None:
    """Repository command group."""


def _install_repository(context: ProjectContext, *, quiet: bool) -> None:
    """Run the install steps, without any top-level success/failure messaging.

    Mirrors ``repository_runner.sh``'s ``install_repository`` function:
    1. Creates/syncs virtual environment with uv
    2. Copies translation overlays to site-packages
    3. Resolves instance path (INVENIO_INSTANCE_PATH or <venv>/var/instance)
    4. Creates instance directory and symlinks invenio.cfg
    5. Runs invenio-cli install
    6. Configures local service ports in .invenio.private
    7. Compiles backend translations

    Shared by both ``install`` and ``upgrade`` (which cleans the venv and uv
    cache, then reinstalls), mirroring how ``repository_runner.sh``'s
    ``upgrade_repository`` calls ``install_repository`` directly. Callers
    are responsible for their own top-level success message and
    ``(OARepoError, ProcessExecutionError)`` handling.
    """
    console = ConsoleOutput(quiet=quiet)

    # Step 1: Ensure virtual environment exists and sync dependencies
    console.info(f"→ Syncing dependencies in {context.config.venv.path}\n")

    venv_manager = VirtualEnvironmentManager(context.config, context.root_directory)
    requirements = VenvRequirements(
        python_binary=str(context.python_binary),
        oarepo_version=context.oarepo_version,
        extras=[],  # No explicit extras for repositories; uv sync reads pyproject.toml
        editable=True,  # Repositories are always editable installs
    )
    venv_manager.ensure_venv(requirements, quiet=quiet)

    # Step 2: Copy translation overlays
    console.info("→ Copying translation overlays\n")

    collected_dir = os.environ.get("COLLECTED_TRANSLATIONS_DIR")
    translations.copy_translations(
        context,
        collected_translations_dir=collected_dir,
        quiet=quiet,
    )

    # Step 3: Get instance path from Invenio shell
    console.info("→ Detecting instance path\n")

    instance_path = repository.get_instance_path(context)

    # Step 4: Ensure instance structure (directory + invenio.cfg symlink)
    repository.ensure_instance_structure(context, instance_path, quiet=quiet)

    # Step 5: Run invenio-cli install
    console.info("→ Running invenio-cli install\n")

    invenio_cli.run_invenio_cli(
        context,
        ["install"],
        quiet=quiet,
        check=True,
    )

    # Step 6: Configure local service ports
    console.info("→ Configuring service ports\n")

    repository.configure_local_ports(context, quiet=quiet)

    # Step 7: Compile backend translations
    # First, ensure translations directory structure exists (bootstrap if needed)
    translations_dir = context.root_directory / "translations"
    messages_pot = translations_dir / "messages.pot"
    en_lc_messages = translations_dir / "en" / "LC_MESSAGES"

    if not messages_pot.exists() or not en_lc_messages.exists():
        console.info("→ Bootstrapping translations with make-translations\n")
        # Try to run make-translations to bootstrap; don't fail if it errors
        result = translations.run_translations(context, quiet=quiet)
        if not result.success:
            console.warning("⚠️  Warning: make-translations failed, translations not compiled!")

    console.info("→ Compiling backend translations\n")

    # Run invenio-cli translations compile
    result = invenio_cli.run_invenio_cli(
        context,
        ["translations", "compile"],
        quiet=quiet,
        check=False,  # Don't fail if translations compile fails
    )

    if not result.success:
        console.warning("⚠️  Warning: invenio-cli failed to compile backend translations!")


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

    See ``_install_repository`` for the individual steps.

    Examples:
        $ oarepo-cli repository install
        $ oarepo-cli repository install --quiet

    Exit codes:
        0: Installation successful
        1: Installation failed
    """
    try:
        context = discover_context()
        console = ConsoleOutput(quiet=quiet)

        console.info("\n→ Installing repository...\n")

        _install_repository(context, quiet=quiet)

        console.success(
            "\n✓ Repository installed successfully!\n",
            fg=typer.colors.BRIGHT_GREEN,
            bold=True,
        )

    except (OARepoError, ProcessExecutionError) as e:
        console_err = ConsoleOutput(quiet=False)  # Always show errors
        console_err.error(f"\n✗ Installation failed: {e}\n", fg=typer.colors.RED)
        raise typer.Exit(1) from e


@repository_app.command()
def upgrade(
    quiet: Annotated[
        bool,
        typer.Option(
            "--quiet",
            "-q",
            help="Suppress output from subprocesses (uv, invenio-cli, etc.)",
        ),
    ] = False,
) -> None:
    """Upgrade repository: clean venv/cache and reinstall from scratch.

    Mirrors ``repository_runner.sh``'s ``upgrade_repository`` function:
    1. Removes the virtual environment (if present)
    2. Removes uv.lock (if present)
    3. Cleans the uv cache (``uv cache clean --force``)
    4. Reinstalls the repository (same steps as ``repository install``)

    Examples:
        $ oarepo-cli repository upgrade
        $ oarepo-cli repository upgrade --quiet

    Exit codes:
        0: Upgrade successful
        1: Upgrade failed
    """
    try:
        context = discover_context()
        console = ConsoleOutput(quiet=quiet)

        console.info("\n→ Upgrading repository...\n")

        venv_manager = VirtualEnvironmentManager(context.config, context.root_directory)
        if context.venv_path.exists():
            console.info("→ Removing virtual environment...\n")
        if (context.root_directory / "uv.lock").exists():
            console.info("→ Removing uv.lock...\n")
        venv_manager.cleanup()

        console.info("→ Cleaning uv cache...\n")
        process.run(["uv", "cache", "clean", "--force"], check=True, interactive=not quiet)

        console.info("→ Reinstalling repository...\n")
        _install_repository(context, quiet=quiet)

        console.success(
            "\n✓ Upgrade completed successfully!\n",
            fg=typer.colors.BRIGHT_GREEN,
            bold=True,
        )

    except (OARepoError, ProcessExecutionError) as e:
        console_err = ConsoleOutput(quiet=False)  # Always show errors
        console_err.error(f"\n✗ Upgrade failed: {e}\n", fg=typer.colors.RED)
        raise typer.Exit(1) from e
