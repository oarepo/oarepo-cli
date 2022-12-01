import os
from pathlib import Path

import click as click

from oarepo_cli.config import MonorepoConfig
from oarepo_cli.utils import print_banner


@click.command(name="add", help="Generate a new UI. Invoke this command with the name of the user interface")
@click.option(
    "-p",
    "--project-dir",
    type=click.Path(exists=False, file_okay=False),
    default=lambda: os.getcwd(),
    callback=lambda ctx, param, value: Path(value).absolute(),
)
@click.argument("name")
def add_ui(project_dir, name, *args, **kwargs):
    oarepo_yaml_file = project_dir / "oarepo.yaml"
    cfg = MonorepoConfig(oarepo_yaml_file, section=["uis", name])
    cfg.load()
    print_banner()
    cfg["ui_name"] = name
