import click as click

from .add.cli import add_ui
from .install.cli import install_ui
from .uninstall.cli import uninstall_ui
from .list import list_uis


@click.group(help="User interface related tools (add user interface for a model, ...)")
def ui():
    pass


ui.add_command(add_ui)
ui.add_command(install_ui)
ui.add_command(uninstall_ui)
ui.add_command(list_uis)
