import click

from oarepo_cli.config import MonorepoConfig
from oarepo_cli.site.site_support import SiteSupport
from oarepo_cli.upgrade.wizard import UpgradeWizard
from oarepo_cli.utils import with_config
from oarepo_cli.wizard.docker import DockerRunner


@click.command(name="upgrade", help="Upgrade dependencies and rebuild site")
@with_config()
@click.option("--site")
@click.pass_context
def upgrade_command(
    ctx,
    cfg: MonorepoConfig = None,
    step=None,
    no_input=False,
    silent=False,
    verbose=False,
    steps=False,
    site=None,
    **kwargs,
):
    if site:
        cfg = cfg.clone(["sites", site])

    runner = DockerRunner(cfg, no_input=no_input)
    wizard = UpgradeWizard(runner, list(cfg.whole_data.get("sites", {}).keys()), site)

    if site:
        cfg = cfg.clone(["sites", site])
        wizard.site_support = SiteSupport(cfg, site)

    if steps:
        wizard.list_steps()
        return

    wizard.run_wizard(
        cfg, selected_steps=step, no_input=no_input, silent=silent, verbose=verbose
    )
