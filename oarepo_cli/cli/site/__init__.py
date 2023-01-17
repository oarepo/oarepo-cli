import click as click

from .add import add_site


@click.group(help="Repository site related tools")
def site():
    pass


site.add_command(add_site)
