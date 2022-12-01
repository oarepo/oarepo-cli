import os
from pathlib import Path

import click as click
from cookiecutter.main import cookiecutter

from oarepo_cli.config import MonorepoConfig
from oarepo_cli.ui.wizard import InputWizardStep, StaticWizardStep, Wizard, WizardStep
from oarepo_cli.ui.wizard.steps import RadioWizardStep
from oarepo_cli.utils import print_banner


@click.command(name="list", help="List installed user interfaces")
@click.option(
    "-p",
    "--project-dir",
    type=click.Path(exists=False, file_okay=False),
    default=lambda: os.getcwd(),
    callback=lambda ctx, param, value: Path(value).absolute(),
)
def list_uis(project_dir, *args, **kwargs):
    oarepo_yaml_file = project_dir / "oarepo.yaml"
    cfg = MonorepoConfig(oarepo_yaml_file)
    cfg.load()

    for ui in cfg.whole_data.get('uis', {}):
        print(ui)
