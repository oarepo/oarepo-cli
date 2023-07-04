import click

from oarepo_cli.config import MonorepoConfig
from oarepo_cli.site.site_support import SiteSupport
from oarepo_cli.utils import with_config
from oarepo_cli.wizard.docker import DockerRunner

from .wizard import BuildWizard


@click.command(
    name="build",
    help="Install packages and build invenio UI, either for development or production",
)
@with_config()
@click.option("--site")
@click.option("--production/--development")
@click.pass_context
def build_command(
    ctx,
    cfg: MonorepoConfig = None,
    step=None,
    no_input=False,
    silent=False,
    verbose=False,
    steps=False,
    site=None,
    production=None,
    **kwargs,
):
    site_support = SiteSupport(cfg, site)

    runner = DockerRunner(cfg, no_input=True)
    wizard = BuildWizard(runner, site_support, production)

    if site:
        cfg = cfg.clone(["sites", site])
        wizard.site_support = SiteSupport(cfg, site)

    if steps:
        wizard.list_steps()
        return

    wizard.run_wizard(
        cfg, selected_steps=step, no_input=no_input, silent=silent, verbose=verbose
    )
