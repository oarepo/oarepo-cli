import click as click

from .add import add_ui

# from .compile import compile_ui
from .install import install_ui
from .list import list_uis


@click.group(help="User interface related tools (add user interface for a model, ...)")
def ui():
    pass


ui.add_command(add_ui)
# ui.add_command(compile_ui)
ui.add_command(install_ui)
ui.add_command(list_uis)
