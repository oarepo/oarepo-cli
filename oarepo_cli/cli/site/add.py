import click

from oarepo_cli.cli.utils import with_config

from oarepo_cli.wizard import Wizard
from ...utils import commit_git, to_python_name
from .install_site import InstallSiteStep
from .check_requirements import CheckRequirementsStep
from .start_containers import StartContainersStep
from .resolve_dependencies import ResolveDependenciesStep
from .install_invenio import InstallInvenioStep
from .init_database import InitDatabaseStep
from .init_files import InitFilesStep
from .next_steps import NextStepsStep


@click.command(
    name="add",
    help="""Generate a new site.  Required arguments:
    <name>   ... name of the site. The recommended pattern for it is <something>-site""",
)
@click.argument("name")
@with_config(config_section=lambda name, **kwargs: ["sites", name])
@click.pass_context
def add_site(ctx, cfg=None, name=None, no_input=False, silent=False, step=None, verbose=False, steps=False, **kwargs):
    commit_git(
        cfg.project_dir,
        f"before-site-install-{cfg.section}",
        f"Committed automatically before site {cfg.section} has been added",
    )
    cfg["site_package"] = to_python_name(name)
    cfg["site_dir"] = f"sites/{name}"

    initialize_wizard = Wizard(
        InstallSiteStep(pause=True),
        CheckRequirementsStep(),
        StartContainersStep(pause=True),
        ResolveDependenciesStep(),
        InstallInvenioStep(pause=True),
        InitDatabaseStep(),
        InitFilesStep(),
        NextStepsStep(pause=True),
    )
    if steps:
        initialize_wizard.list_steps()
        return

    initialize_wizard.run_wizard(cfg, no_input=no_input, silent=silent, single_step=step, verbose=verbose)
    commit_git(
        cfg.project_dir,
        f"after-site-install-{cfg.section}",
        f"Committed automatically after site {cfg.section} has been added",
    )
