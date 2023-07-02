import click as click

from oarepo_cli.run.wizard import RunSiteWizard
from oarepo_cli.site.site_support import SiteSupport
from oarepo_cli.utils import with_config
from oarepo_cli.wizard.docker import DockerRunner


@click.command(name="run", help="Run the server")
@click.option("-c", "--celery")
@click.option("--site", default=None, required=False)
@with_config()
def run_server_command(
    cfg=None,
    site=None,
    no_input=False,
    silent=False,
    step=None,
    steps=False,
    verbose=False,
    **kwargs
):
    site_support = SiteSupport(cfg, site)

    model_sites = cfg.setdefault("sites", [])
    if site_support.site_name not in model_sites:
        model_sites.append(site_support.site_name)
    cfg.save()

    runner = DockerRunner(cfg, no_input)
    wizard = RunSiteWizard(runner, site_support=site_support)

    if steps:
        wizard.list_steps()
        return

    wizard.run_wizard(
        cfg, no_input=no_input, silent=silent, selected_steps=step, verbose=verbose
    )
