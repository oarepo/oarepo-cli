import json
import shutil

import click

from oarepo_cli.assets import build_assets
from oarepo_cli.site.install_site import update_and_install_site
from oarepo_cli.utils import run_cmdline, with_config


@click.command
@with_config()
@click.pass_context
def upgrade(ctx, project_dir, cfg, **kwargs):
    "Upgrade all virtualenvs in this repository"
    for venv_dir in (project_dir / ".venv").glob("*"):
        if not venv_dir.is_dir():
            continue
        if venv_dir.name == "oarepo-model-builder":
            shutil.rmtree(venv_dir)
            continue
        if not (venv_dir / "bin" / "python").exists():
            continue
        upgrade_venv(venv_dir)
    for site in cfg.whole_data["sites"]:
        update_and_install_site(cfg, site)
        site_dir = cfg.project_dir / "sites" / site
        build_assets(
            virtualenv=site_dir / ".venv",
            invenio=site_dir / ".venv" / "var" / "instance",
            site_dir=site_dir,
        )


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
