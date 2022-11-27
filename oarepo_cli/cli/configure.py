import os
from pathlib import Path

import click

from oarepo_cli.actions.configure.model import add_model_wizard
from oarepo_cli.cli.utils import print_banner
from oarepo_cli.config import MonorepoConfig


@click.group()
def run(*args, **kwargs):
    pass


@run.group()
def model():
    pass


@model.command(name="add")
@click.option(
    "-p", "--project-dir", type=click.Path(exists=False, file_okay=False), default=lambda: os.getcwd(),
    callback=lambda ctx, param, value: Path(value).absolute()
)
@click.argument('name')
def add_model(project_dir, name, *args, **kwargs):
    oarepo_yaml_file = project_dir / "oarepo.yaml"
    cfg = MonorepoConfig(oarepo_yaml_file, section=['models', name])
    cfg.load()
    print_banner()
    cfg['model_name'] = name

    add_model_wizard.run(cfg)


if __name__ == "__main__":
    run()
