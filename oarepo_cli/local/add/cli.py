import click as click

from oarepo_cli.utils import commit_git, with_config

from ...site.site_support import SiteSupport
from ...wizard.docker import DockerRunner
from .wizard import AddLocalWizard


@click.command(
    name="add",
    help="""Add a local package:
    <name>               ... pypi name of the package
    """,
)
@click.option("--site-name", help="Site where to install the package")
@click.argument("name")
@click.argument("github_url", required=False)
@click.option("--branch", help="Branch")
@with_config(config_section=lambda name, **kwargs: ["local", name])
def add_local(
    cfg=None,
    step=None,
    no_input=False,
    silent=False,
    verbose=False,
    steps=False,
    site_name=None,
    github_url=None,
    branch=None,
    **kwargs,
):
    commit_git(
        cfg.project_dir,
        f"before-local-clone-{cfg.section}",
        f"Committed automatically before package {cfg.section} has been cloned",
    )
    cfg["local_dir"] = f"local/{cfg.section_path[-1]}"
    cfg["github_clone_url"] = github_url
    cfg["branch"] = branch

    site_support = SiteSupport(cfg, site_name)

    local_sites = cfg.setdefault("sites", [])
    if site_name not in local_sites:
        local_sites.append(site_support.site_name)

    runner = DockerRunner(cfg, no_input)
    wizard = AddLocalWizard(runner, site_support)
    if steps:
        wizard.list_steps()
        return

    wizard.run_wizard(
        cfg, selected_steps=step, no_input=no_input, silent=silent, verbose=verbose
    )
    commit_git(
        cfg.project_dir,
        f"after-local-clone-{cfg.section}",
        f"Committed automatically after package {cfg.section} has been cloned",
    )
