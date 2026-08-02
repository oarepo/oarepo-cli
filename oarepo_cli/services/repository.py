# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Repository-specific service operations for OARepo projects."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

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
    """Get the Invenio instance path by running Python code in invenio shell.

    Mirrors ``repository_runner.sh``'s instance_path detection:
    ``instance_path=$(echo "print(app.instance_path, end='')" | in_invenio_shell | tail -n1)``

    Args:
        context: Project context with paths and configuration

    Returns:
        Path to the Invenio instance directory

    Raises:
        ProcessExecutionError: If invenio shell command fails
    """
    from oarepo_cli.services import invenio_cli

    result = invenio_cli.run_invenio_shell(
        context,
        "print(app.instance_path, end='')",
        check=True,
    )

    # Take the last line of output (the actual path)
    instance_path_str = result.stdout.strip().splitlines()[-1]
    return Path(instance_path_str)


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
