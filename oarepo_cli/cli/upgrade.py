import json
import click

from oarepo_cli.cli.utils import with_config
from oarepo_cli.utils import run_cmdline


@click.command
@with_config()
@click.pass_context
def upgrade(ctx, project_dir, cfg, **kwargs):
    "Upgrade all virtualenvs in this repository"
    for venv_dir in (project_dir / ".venv").glob("*"):
        if not venv_dir.is_dir():
            continue
        if not (venv_dir / "bin" / "python").exists():
            continue
        upgrade_venv(venv_dir)
    for site in cfg.whole_data["sites"].values():
        upgrade_site(project_dir / site["site_dir"])


def upgrade_venv(venv_dir):
    # run
    packages = run_cmdline(
        "./bin/pip",
        "list",
        "--outdated",
        "--format",
        "json",
        cwd=venv_dir,
        grab_stdout=True,
        grab_stderr=False,
        raise_exception=True,
    )
    packages = json.loads(packages)
    obsolete_packages = [
        f"{p['name']}=={p['latest_version']}"
        for p in packages
        if p["name"].startswith("oarepo") or p["name"].startswith("nrp")
    ]
    if obsolete_packages:
        run_cmdline(
            "./bin/pip",
            "install",
            "-U",
            *obsolete_packages,
            cwd=venv_dir,
            raise_exception=True,
        )


def upgrade_site(site_dir):
    venv_dir = site_dir / ".venv"
    if not venv_dir.exists():
        venv_dir.mkdir(parents=True)
    run_cmdline(
        "pipenv",
        "update",
        cwd=site_dir,
        environ={"PIPENV_IGNORE_VIRTUALENVS": "1"},
    )
