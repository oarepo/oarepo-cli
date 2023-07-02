import click

from .add.cli import add_site
from .list import list_sites


@click.group(help="Repository site related tools", name="site")
def site_commands():
    pass


site_commands.add_command(add_site)
site_commands.add_command(list_sites)
