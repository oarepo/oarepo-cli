import click as click

from oarepo_cli.develop.wizard import DevelopWizard
from oarepo_cli.site.site_support import SiteSupport
from oarepo_cli.utils import with_config
from oarepo_cli.wizard.docker import DockerRunner


@click.command(
    name="develop",
    hidden=True,
    help="Use this command to start development server (either in docker or in userspace)",
)
@click.option("--site", required=False)
@with_config()
def develop(
    cfg,
    no_input=False,
    silent=False,
    step=None,
    verbose=False,
    steps=False,
    site=None,
    **kwargs
):
    site_support = SiteSupport(cfg, site)

    runner = DockerRunner(cfg, no_input)
    develop_wizard = DevelopWizard(runner, site_support=site_support)
    if steps:
        develop_wizard.list_steps()
        return

    develop_wizard.run_wizard(
        cfg, no_input=no_input, silent=silent, selected_steps=step, verbose=verbose
    )
