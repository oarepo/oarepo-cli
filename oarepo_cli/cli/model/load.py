import os
import venv
from pathlib import Path

import click as click
from colorama import Fore, Style

from oarepo_cli.cli.model.utils import ModelWizardStep, get_model_dir, load_model_repo
from oarepo_cli.ui.wizard import Wizard, WizardStep
from oarepo_cli.ui.wizard.steps import RadioWizardStep
from oarepo_cli.utils import run_cmdline


@click.command(name="load", help="Import (sample) data")
@click.option(
    "-p",
    "--project-dir",
    type=click.Path(exists=False, file_okay=False),
    default=lambda: os.getcwd(),
)
@click.argument("model-name", required=False)
@click.option(
    "-d",
    "--data-path",
    required=False,
    type=click.Path(file_okay=True, dir_okay=False),
    help="Path to the data. If not specified, import sample data",
)
def load_data(project_dir, model_name, data_path, *args, **kwargs):
    cfg, project_dir = load_model_repo(model_name, project_dir)

    cfg["project_dir"] = project_dir

    if not data_path:
        data_path = (
            Path(project_dir) / "models" / model_name / "scripts" / "sample_data.yaml"
        )

    cfg["data_path"] = str(data_path)

    w = Wizard(ImportDataWizardStep())
    w.run(cfg)


class ImportDataWizardStep(ModelWizardStep):

    def after_run(self, data):
        self.invenio_command(data, data["model_name"], "load", data["data_path"])
