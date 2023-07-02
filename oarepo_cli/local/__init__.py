import click as click

from .add.cli import add_local
from .remove.cli import remove_local


@click.group(help="Support for local packages", name="local")
def local_commands():
    pass


local_commands.add_command(add_local)
local_commands.add_command(remove_local)
