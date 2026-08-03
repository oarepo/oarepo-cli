# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Repository-specific service operations for OARepo projects."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import TYPE_CHECKING

from oarepo_cli.services import invenio_cli, process, translations
from oarepo_cli.services.venv import VenvRequirements, VirtualEnvironmentManager
from oarepo_cli.ui import ConsoleOutput

if TYPE_CHECKING:
    from oarepo_cli.core.context import ProjectContext


def configure_local_ports(context: ProjectContext, *, quiet: bool = False) -> None:
    """Configure local service ports in .invenio.private file.

    Mirrors ``repository_runner.sh``'s port configuration step in install_repository:
    reads port values from the ``variables`` file and writes them to ``.invenio.private``.

    Args:
        context: Project context with paths and configuration
        quiet: If True, suppress status messages

    Raises:
        FileNotFoundError: If .invenio.private or variables file doesn't exist
        IOError: If reading/writing files fails
    """
    invenio_private = context.root_directory / ".invenio.private"
    variables_file = context.root_directory / "variables"

    if not invenio_private.exists():
        msg = f".invenio.private not found at {invenio_private}"
        raise FileNotFoundError(msg)

    if not variables_file.exists():
        msg = f"variables file not found at {variables_file}"
        raise FileNotFoundError(msg)

    # Read port values from variables file
    variables_content = variables_file.read_text()
    port_vars = {
        "search_port": "INVENIO_OPENSEARCH_PORT",
        "db_port": "INVENIO_DATABASE_PORT",
        "redis_port": "INVENIO_REDIS_PORT",
        "rabbitmq_port": "INVENIO_RABBIT_PORT",
        "s3_port": "INVENIO_S3_PORT",
        "web_port": "INVENIO_UI_PORT",
    }

    ports: dict[str, str] = {}
    for key, var_name in port_vars.items():
        # Match pattern like: export INVENIO_OPENSEARCH_PORT=9200
        # or INVENIO_OPENSEARCH_PORT=9200
        pattern = rf"(?:export\s+)?{re.escape(var_name)}=([^\s]+)"
        match = re.search(pattern, variables_content)
        if match:
            ports[key] = match.group(1).strip("\"'")

    if not ports:
        if not quiet:
            import sys

            print(
                "\n⚠️  Warning: No port variables found in variables file, skipping port configuration",
                file=sys.stderr,
            )
        return

    if not quiet:
        import sys

        print(
            f"\n→ Configuring local service ports in {invenio_private.name}",
            file=sys.stderr,
        )

    # Read existing .invenio.private and remove old port entries
    content = invenio_private.read_text()
    lines = content.splitlines()

    # Remove lines matching port patterns
    port_pattern = re.compile(r"^(search|db|redis|rabbitmq|s3|web)_port\s*=")
    filtered_lines = [line for line in lines if not port_pattern.match(line)]

    # Write back with new port values
    with invenio_private.open("w") as f:
        # Write existing non-port lines
        if filtered_lines:
            f.write("\n".join(filtered_lines))
            # Add newline if file didn't end with one
            if filtered_lines[-1]:
                f.write("\n")

        # Add new port values
        for key, value in ports.items():
            f.write(f"{key} = {value}\n")

    if not quiet:
        import sys

        print("✓ Port configuration updated\n", file=sys.stderr)


def get_instance_path(context: ProjectContext) -> Path:
    """Get the Invenio instance path without booting the Flask app.

    Historically this ran ``invenio shell -c "print(app.instance_path)"`` to
    ask Invenio directly, but spinning up the full application just to read
    one path is slow. Invenio's own default instance path is
    ``sys.prefix/var/instance``, which for a project's venv is
    ``<venv>/var/instance``; ``INVENIO_INSTANCE_PATH``, when set, overrides
    it. Replicating that resolution here avoids the subprocess entirely. See
    ADR-007 in 00-main-architecture.md.

    Args:
        context: Project context with paths and configuration

    Returns:
        Path to the Invenio instance directory
    """
    instance_path = os.environ.get("INVENIO_INSTANCE_PATH")
    if instance_path:
        return Path(instance_path)

    return context.venv_path / "var" / "instance"


def ensure_instance_structure(
    context: ProjectContext,
    instance_path: Path,
    *,
    quiet: bool = False,
) -> None:
    """Ensure instance directory structure exists and invenio.cfg is symlinked.

    Mirrors ``repository_runner.sh``'s instance setup steps:
    - Create instance_path if it doesn't exist
    - Create symlink to invenio.cfg if it doesn't exist

    Args:
        context: Project context with paths and configuration
        instance_path: Path to the instance directory
        quiet: If True, suppress status messages
    """
    if not quiet:
        import sys

        print(
            f"\n→ Instance path: {instance_path}",
            file=sys.stderr,
        )

    # Create instance directory if it doesn't exist
    if not instance_path.exists():
        if not quiet:
            import sys

            print(
                f"  Creating instance path: {instance_path}",
                file=sys.stderr,
            )
        instance_path.mkdir(parents=True, exist_ok=True)

    # Create symlink to invenio.cfg if it doesn't exist
    invenio_cfg_link = instance_path / "invenio.cfg"
    invenio_cfg_source = context.root_directory / "invenio.cfg"

    if not invenio_cfg_link.exists() and invenio_cfg_source.exists():
        if not quiet:
            import sys

            print(
                f"  Symlinking {invenio_cfg_source.name} to instance",
                file=sys.stderr,
            )
        # Use relative path if possible, absolute otherwise
        try:
            invenio_cfg_link.symlink_to(invenio_cfg_source)
        except OSError:
            # If symlink fails (e.g., on Windows without admin), try copy instead
            import shutil

            shutil.copy2(invenio_cfg_source, invenio_cfg_link)

    if not quiet:
        import sys

        print("✓ Instance structure ready\n", file=sys.stderr)


def install_repository(context: ProjectContext, *, quiet: bool = False) -> None:
    """Install/reinstall a repository into its virtual environment.

    Mirrors ``repository_runner.sh``'s ``install_repository`` function:
    1. Creates/syncs virtual environment with uv
    2. Copies translation overlays to site-packages
    3. Resolves instance path (INVENIO_INSTANCE_PATH or <venv>/var/instance)
    4. Creates instance directory and symlinks invenio.cfg
    5. Runs invenio-cli install
    6. Configures local service ports in .invenio.private
    7. Compiles backend translations

    Shared by ``repository install``, ``upgrade_repository`` (below, which
    cleans the venv and uv cache first, then reinstalls), and
    ``ModelManager.create_model()`` (which reinstalls after adding a model,
    if a venv already exists) -- mirroring how repository_runner.sh's
    ``install_repository`` is called from ``install``, ``upgrade_repository``,
    and ``create_model`` alike. Callers are responsible for their own
    top-level success message and ``(OARepoError, ProcessExecutionError)``
    handling.

    Args:
        context: Project context with paths and configuration
        quiet: If True, suppress status/progress messages

    Raises:
        ProcessExecutionError: If a required step (uv sync, invenio-cli
            install) fails
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

    instance_path = get_instance_path(context)

    # Step 4: Ensure instance structure (directory + invenio.cfg symlink)
    ensure_instance_structure(context, instance_path, quiet=quiet)

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

    configure_local_ports(context, quiet=quiet)

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


def upgrade_repository(context: ProjectContext, *, quiet: bool = False) -> None:
    """Upgrade repository: clean venv/cache and reinstall from scratch.

    Mirrors ``repository_runner.sh``'s ``upgrade_repository`` function:
    1. Removes the virtual environment (if present)
    2. Removes uv.lock (if present)
    3. Cleans the uv cache (``uv cache clean --force``)
    4. Reinstalls the repository (see ``install_repository`` above)

    Shared by ``repository upgrade`` and ``LocalPackageManager`` (which
    triggers a full upgrade after adding/removing a local package,
    unconditionally -- mirroring repository_runner.sh's
    ``local_sources_cmd``'s unconditional call to ``upgrade_repository``
    after ``uv add``, unlike ``ModelManager.create_model()``'s conditional
    reinstall). Callers are responsible for their own top-level success
    message and ``(OARepoError, ProcessExecutionError)`` handling.

    Args:
        context: Project context with paths and configuration
        quiet: If True, suppress status/progress messages

    Raises:
        ProcessExecutionError: If ``uv cache clean`` or ``install_repository``
            fails
    """
    console = ConsoleOutput(quiet=quiet)

    venv_manager = VirtualEnvironmentManager(context.config, context.root_directory)
    if context.venv_path.exists():
        console.info("→ Removing virtual environment...\n")
    if (context.root_directory / "uv.lock").exists():
        console.info("→ Removing uv.lock...\n")
    venv_manager.cleanup()

    console.info("→ Cleaning uv cache...\n")
    process.run(["uv", "cache", "clean", "--force"], check=True, interactive=not quiet)

    console.info("→ Reinstalling repository...\n")
    install_repository(context, quiet=quiet)
