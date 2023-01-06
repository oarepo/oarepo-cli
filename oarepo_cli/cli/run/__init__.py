import os
from pathlib import Path
import sys

import click as click

from oarepo_cli.cli.model.utils import load_model_repo
from oarepo_cli.config import MonorepoConfig
from oarepo_cli.utils import find_oarepo_project, run_cmdline


@click.command(name="run", help="Run the server")
@click.option(
    "-p",
    "--project-dir",
    type=click.Path(exists=False, file_okay=False),
    default=lambda: os.getcwd(),
)
@click.option("-c", "--celery")
@click.argument("site", default=None, required=False)
def run_server(project_dir, celery=False, site=None, *args, **kwargs):
    project_dir = find_oarepo_project(project_dir)
    config = MonorepoConfig(project_dir / "oarepo.yaml")
    config.load()
    sites = config.whole_data.get("sites", {})
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
        run_invenio_cli(config, sites[site])
    else:
        run_pipenv_server(config, sites[site])


def run_invenio_cli(config, site):
    invenio_cli = str(Path(config.get("invenio_cli")).absolute())
    site_dir = Path(config.get("project_dir")).absolute() / site["config"]["site_dir"]
    run_cmdline(
        "pipenv",
        "run",
        invenio_cli,
        "run",
        cwd=site_dir,
        environ={"PIPENV_IGNORE_VIRTUALENVS": "1"},
    )


def run_pipenv_server(config, site):
    site_dir = Path(config.get("project_dir")).absolute() / site["config"]["site_dir"]
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
