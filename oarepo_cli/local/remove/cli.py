from typing import List

import click as click

from oarepo_cli.site.site_support import SiteSupport
from oarepo_cli.utils import commit_git, with_config
from oarepo_cli.wizard.docker import DockerRunner

from .wizard import RemoveLocalWizard


@click.command(
    name="remove",
    help="""Remove a local package:
    <name>               ... pypi name of the package
    """,
)
@click.argument("name")
@click.argument("site_name", required=False)
@with_config(config_section=lambda name, **kwargs: ["local", name])
def remove_local(
    cfg=None,
    step=None,
    no_input=False,
    silent=False,
    verbose=False,
    steps=False,
    site_name=None,
    **kwargs,
):
    commit_git(
        cfg.project_dir,
        f"before-local-remove-{cfg.section}",
        f"Committed automatically before package {cfg.section} has been removed",
    )

    site_support = SiteSupport(cfg, site_name)

    list_sites: List[str] = cfg.setdefault("sites", [])
    list_sites.remove(site_support.site_name)
    cfg.save()

    runner = DockerRunner(cfg, no_input)
    wizard = RemoveLocalWizard(runner, site_support=site_support)
    if steps:
        wizard.list_steps()
        return

    wizard.run_wizard(
        cfg, selected_steps=step, no_input=no_input, silent=silent, verbose=verbose
    )

    commit_git(
        cfg.project_dir,
        f"after-local-clone-{cfg.section}",
        f"Committed automatically after package {cfg.section} has been removed",
    )
