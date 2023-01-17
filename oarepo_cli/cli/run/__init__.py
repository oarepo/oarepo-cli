import sys

import click as click

from oarepo_cli.cli.utils import with_config
from oarepo_cli.utils import run_cmdline


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
    if celery:
        run_invenio_cli(cfg, sites[site])
    else:
        run_pipenv_server(cfg, sites[site])


def run_invenio_cli(config, site):
    invenio_cli = config.project_dir / config.get("invenio_cli")
    site_dir = config.project_dir.absolute() / site["site_dir"]
    run_cmdline(
        "pipenv",
        "run",
        invenio_cli,
        "run",
        cwd=site_dir,
        environ={"PIPENV_IGNORE_VIRTUALENVS": "1"},
    )


def run_pipenv_server(config, site):
    site_dir = config.project_dir.absolute() / site["site_dir"]
    run_cmdline(
        "pipenv",
        "run",
        "invenio",
        "run",
        "--cert",
        "docker/nginx/test.crt",
        "--key",
        "docker/nginx/test.key",
        cwd=site_dir,
        environ={"PIPENV_IGNORE_VIRTUALENVS": "1"},
    )
