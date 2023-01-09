import click

from oarepo_cli.cli.site.add import add_site
from oarepo_cli.cli.utils import with_config

from ...ui.wizard import StaticWizardStep, Wizard
from .step_01_initialize_directory import DirectoryStep
from .step_02_deployment_type import DeploymentTypeStep
from .step_03_create_monorepo import CreateMonorepoStep
from .step_04_install_invenio_cli import InstallInvenioCliStep
from .step_05_install_oarepo_cli import InstallIOARepoCliStep
from .step_06_primary_site_name import PrimarySiteNameStep


@click.command(
    name="initialize",
    help="""
Initialize the whole repository structure. Required arguments:
    <project_dir>   ... path to the output directory
""",
)
@click.option("--no-site", default=False, is_flag=True, type=bool)
@with_config(project_dir_as_argument=True)
@click.pass_context
def initialize(ctx, project_dir, cfg, no_site):

    initialize_wizard = Wizard(
        StaticWizardStep(
            """
        This command will initialize a new repository based on OARepo codebase (an extension of Invenio repository).
                """,
            pause=True,
        ),
        DirectoryStep(),
        DeploymentTypeStep(),
        CreateMonorepoStep(pause=True),
        InstallInvenioCliStep(pause=True),
        InstallIOARepoCliStep(pause=True),
        PrimarySiteNameStep(),
    )
    initialize_wizard.run(cfg)
    if not no_site:
        ctx.invoke(
            add_site,
            project_dir=str(project_dir),
            site_name=cfg["primary_site_name"],
            no_banner=True,
        )


if __name__ == "__main__":
    initialize()
