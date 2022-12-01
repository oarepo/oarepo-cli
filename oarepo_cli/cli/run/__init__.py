import os
from pathlib import Path

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
def run_server(project_dir, celery=False, *args, **kwargs):
    project_dir = find_oarepo_project(project_dir)
    config = MonorepoConfig(project_dir / "oarepo.yaml")
    config.load()

    if celery:
        run_invenio_cli(config)
    else:
        run_pipenv_server(config)


def run_invenio_cli(config):
    invenio_cli = str(Path(config.get("invenio_cli")).absolute())
    site_dir = Path(config.get("project_dir")).absolute() / config.get("site_dir")
    run_cmdline(
        "pipenv",
        "run",
        invenio_cli,
        "run",
        cwd=site_dir,
        environ={"PIPENV_IGNORE_VIRTUALENVS": "1"},
    )


def run_pipenv_server(config):
    site_dir = Path(config.get("project_dir")).absolute() / config.get("site_dir")
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
