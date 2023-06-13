import subprocess
import sys
import time

import click as click

from oarepo_cli.config import MonorepoConfig
from oarepo_cli.utils import with_config


@click.command(
    name="develop",
    hidden=True,
    help="Start a development docker-compose",
)
@click.option("--site", help="Name of the site to start")
@click.option(
    "--rebuild/--no-rebuild", help="Rebuild the container", default=True, is_flag=True
)
@click.option(
    "--nrp-cli-directory",
    help="Use this directory for nrp-cli (nrp-cli development only)",
    hidden=True,
)
@with_config()
def develop(
    cfg: MonorepoConfig = None,
    site=None,
    rebuild=True,
    nrp_cli_directory=None,
    **kwargs,
):
    if not site:
        site = list(cfg.whole_data["sites"].keys())[0]

    if rebuild:
        subprocess.check_call(
            [
                "docker",
                "build",
                ".",
                "-f",
                f"sites/{site}/docker/Dockerfile.development",
                "-t",
                f"{site}:devel",
                "--build-arg",
                f"REPOSITORY_SITE_NAME={site}",
                "--no-cache",
                "--progress",
                "plain",
            ],
            cwd=cfg.project_dir,
        )

    # run the services
    subprocess.Popen(
        [
            "docker",
            "compose",
            "-f",
            "docker-compose.development.yml",
            "up",
            "-d",
            "cache",
            "db",
            "mq",
            "search",
            "s3",
        ],
        cwd=cfg.project_dir / "sites" / site,
    )
    # wait a bit, proper checking for started containers should be from the app service
    time.sleep(5)
    print(
        "Please make sure that the containers (cache, db, mq, search, s3) are up and running. "
        "The future version will check for this automatically. "
    )
    sys.stdout.flush()
    input("Press Enter when ok")

    app = subprocess.call(
        [
            "docker",
            "compose",
            "-f",
            "docker-compose.development.yml",
            "run",
            "--service-ports",
            "-i",
            "app",
        ],
        cwd=cfg.project_dir / "sites" / site,
    )
