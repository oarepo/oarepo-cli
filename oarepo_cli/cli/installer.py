# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Top-level `new` command: scaffolds a brand-new repository.

Argument parsing, defaults, and the same upfront validation
`repository_installer.sh`'s `parse_arguments()` performs (uv/uvx/python
binaries must resolve on PATH, a repository name must be given) -- before
any subprocess runs. Mirrors `core/context.py`'s ProjectContext
resolution, which performs the identical "not found" check for its own
Python binary.

The actual scaffolding (copier invocation, certificate generation, Docker
Compose cleanup, git init) is `services.repository_installer.RepositoryInstaller`
-- see its class docstring for why `--python`/`--uv`/`--uvx` are validated
here but not forwarded to it.
"""

from __future__ import annotations

import shutil
from pathlib import Path  # noqa: TC003
from typing import Annotated

import typer

from oarepo_cli.core.errors import ConfigurationError, OARepoError
from oarepo_cli.services.process import get_system_path
from oarepo_cli.services.repository_installer import RepositoryInstaller
from oarepo_cli.ui import ConsoleOutput

DEFAULT_PYTHON = "python3.14"
DEFAULT_TEMPLATE = "https://github.com/oarepo/nrp-app-copier"
DEFAULT_TEMPLATE_VERSION = "rdm-14"
DEFAULT_UV = "uv"
DEFAULT_UVX = "uvx"


def _require_binary(binary: str, option: str) -> None:
    """Raise ConfigurationError if `binary` cannot be resolved on PATH.

    Mirrors repository_installer.sh's `command -v "${binary}"` checks for
    uv/uvx/python. RepositoryInstaller doesn't actually use these binaries
    itself (see its class docstring) -- validated here purely for
    interface compatibility with the shell script, which requires them
    upfront before running anything.
    """
    if shutil.which(binary, path=get_system_path()) is None:
        raise ConfigurationError(
            f"{option} binary '{binary}' not found. Install it, or specify a different binary with {option}."
        )


def new_repository(
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
    config: Annotated[
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

    See ``services.repository_installer.RepositoryInstaller.install`` for
    the individual steps: running copier, generating SSL certificates,
    cleaning up stale Docker state, and initializing git.

    Examples:
        $ oarepo-cli new my-repo
        $ oarepo-cli new --python python3.14 --version rdm-14 my-repo
        $ oarepo-cli new --template ../local-template my-repo
        $ oarepo-cli new --config answers.yaml my-repo

    Exit codes:
        0: Success
        1: Invalid input (missing repository name, or uv/uvx/python binary
           not found), or repository creation failed

    """
    console = ConsoleOutput()
    try:
        if not repository_name.strip():
            raise ConfigurationError("Repository name is required.")
        _require_binary(uv, "--uv")
        _require_binary(uvx, "--uvx")
        _require_binary(python, "--python")

        console.info(
            f"Creating repository '{repository_name}' using template '{template}' with version '{version}'...\n",
            fg=typer.colors.BRIGHT_BLUE,
        )
        RepositoryInstaller(console).install(
            repository_name,
            template=template,
            version=version,
            config_file=config,
        )
    except OARepoError as e:
        console.error(f"\n✗ Repository creation failed: {e}\n", fg=typer.colors.RED)
        raise typer.Exit(1) from e
