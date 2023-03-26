import click as click

from oarepo_cli.cli.model.utils import ProjectWizardMixin
from oarepo_cli.cli.utils import PipenvInstallWizardStep, SiteMixin, with_config
from oarepo_cli.ui.wizard import Wizard
from oarepo_cli.ui.wizard.steps import WizardStep


@click.command(
    name="install",
    help="""
    Install the UI to the site. Required arguments:
    <name>   ... name of the ui. The recommended pattern for it is <modelname>-ui
    """,
)
@click.argument("name")
@with_config(config_section=lambda name, **kwargs: ["ui", name])
def install_ui(cfg=None, **kwargs):
    InstallWizard().run(cfg)


class InstallWizardStep(PipenvInstallWizardStep):
    folder = "ui"


class CompileAssetsStep(SiteMixin, ProjectWizardMixin, WizardStep):
    def should_run(self):
        return True

    def after_run(self):
        self.invenio_cli_command("assets", "build")


class InstallWizard(ProjectWizardMixin, Wizard):
    steps = [InstallWizardStep(), CompileAssetsStep()]

    def should_run(self):
        return super().should_run()
