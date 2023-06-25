from pathlib import Path

import click as click

from oarepo_cli.assets import build_assets

# from oarepo_cli.develop import call_task, install_editable_sources, copy_invenio_cfg, db_init, search_init, \
#     create_custom_fields, import_fixtures, development_script, Runner
from oarepo_cli.utils import with_config


@click.command(
    name="docker-develop",
    hidden=True,
    help="Internal action called inside the development docker. "
    "Do not call from outside as it will not work. "
    "Call from the directory containing the oarepo.yaml",
)
@click.option(
    "--virtualenv",
    help="Path to invenio virtualenv",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
)
@click.option(
    "--invenio",
    help="Path to invenio instance directory",
    type=click.Path(file_okay=False, path_type=Path),
)
@click.option(
    "--skip-initialization",
    help="Skip the database/es initialization and loading fixtures",
    is_flag=True,
)
@click.option("--site", help="Name of the site to run the development in")
@click.option("--host", help="Bind host", default="127.0.0.1")
@click.option("--port", help="Bind port", default="5000")
@with_config(config_section=lambda site=None, **kwargs: ["sites", site])
def develop(
    cfg, *, virtualenv: Path, invenio: Path, skip_initialization, host, port, **kwargs
):
    if not invenio:
        invenio = virtualenv / "var" / "instance"
        if not invenio.exists():
            invenio.mkdir(parents=True)
    site_dir = cfg.project_dir / cfg["site_dir"]

    call_task(install_editable_sources, cfg=cfg, virtualenv=virtualenv, invenio=invenio)
    if not skip_initialization:
        call_task(copy_invenio_cfg, cfg=cfg, virtualenv=virtualenv, invenio=invenio)
        call_task(db_init, virtualenv=virtualenv, invenio=invenio)
        call_task(search_init, virtualenv=virtualenv, invenio=invenio)
        call_task(create_custom_fields, virtualenv=virtualenv, invenio=invenio)
        call_task(import_fixtures, virtualenv=virtualenv, invenio=invenio)
    call_task(
        build_assets, pdm_name=cfg["pdm_name"], invenio=invenio, site_dir=site_dir
    )
    call_task(development_script, virtualenv=virtualenv, invenio=invenio)

    runner = Runner(virtualenv, invenio, site_dir, host, port)
    runner.run()
