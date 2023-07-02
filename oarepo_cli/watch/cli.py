import click

from oarepo_cli.site.site_support import SiteSupport
from oarepo_cli.utils import with_config
from oarepo_cli.watch.wizard import WatcherWizard
from oarepo_cli.wizard.docker import DockerRunner


@click.command(
    name="ui-watch",
    hidden=True,
    help="Internal action called inside the development docker. " "It watches the ",
)
@with_config()
@click.option("--run-ui", is_flag=True)
@click.option("--site")
def watch_command(
    run_ui,
    site,
    cfg=None,
    step=None,
    no_input=False,
    silent=False,
    verbose=False,
    steps=False,
    **kwargs,
):
    site_support = SiteSupport(cfg, site)

    runner = DockerRunner(cfg, no_input)
    wizard = WatcherWizard(runner, site_support, run_ui)
    if steps:
        wizard.list_steps()
        return

    wizard.run_wizard(
        cfg, selected_steps=step, no_input=no_input, silent=silent, verbose=verbose
    )
