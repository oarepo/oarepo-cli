import click as click

from oarepo_cli.utils import with_config

from ..site.site_support import SiteSupport
from ..wizard.docker import DockerRunner
from .wizard import OARepoWizard


@click.command(
    name="oarepo",
    help="""
Run the invenio oarepo command, possibly inside a docker""",
    context_settings=dict(
        ignore_unknown_options=True,
    ),
)
@click.option("--site", required=False)
@click.argument("oarepo_args", nargs=-1, type=click.UNPROCESSED)
@with_config()
def oarepo_command(
    cfg=None,
    no_input=False,
    silent=False,
    step=None,
    steps=False,
    verbose=False,
    site=None,
    oarepo_args=None,
    **kwargs,
):
    site_support = SiteSupport(cfg, site)
    runner = DockerRunner(cfg, no_input)
    wizard = OARepoWizard(runner, site_support=site_support, oarepo_args=oarepo_args)

    if steps:
        wizard.list_steps()
        return

    wizard.run_wizard(
        cfg, no_input=no_input, silent=silent, selected_steps=step, verbose=verbose
    )
