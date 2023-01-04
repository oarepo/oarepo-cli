from pathlib import Path

import click

from oarepo_cli.config import MonorepoConfig

from ...utils import print_banner, to_python_name

from ...ui.wizard import StaticWizardStep, Wizard
from .step_01_install_site import InstallSiteStep
from .step_02_fixup_code import FixupSiteCodeStep
from .step_03_start_containers import StartContainersStep
from .step_04_create_pipenv import CreatePipenvStep
from .step_05_install_invenio import InstallInvenioStep
from .step_06_init_database import InitDatabaseStep
from .step_07_next_steps import NextStepsStep
import os


@click.command(
    name="add",
    help="""Generate a new site. Invoke this command with a site name. 
The recommended pattern is <something>-site""",
)
@click.option(
    "-p",
    "--project-dir",
    type=click.Path(exists=False, file_okay=False),
    default=lambda: os.getcwd(),
    callback=lambda ctx, param, value: Path(value).absolute(),
)
@click.option("--no-banner", type=bool, default=False)
@click.argument("site_name")
@click.pass_context
def add_site(ctx, project_dir, site_name, no_banner, **kwargs):
    project_dir = Path(project_dir).absolute()
    oarepo_yaml_file = project_dir / "oarepo.yaml"

    cfg = MonorepoConfig(oarepo_yaml_file, section=["sites", site_name])

    if project_dir.exists():
        if oarepo_yaml_file.exists():
            cfg.load()

    site_name = to_python_name(site_name)
    cfg["site_package"] = site_name
    cfg["site_dir"] = f"sites/{site_name}"

    if not no_banner:
        print_banner()

    initialize_wizard = Wizard(
        InstallSiteStep(pause=True),
        FixupSiteCodeStep(),
        StartContainersStep(pause=True),
        CreatePipenvStep(),
        InstallInvenioStep(pause=True),
        InitDatabaseStep(),
        NextStepsStep(pause=True),
    )
    initialize_wizard.run(cfg)


if __name__ == "__main__":
    initialize()
