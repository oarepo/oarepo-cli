import click as click

from .add.cli import add_ui
from .install.cli import install_ui
from .list import list_uis
from .uninstall.cli import uninstall_ui


@click.group(
    help="User interface related tools (add user interface for a model, ...)", name="ui"
)
def ui_commands():
    pass


ui_commands.add_command(add_ui)
ui_commands.add_command(install_ui)
ui_commands.add_command(uninstall_ui)
ui_commands.add_command(list_uis)
