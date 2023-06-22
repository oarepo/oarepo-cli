import click as click

from oarepo_cli.local.remove.wizard import RemoveLocalWizard
from oarepo_cli.utils import commit_git, with_config


@click.command(
    name="remove",
    help="""Remove a local package:
    <name>               ... pypi name of the package
    """,
)
@click.argument("name")
@with_config(config_section=lambda name, **kwargs: ["local", name])
def remove_local(
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
        f"before-local-remove-{cfg.section}",
        f"Committed automatically before package {cfg.section} has been removed",
    )

    wizard = RemoveLocalWizard()
    if steps:
        wizard.list_steps()
        return

    wizard.run_wizard(
        cfg, selected_steps=step, no_input=no_input, silent=silent, verbose=verbose
    )
    commit_git(
        cfg.project_dir,
        f"after-local-clone-{cfg.section}",
        f"Committed automatically after package {cfg.section} has been removed",
    )
