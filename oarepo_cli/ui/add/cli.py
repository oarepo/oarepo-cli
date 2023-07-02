import click as click

from oarepo_cli.site.site_support import SiteSupport
from oarepo_cli.utils import commit_git, with_config
from oarepo_cli.wizard.docker import DockerRunner

from .wizard import AddUIWizard


@click.command(
    name="add",
    help="""Generate a new UI. Required arguments:
    <name>   ... name of the ui. The recommended pattern for it is <modelname>-ui
    """,
)
@click.argument("name")
@with_config(config_section=lambda name, **kwargs: ["ui", name])
def add_ui(
    cfg=None,
    step=None,
    no_input=False,
    silent=False,
    verbose=False,
    steps=False,
    **kwargs,
):
    commit_git(
        cfg.project_dir,
        f"before-ui-add-{cfg.section}",
        f"Committed automatically before ui {cfg.section} has been added",
    )

    site_support = SiteSupport(cfg)

    runner = DockerRunner(cfg, no_input)

    wizard = AddUIWizard(runner, site_support=site_support)

    if steps:
        wizard.list_steps()
        return

    wizard.run_wizard(
        cfg, selected_steps=step, no_input=no_input, silent=silent, verbose=verbose
    )
    commit_git(
        cfg.project_dir,
        f"after-ui-add-{cfg.section}",
        f"Committed automatically after ui {cfg.section} has been added",
    )
