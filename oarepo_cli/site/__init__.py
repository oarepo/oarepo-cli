import click

from .add import add_site
from .list import list_sites


@click.group(help="Repository site related tools")
def site():
    pass


site.add_command(add_site)
site.add_command(list_sites)
