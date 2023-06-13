import click as click

from .add import add_local
from .remove import remove_local


@click.group(help="Support for local packages")
def local():
    pass


local.add_command(add_local)
local.add_command(remove_local)
