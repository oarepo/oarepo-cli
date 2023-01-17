import click as click

from oarepo_cli.cli.utils import with_config


@click.command(name="list", help="List installed models")
@with_config()
def list_models(cfg=None, **kwargs):
    for model in cfg.whole_data.get("models", {}):
        print(model)
