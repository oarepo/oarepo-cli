import json
import os
import re
from pathlib import Path

import click as click
from cookiecutter.main import cookiecutter

from oarepo_cli.cli.model.utils import ProjectWizardMixin
from oarepo_cli.config import MonorepoConfig
from oarepo_cli.ui.wizard import StaticWizardStep, Wizard
from oarepo_cli.ui.wizard.steps import RadioWizardStep, InputWizardStep
from oarepo_cli.utils import print_banner, add_to_pipfile_dependencies


@click.command(
    name="install",
    help="Install the UI to the site",
)
@click.option(
    "-p",
    "--project-dir",
    type=click.Path(exists=False, file_okay=False),
    default=lambda: os.getcwd(),
    callback=lambda ctx, param, value: Path(value).absolute(),
)
@click.argument("name")
def install_ui(project_dir, name, *args, **kwargs):
    oarepo_yaml_file = project_dir / "oarepo.yaml"
    cfg = MonorepoConfig(oarepo_yaml_file, section=["uis", name])
    cfg.load()
    print_banner()

    if not (name.endswith('-ui') or name.endswith('-app')):
        name = name + "-ui"
    cfg["ui_name"] = name

    InstallWizard().run(cfg)


class InstallWizard(ProjectWizardMixin, Wizard):
    steps = [
        StaticWizardStep(
            heading="""
    I will install the UI package into the repository site.
                """,
        ),
        "install",
        StaticWizardStep(
            heading="""
    Now I will compile the assets so that UI's javascript and CSS will be incorporated to site's UI.
                    """,
        ),
        "compile_assets"
    ]

    def install(self, data):
        ui_name = data["ui_name"]
        pipfile = self.site_dir(data) / "Pipfile"
        add_to_pipfile_dependencies(pipfile, ui_name, f"../ui/{ui_name}")

        self.pipenv_command(data, "lock")
        self.pipenv_command(data, "install")

    def compile_assets(self, data):
        self.invenio_command(data, "webpack", "buildall")
