import click as click

from oarepo_cli.model.install.wizard import InstallModelWizard
from oarepo_cli.utils import commit_git, with_config


@click.command(
    name="install",
    help="""
Install the model into the current site. Required arguments:
    <name>   ... name of the already existing model""",
)
@click.argument("name", required=True)
@click.argument("site_name", required=False)
@with_config(config_section=lambda name, **kwargs: ["models", name])
def install_model(
    cfg=None,
    no_input=False,
    silent=False,
    step=None,
    steps=False,
    verbose=False,
    site_name=None,
    **kwargs,
):
    commit_git(
        cfg.project_dir,
        f"before-model-install-{cfg.section}",
        f"Committed automatically before model {cfg.section} has been installed",
    )
    sites = cfg.whole_data.get("sites", {})
    if not sites:
        print("Please create a site first")
    if not site_name:
        if len(sites) > 1:
            print(
                f"You have more than one site, add site name to the end of this command. Known sites: {', '.join(sites)}"
            )
            return 1
        site_name = next(iter(sites.keys()))
    if site_name not in sites:
        print(f"Site {site_name} has not beem found. Known sites: {', '.join(sites)}")
        return 1
    model_sites = cfg.setdefault("sites", [])
    if site_name not in model_sites:
        model_sites.append(site_name)

    wizard = InstallModelWizard()
    if steps:
        wizard.list_steps()
        return

    wizard.run_wizard(
        cfg, no_input=no_input, silent=silent, single_step=step, verbose=verbose
    )
    commit_git(
        cfg.project_dir,
        f"after-model-install-{cfg.section}",
        f"Committed automatically after model {cfg.section} has been installed",
    )
