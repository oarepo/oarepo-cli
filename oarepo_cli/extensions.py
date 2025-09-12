#
# Copyright (c) 2025 CESNET z.s.p.o.
#
# This file is a part of oarepo-cli (see https://github.com/oarepo/oarepo-cli).
#
# oarepo-cli is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.
#
"""A set of extensions to the invenio-cli module."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import click
from invenio_cli.cli.utils import pass_cli_config, run_steps

from .less import LessComponentsCommands

if TYPE_CHECKING:
    from invenio_cli.helpers.cli_config import CLIConfig


@click.group(name="less")
def less_group() -> None:
    """Commands for working with less components."""


@less_group.command(name="register")
@click.option(
    "--theme-config-file",
    type=click.Path(exists=True),
    help="Path to the theme config file.",
)
@pass_cli_config
def register_less_components(cli_config: CLIConfig, theme_config_file: str | None) -> None:
    """Collect and register less components into the theme.less file."""
    steps = LessComponentsCommands(
        cli_config,
    ).register_less_components(
        theme_config_file=Path(theme_config_file) if theme_config_file else None,
    )
    on_fail = "Registration of less components failed."
    on_success = "Registration of less components successful."

    run_steps(steps, on_fail, on_success)


def register_commands(grp: click.Group) -> None:
    """Register extra commands to invenio-cli."""
    grp.add_command(less_group)
