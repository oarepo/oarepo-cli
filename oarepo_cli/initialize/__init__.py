import click

from oarepo_cli.site import add_site
from oarepo_cli.utils import with_config
from oarepo_cli.wizard import StaticStep, Wizard

from .create_monorepo import CreateMonorepoStep
from .initialize_directory import MonorepoDirectoryStep
from .install_nrp_cli import InstallINRPCliStep
from .set_primary_site_name import PrimarySiteNameStep


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
@with_config(project_dir_as_argument=True, allow_docker=False)
def initialize(
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
    initialize_wizard = Wizard(
        StaticStep(
            """
        This command will initialize a new repository based on OARepo codebase (an extension of Invenio repository).
                """,
            pause=True,
        ),
        MonorepoDirectoryStep(),
        CreateMonorepoStep(),
        InstallINRPCliStep(pause=True),
        *([PrimarySiteNameStep()] if not no_site else [])
    )
    if steps:
        initialize_wizard.list_steps()
        return

    initialize_wizard.run_wizard(
        cfg, single_step=step, no_input=no_input, silent=silent, verbose=verbose
    )

    # install all sites from the config file
    sites = cfg.whole_data.get("sites", {})
    if sites:
        for site in sites:
            context.invoke(
                add_site,
                project_dir=str(cfg.project_dir),
                name=site,
                no_input=no_input,
                silent=silent,
                verbose=verbose,
            )
    elif not no_site:
        # if there is no site, install the default one
        context.invoke(
            add_site,
            project_dir=str(cfg.project_dir),
            name=cfg["primary_site_name"],
            no_input=no_input,
            silent=silent,
            verbose=verbose,
        )
    # do not install model nor uis as user might (and will) modify them


if __name__ == "__main__":
    initialize()
