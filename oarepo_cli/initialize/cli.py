import click

from oarepo_cli.initialize.wizard import InitializeWizard
from oarepo_cli.utils import with_config


@click.command(
    name="initialize",
    help="""
Initialize the whole repository structure. Required arguments:
    <project_dir>   ... path to the output directory
""",
)
@click.option(
    "--no-site",
    default=False,
    is_flag=True,
    type=bool,
    help="Do not create default site",
)
@click.option("--python", required=False)
@with_config(project_dir_as_argument=True)
def initialize_command(
    *,
    context=None,
    cfg=None,
    no_site=False,
    python=None,
    step=None,
    steps=False,
    no_input=False,
    silent=False,
    verbose=False,
    **kwargs
):
    cfg["python"] = python or "python3.9"
    initialize_wizard = InitializeWizard()
    if steps:
        initialize_wizard.list_steps()
        return

    initialize_wizard.run_wizard(
        cfg, selected_steps=step, no_input=no_input, silent=silent, verbose=verbose
    )
