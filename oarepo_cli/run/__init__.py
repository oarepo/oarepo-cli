import sys

import click as click

from oarepo_cli.utils import run_cmdline, with_config


@click.command(name="run", help="Run the server")
@click.option("-c", "--celery")
@click.argument("site", default=None, required=False)
@with_config()
def run_server(cfg=None, celery=False, site=None, **kwargs):
    sites = cfg.whole_data.get("sites", {})
    if not site:
        if len(sites) == 1:
            site = next(iter(sites.keys()))
        else:
            print(
                f"You have more than one site installed ({list(sites.keys())}), please specify its name on the commandline"
            )
            sys.exit(1)
    else:
        if site not in sites:
            print(
                f"Site with name {site} not found in repository sites {list(sites.keys())}"
            )
            sys.exit(1)

    site = sites[site]
    site_dir = cfg.project_dir.absolute() / site["site_dir"]

    return run_cmdline(
        ".venv/bin/invenio",
        "run",
        "--cert",
        "docker/nginx/test.crt",
        "--key",
        "docker/nginx/test.key",
        cwd = site_dir,
    )
