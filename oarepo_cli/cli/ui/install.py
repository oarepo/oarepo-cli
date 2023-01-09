import os
from pathlib import Path

import click as click

from oarepo_cli.cli.model.utils import ProjectWizardMixin
from oarepo_cli.cli.utils import PipenvInstallWizardStep, SiteMixin
from oarepo_cli.config import MonorepoConfig
from oarepo_cli.ui.wizard import Wizard
from oarepo_cli.ui.wizard.steps import RadioWizardStep, WizardStep
from oarepo_cli.utils import print_banner


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

    if not (name.endswith("-ui") or name.endswith("-app")):
        name = name + "-ui"
    cfg["ui_name"] = name

    InstallWizard().run(cfg)


class InstallWizardStep(PipenvInstallWizardStep):
    folder = "ui"


class CompileAssetsStep(SiteMixin, ProjectWizardMixin, WizardStep):
    def should_run(self, data):
        return True

    def after_run(self, data):
        self.invenio_command(data, "webpack", "buildall")


class InstallWizard(ProjectWizardMixin, Wizard):
    steps = [InstallWizardStep(), CompileAssetsStep()]

    def should_run(self, data):
        return super().should_run(data)
