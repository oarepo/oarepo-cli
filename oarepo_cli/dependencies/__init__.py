import subprocess

import click as click

from oarepo_cli.config import MonorepoConfig
from oarepo_cli.site.add.steps.resolve_dependencies import ResolveDependenciesStep
from oarepo_cli.utils import with_config
from oarepo_cli.wizard import Wizard


@click.command(
    name="dependencies",
    hidden=True,
    help="Update dependencies for a given site",
)
@click.argument("name")
@click.option("--pdm-name")
@click.option("--pdm-binary")
@click.option('--use-docker', is_flag=True)
@with_config(config_section=lambda name, **kwargs: ["sites", name])
def dependencies(
    cfg: MonorepoConfig = None,
    *,
    pdm_name,
    pdm_binary,
    use_docker,
    **kwargs,
):
    if not use_docker:
        cfg.readonly = True
        cfg["pdm_name"] = pdm_name
        cfg["pdm_binary"] = pdm_binary

        wizard = Wizard(ResolveDependenciesStep())
        wizard.run_wizard(cfg, no_input=True, silent=True, verbose=False)
    else:
        # build the docker from dockerfile
        site = cfg.section_path[-1]
        subprocess.check_call(
            [
                "docker",
                "build",
                ".",
                "-f",
                f"sites/{site}/docker/Dockerfile.pdm",
                "-t",
                f"{site}:pdm",
                "--build-arg",
                f"REPOSITORY_SITE_NAME={site}",
                "--no-cache",
                "--progress",
                "plain",
            ],
            cwd=cfg.project_dir,
        )

        # run the docker
        subprocess.check_call(
            [
                "docker",
                "run",
                '--mount',
                f'type=bind,source=.,target=/repository',
                f"{site}:pdm",
            ],
            cwd=cfg.project_dir,
        )
