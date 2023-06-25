from typing import List

import click as click

from oarepo_cli.utils import commit_git, with_config

from ...config import MonorepoConfig
from ...site.site_support import SiteSupport
from ...wizard.docker import DockerRunner
from ..model_support import ModelSupport
from .wizard import UnInstallModelWizard


@click.command(
    name="uninstall",
    help="""
Uninstall the model from the current site. Required arguments:
    <name>   ... name of the already existing model""",
)
@click.argument("name", required=True)
@click.argument("site_name", required=False)
@with_config(config_section=lambda name, **kwargs: ["models", name])
def uninstall_model(
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
        f"before-model-uninstall-{cfg.section}",
        f"Committed automatically before model {cfg.section} has been uninstalled",
    )
    site_support = SiteSupport(cfg, site_name)

    model_sites: List[str] = cfg.setdefault("sites", [])

    if site_support.site_name in model_sites:
        model_sites.remove(site_support.site_name)
    cfg.save()

    runner = DockerRunner(cfg, no_input)
    wizard = UnInstallModelWizard(
        runner, model_support=ModelSupport(cfg), site_support=site_support
    )

    if steps:
        wizard.list_steps()
        return

    wizard.run_wizard(
        cfg, no_input=no_input, silent=silent, selected_steps=step, verbose=verbose
    )
    commit_git(
        cfg.project_dir,
        f"after-model-uninstall-{cfg.section}",
        f"Committed automatically after model {cfg.section} has been uninstalled",
    )
