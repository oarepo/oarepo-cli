import click as click

from .add.cli import add_model
from .compile.cli import compile_model
from .install.cli import install_model
from .uninstall.cli import uninstall_model
from .list import list_models


@click.group(
    help="Model-related tools (add model, compile, install, load and dump data)"
)
def model():
    pass


model.add_command(add_model)
model.add_command(compile_model)
model.add_command(install_model)
model.add_command(uninstall_model)
model.add_command(list_models)
