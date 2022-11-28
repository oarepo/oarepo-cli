import os
import venv
from pathlib import Path

import click as click

from oarepo_cli.cli.model.utils import load_model_repo
from oarepo_cli.utils import run_cmdline


@click.command(name="install", help="Install the model into the current site")
@click.option(
    "-p",
    "--project-dir",
    type=click.Path(exists=False, file_okay=False),
    default=lambda: os.getcwd(),
)
@click.argument("model-name", required=False)
def install_model(project_dir, model_name, *args, **kwargs):
    cfg, project_dir = load_model_repo(model_name, project_dir)
