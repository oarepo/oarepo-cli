import os

import click

from oarepo_cli.site.add.wizard import AddSiteWizard
from oarepo_cli.utils import commit_git, to_python_name, with_config
from oarepo_cli.wizard.docker import DockerRunner


@click.command(
    name="add",
    help="""Generate a new site.  Required arguments:
    <name>   ... name of the site. The recommended pattern for it is <something>-site""",
)
@click.argument("name")
@with_config(config_section=lambda name, **kwargs: ["sites", name])
def add_site(
    cfg=None,
    name=None,
    no_input=False,
    silent=False,
    step=None,
    verbose=False,
    steps=False,
    **kwargs,
):

    print(f'Current user {os.getuid()}:{os.getgid()}')

    commit_git(
        cfg.project_dir,
        f"before-site-install-{cfg.section}",
        f"Committed automatically before site {cfg.section} has been added",
    )
    cfg["site_package"] = to_python_name(name)
    cfg["site_dir"] = f"sites/{name}"

    runner = DockerRunner(running_in_container=cfg.running_in_docker, use_container=cfg.use_docker)
    initialize_wizard = AddSiteWizard(runner)
    if steps:
        initialize_wizard.list_steps()
        return

    initialize_wizard.run_wizard(
        cfg, no_input=no_input, silent=silent, single_step=step, verbose=verbose
    )
    commit_git(
        cfg.project_dir,
        f"after-site-install-{cfg.section}",
        f"Committed automatically after site {cfg.section} has been added",
    )
