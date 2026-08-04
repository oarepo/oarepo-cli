# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Repository-specific service operations for OARepo projects."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, NoReturn

from oarepo_cli.core.platform import get_platform_detector
from oarepo_cli.services import invenio_cli, process, translations
from oarepo_cli.services.venv import VenvRequirements, VirtualEnvironmentManager
from oarepo_cli.ui import ConsoleOutput

if TYPE_CHECKING:
    from collections.abc import Sequence

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


def upgrade_repository(
    context: ProjectContext, *, quiet: bool = False, clean_cache: bool = True
) -> None:
    """Upgrade repository: clean venv (and, by default, cache) and reinstall from scratch.

    Mirrors ``repository_runner.sh``'s ``upgrade_repository`` function:
    1. Removes the virtual environment (if present)
    2. Removes uv.lock (if present)
    3. Cleans the uv cache (``uv cache clean --force``), unless ``clean_cache`` is False
    4. Reinstalls the repository (see ``install_repository`` above)

    Shared by ``repository upgrade`` (``clean_cache=True``, matching bash) and
    ``LocalPackageManager`` (which triggers a full upgrade after adding/removing
    a local package, unconditionally -- mirroring repository_runner.sh's
    ``local_sources_cmd``'s unconditional call to ``upgrade_repository`` after
    ``uv add``, unlike ``ModelManager.create_model()``'s conditional reinstall
    -- but with ``clean_cache=False``: a local package's own dependencies
    haven't changed, so purging already-downloaded wheels for everything else
    just to reinstall the same versions is wasted time, unlike a real
    ``repository upgrade``, which explicitly wants to force a fresh resolve).
    Callers are responsible for their own top-level success message and
    ``(OARepoError, ProcessExecutionError)`` handling.

    Args:
        context: Project context with paths and configuration
        quiet: If True, suppress status/progress messages
        clean_cache: If False, skip the ``uv cache clean --force`` step

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

    if clean_cache:
        console.info("→ Cleaning uv cache...\n")
        process.run(["uv", "cache", "clean", "--force"], check=True, interactive=not quiet)

    console.info("→ Reinstalling repository...\n")
    install_repository(context, quiet=quiet)


def get_invenio_binary(context: ProjectContext) -> Path:
    """Resolve the path to the venv's own ``invenio`` binary (bare, not ``invenio-cli``)."""
    bin_dir = get_platform_detector().get_venv_bin_dir()
    return context.venv_path / bin_dir / "invenio"


def exec_invenio(context: ProjectContext, args: Sequence[str]) -> NoReturn:
    """Replace the current process with the venv's own ``invenio`` binary. Never returns.

    Mirrors ``repository_runner.sh``'s ``run_invenio()`` (``export
    PYTHONWARNINGS=ignore; activate_venv; invenio "$@"``): a pure, one-shot
    passthrough to the bare ``invenio`` CLI (not ``invenio-cli``, which
    ``invenio_cli.exec_invenio_cli`` handles), like ``cli/library.py``'s
    ``library_invenio``. Process replacement (``os.execve``) lets a
    terminal Ctrl+C hit ``invenio`` directly, exactly as if the user had
    run it themselves, and preserves its exit code exactly -- mirrors
    ``ServerRunner._exec_bare_invenio``'s same approach for ``invenio run``
    specifically.

    Args:
        context: Project context with paths and configuration -- also
            ``chdir``s into ``context.root_directory`` first, since
            ``execve`` has no ``cwd`` parameter of its own
        args: Arguments to pass to ``invenio``

    Raises:
        OSError: If the invenio binary can't be exec'd (not found, not
            executable, ...)
    """
    os.chdir(context.root_directory)
    binary = get_invenio_binary(context)
    env = {**os.environ, "PYTHONWARNINGS": "ignore"}
    os.execve(str(binary), [str(binary), *args], env)


def _run_invenio(context: ProjectContext, args: Sequence[str], *, quiet: bool = False) -> None:
    """Run a bare ``invenio`` subcommand in the venv, waiting for it to complete.

    Unlike ``ServerRunner``, which ``exec``s the final long-running ``invenio
    run``, callers here (``rebuild_index``, ``reset_repository``) need to run
    several one-shot commands in sequence, so this blocks and raises on
    failure like any other subprocess call in this module.
    """
    process.run(
        [str(get_invenio_binary(context)), *args],
        cwd=context.root_directory,
        check=True,
        interactive=not quiet,
    )


def rebuild_index(context: ProjectContext, *, quiet: bool = False) -> None:
    """Destroy and re-create the search index, then rebuild all records/custom fields.

    Mirrors ``repository_runner.sh``'s ``rebuild_index()``: a sequence of bare
    ``invenio`` subcommands (not ``invenio-cli``), run directly against the venv.

    Args:
        context: Project context with paths and configuration
        quiet: If True, suppress status/progress messages

    Raises:
        ProcessExecutionError: If any of the ``invenio`` subcommands fail
    """
    console = ConsoleOutput(quiet=quiet)

    console.info("→ Destroying search index...\n")
    _run_invenio(context, ["index", "destroy", "--yes-i-know"], quiet=quiet)

    console.info("→ Initializing search index...\n")
    _run_invenio(context, ["index", "init"], quiet=quiet)

    console.info("→ Initializing custom fields...\n")
    _run_invenio(context, ["rdm-records", "custom-fields", "init"], quiet=quiet)
    _run_invenio(context, ["communities", "custom-fields", "init"], quiet=quiet)

    console.info("→ Rebuilding all indices...\n")
    _run_invenio(context, ["rdm", "rebuild-all-indices"], quiet=quiet)

    console.success("✓ Search index was destroyed and re-created\n")
    console.info(
        "Please run the server with workers (oarepo-cli repository run) to complete the indexing.\n"
    )


def reset_repository(context: ProjectContext, *, quiet: bool = False) -> None:
    """Full reset: destroy services, wipe venv/lock/local config, reinstall, reseed demo data.

    Mirrors ``repository_runner.sh``'s ``reset_repository()`` (the confirmation
    prompt is the caller's responsibility, e.g. ``cli/repository.py``'s
    ``reset`` command -- this always proceeds unconditionally). Docker
    service destruction failure (e.g. nothing was running) is deliberately
    ignored, matching bash's ``services destroy || true``; every other step
    raises on failure.

    Args:
        context: Project context with paths and configuration
        quiet: If True, suppress status/progress messages

    Raises:
        ProcessExecutionError: If reinstalling, setting up services, or
            seeding the demo admin/user fails
    """
    console = ConsoleOutput(quiet=quiet)

    console.info("→ Stopping and removing services (if running)...\n")
    invenio_cli.run_invenio_cli(context, ["services", "destroy"], quiet=quiet, check=False)

    venv_manager = VirtualEnvironmentManager(context.config, context.root_directory)
    if context.venv_path.exists():
        console.info("→ Removing virtual environment...\n")
    venv_manager.cleanup()

    uv_lock = context.root_directory / "uv.lock"
    if uv_lock.exists():
        console.info("→ Removing uv.lock...\n")
        uv_lock.unlink()

    invenio_private = context.root_directory / ".invenio.private"
    if invenio_private.exists():
        console.info("→ Removing local invenio settings...\n")
        invenio_private.unlink()

    console.info("→ Cleaning uv cache...\n")
    process.run(["uv", "cache", "clean", "--force"], check=True, interactive=not quiet)

    console.info("→ Reinstalling repository...\n")
    install_repository(context, quiet=quiet)

    console.info("→ Setting up services...\n")
    invenio_cli.run_invenio_cli(context, ["services", "setup", "-N"], quiet=quiet, check=True)

    console.info("→ Creating administration group and a sample user@demo.org...\n")
    _run_invenio(context, ["roles", "create", "administration"], quiet=quiet)
    _run_invenio(
        context,
        ["access", "allow", "administration-access", "role", "administration"],
        quiet=quiet,
    )
    _run_invenio(
        context,
        ["access", "allow", "administration-moderation", "role", "administration"],
        quiet=quiet,
    )
    _run_invenio(
        context,
        [
            "users",
            "create",
            "-a",
            "-c",
            "user@demo.org",
            "--password",
            context.config.security.demo_user_password,
        ],
        quiet=quiet,
    )
    _run_invenio(context, ["roles", "add", "user@demo.org", "administration"], quiet=quiet)


def get_python_version(context: ProjectContext) -> str:
    """Return the resolved Python interpreter's version string (e.g. "Python 3.14.4").

    Mirrors ``repository_runner.sh``'s ``show_info()``: ``"$PYTHON" --version``.
    """
    result = process.run(
        [str(context.python_binary), "--version"],
        check=False,
        capture_output=True,
    )
    return (result.stdout or result.stderr).strip()


@dataclass(frozen=True)
class ModelInfo:
    """A discovered record model: name and version extracted from its ``model.py``."""

    name: str
    version: str


_MODEL_VERSION_PATTERN = re.compile(r"""version\s*=\s*["']([^"']+)["']""")


def list_repository_models(context: ProjectContext) -> list[ModelInfo]:
    """List record models under ``models/``, with their version from ``model.py``.

    Mirrors ``repository_runner.sh``'s ``show_info()``'s model discovery: a
    directory under ``models/`` counts as a model only if it has both
    ``.copier-answers.yml`` and ``model.py``; version is the first
    ``version = "..."`` match in ``model.py``, or ``"unknown"`` if none.
    """
    models_dir = context.root_directory / "models"
    if not models_dir.is_dir():
        return []

    models = []
    for entry in sorted(models_dir.iterdir()):
        if not entry.is_dir():
            continue
        if not (entry / ".copier-answers.yml").exists() or not (entry / "model.py").exists():
            continue
        models.append(
            ModelInfo(name=entry.name, version=_extract_model_version(entry / "model.py"))
        )
    return models


def _extract_model_version(model_py: Path) -> str:
    for line in model_py.read_text().splitlines():
        match = _MODEL_VERSION_PATTERN.search(line)
        if match:
            return match.group(1)
    return "unknown"
