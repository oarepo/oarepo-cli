import click as click

from oarepo_cli.utils import commit_git, with_config

from .wizard import AddLocalWizard


@click.command(
    name="add",
    help="""Add a local package:
    <name>               ... pypi name of the package
    """,
)
@click.option("--site-name", help="Site where to install the package")
@click.argument("name")
@with_config(config_section=lambda name, **kwargs: ["local", name])
def add_local(
    cfg=None,
    step=None,
    no_input=False,
    silent=False,
    verbose=False,
    steps=False,
    site_name=None,
    **kwargs,
):
    commit_git(
        cfg.project_dir,
        f"before-local-clone-{cfg.section}",
        f"Committed automatically before package {cfg.section} has been cloned",
    )
    cfg["local_dir"] = f"local/{cfg.section_path[-1]}"

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

    wizard = AddLocalWizard()
    if steps:
        wizard.list_steps()
        return

    wizard.run_wizard(
        cfg, single_step=step, no_input=no_input, silent=silent, verbose=verbose
    )
    commit_git(
        cfg.project_dir,
        f"after-local-clone-{cfg.section}",
        f"Committed automatically after package {cfg.section} has been cloned",
    )
