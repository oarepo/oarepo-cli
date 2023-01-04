from pathlib import Path

import click
from oarepo_cli.cli.site.add import add_site

from oarepo_cli.config import MonorepoConfig

from ...utils import print_banner

from ...ui.wizard import StaticWizardStep, Wizard
from .step_01_initialize_directory import DirectoryStep
from .step_02_deployment_type import DeploymentTypeStep
from .step_03_create_monorepo import CreateMonorepoStep
from .step_04_install_invenio_cli import InstallInvenioCliStep
from .step_05_install_oarepo_cli import InstallIOARepoCliStep
from .step_06_primary_site_name import PrimarySiteNameStep


@click.command(name="initialize", help="Initialize the whole repository structure")
@click.argument(
    "project_dir", type=click.Path(exists=False, file_okay=False), required=True
)
@click.pass_context
def initialize(ctx, project_dir):
    project_dir = Path(project_dir).absolute()
    oarepo_yaml_file = project_dir / "oarepo.yaml"

    cfg = MonorepoConfig(oarepo_yaml_file)

    if project_dir.exists():
        if oarepo_yaml_file.exists():
            cfg.load()

    cfg["project_dir"] = str(project_dir)

    print_banner()

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
    ctx.invoke(
        add_site,
        project_dir=str(project_dir),
        site_name=cfg["primary_site_name"],
        no_banner=True,
    )


if __name__ == "__main__":
    initialize()
