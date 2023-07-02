from typing import List

import click as click

from oarepo_cli.utils import commit_git, with_config

from ...config import MonorepoConfig
from ...site.site_support import SiteSupport
from ...wizard.docker import DockerRunner
from .wizard import UnInstallUIWizard


@click.command(
    name="uninstall",
    help="""
Uninstall the ui from the current site. Required arguments:
    <name>   ... name of the already existing ui""",
)
@click.argument("name", required=True)
@click.argument("site_name", required=False)
@with_config(config_section=lambda name, **kwargs: ["ui", name])
def uninstall_ui(
    cfg: MonorepoConfig = None,
    no_input=False,
    silent=False,
    step=None,
    steps=False,
    verbose=False,
    site_name=None,
    **kwargs,
):
    commit_git(
        cfg.project_dir,
        f"before-ui-uninstall-{cfg.section}",
        f"Committed automatically before ui {cfg.section} has been uninstalled",
    )
    site_support = SiteSupport(cfg, site_name)

    ui_sites: List[str] = cfg.setdefault("sites", [])

    if site_support.site_name in ui_sites:
        ui_sites.remove(site_support.site_name)
    cfg.save()

    runner = DockerRunner(cfg, no_input)
    wizard = UnInstallUIWizard(runner, site_support=site_support)

    if steps:
        wizard.list_steps()
        return

    wizard.run_wizard(
        cfg, no_input=no_input, silent=silent, selected_steps=step, verbose=verbose
    )
    commit_git(
        cfg.project_dir,
        f"after-ui-uninstall-{cfg.section}",
        f"Committed automatically after ui {cfg.section} has been uninstalled",
    )
