import click as click

from oarepo_cli.utils import with_config


@click.command(name="list", help="List installed sites")
@with_config()
def list_sites(cfg=None, **kwargs):
    for site in cfg.whole_data.get("sites", {}):
        print(site)
