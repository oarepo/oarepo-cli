# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Top-level `repo-install` command: scaffolds a brand-new repository.

This is the CLI-only skeleton for `repository_installer.sh`'s replacement:
argument parsing, defaults, and the same upfront validation the shell
script performs in its `parse_arguments()` (uv/uvx/python binaries must
resolve on PATH, a repository name must be given) -- before any subprocess
runs. Mirrors `core/context.py`'s ProjectContext resolution, which
performs the identical "not found" check for its own Python binary.

The actual scaffolding (copier invocation, certificate generation, Docker
compose symlinks, git init) is a separate, later step -- see
`implementation-steps.md`'s Step 5.2 (`services/repository_installer.py`,
`RepositoryInstaller`), not implemented yet.
"""

from __future__ import annotations

import shutil
from pathlib import Path  # noqa: TC003
from typing import Annotated

import typer

from oarepo_cli.core.errors import ConfigurationError, OARepoError
from oarepo_cli.services.process import get_system_path
from oarepo_cli.ui import ConsoleOutput

DEFAULT_PYTHON = "python3.14"
DEFAULT_TEMPLATE = "https://github.com/oarepo/nrp-app-copier"
DEFAULT_TEMPLATE_VERSION = "rdm-14"
DEFAULT_UV = "uv"
DEFAULT_UVX = "uvx"


def _require_binary(binary: str, option: str) -> None:
    """Raise ConfigurationError if `binary` cannot be resolved on PATH.

    Mirrors repository_installer.sh's `command -v "${binary}"` checks for
    uv/uvx/python: verified upfront since copier is invoked as `uvx
    --python <python_binary> ... copier ...` (Step 5.2), where a
    missing/misnamed binary would otherwise only surface as an opaque uvx
    failure well into the installation.
    """
    if shutil.which(binary, path=get_system_path()) is None:
        raise ConfigurationError(
            f"{option} binary '{binary}' not found. Install it, or specify a different "
            f"binary with {option}."
        )


def repo_install(
    repository_name: Annotated[
        str,
        typer.Argument(help="Name of the repository to create (also the target directory)"),
    ],
    python: Annotated[str, typer.Option("--python", help="Python binary to use")] = DEFAULT_PYTHON,
    template: Annotated[
        str,
        typer.Option(
            "--template",
            help="Copier template: a GitHub URL (https://...) or a local path",
        ),
    ] = DEFAULT_TEMPLATE,
    version: Annotated[
        str,
        typer.Option(
            "--version",
            help="Template git ref, used when --template is a GitHub URL",
        ),
    ] = DEFAULT_TEMPLATE_VERSION,
    uv: Annotated[str, typer.Option("--uv", help="uv binary to use")] = DEFAULT_UV,
    uvx: Annotated[str, typer.Option("--uvx", help="uvx binary to use")] = DEFAULT_UVX,
    config: Annotated[  # noqa: ARG001 -- forwarded to RepositoryInstaller once Step 5.2 implements it
        Path | None,
        typer.Option(
            "--config",
            help="Additional copier data file, seeding answers non-interactively",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
        ),
    ] = None,
) -> None:
    """Create a new repository from a copier template.

    See ``services.repository_installer.RepositoryInstaller`` (not yet
    implemented -- see ``implementation-steps.md``'s Step 5.2) for the
    actual scaffolding steps: running copier, generating SSL certificates,
    setting up Docker compose symlinks, and initializing git.

    Examples:
        $ oarepo-cli repo-install my-repo
        $ oarepo-cli repo-install --python python3.14 --version rdm-14 my-repo
        $ oarepo-cli repo-install --template ../local-template my-repo
        $ oarepo-cli repo-install --config answers.yaml my-repo

    Exit codes:
        0: Success
        1: Invalid input (missing repository name, or uv/uvx/python binary
           not found)
    """
    console = ConsoleOutput()
    try:
        if not repository_name.strip():
            raise ConfigurationError("Repository name is required.")
        _require_binary(uv, "--uv")
        _require_binary(uvx, "--uvx")
        _require_binary(python, "--python")
    except OARepoError as e:
        console.error(f"\n✗ repo-install failed: {e}\n", fg=typer.colors.RED)
        raise typer.Exit(1) from e

    console.info(
        f"Creating repository '{repository_name}' using template '{template}' "
        f"with version '{version}'...\n",
        fg=typer.colors.BRIGHT_BLUE,
    )
