import click as click

from oarepo_cli.utils import with_config

from .wizard import InstallWizard


@click.command(
    name="install",
    help="""
    Install the UI to the site. Required arguments:
    <name>   ... name of the ui. The recommended pattern for it is <modelname>-ui
    """,
)
@click.argument("name")
@with_config(config_section=lambda name, **kwargs: ["ui", name])
def install_ui(
    cfg=None,
    step=None,
    no_input=False,
    silent=False,
    verbose=False,
    steps=False,
    **kwargs
):
    wizard = InstallWizard()
    if steps:
        wizard.list_steps()
        return

    wizard.run_wizard(
        cfg, single_step=step, no_input=no_input, silent=silent, verbose=verbose
    )
