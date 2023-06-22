import click as click

from oarepo_cli.ui.add.wizard import AddUIWizard
from oarepo_cli.utils import commit_git, with_config


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
    wizard = AddUIWizard()
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
