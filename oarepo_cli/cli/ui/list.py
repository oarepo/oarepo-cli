import click as click

from oarepo_cli.cli.utils import with_config


@click.command(name="list", help="List installed user interfaces")
@with_config()
def list_uis(cfg, **kwargs):
    for ui in cfg.whole_data.get("ui", {}):
        print(ui)
